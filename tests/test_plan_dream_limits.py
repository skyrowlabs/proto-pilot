"""Dreaming pressed at its edges: what a model, a race or a hostile input cannot do to a plan."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import (
    DREAM_PASS_NAMES,
    GOOD,
    IDEA,
    NO_REPAIR,
    SLUGS,
    consider_of,
    dream_row,
    edge,
    judged_row,
    outline_of,
    proposal_row,
    repair_of,
    script,
    step,
)

from protopilot import cli
from protopilot.console.progress import DONE, FAILED, fold
from protopilot.jobs import Job
from protopilot.llm import LLMError, _without_patterns
from protopilot.plan import dreaming, passes, pipeline, render, verify
from protopilot.plan.model import (
    DREAM_FIELD_WORDS,
    DREAM_WORD_CAP,
    MAX_SLUG_LENGTH,
    MAX_TOPICS,
    Plan,
    dream_words,
    plan_path,
)
from protopilot.plan.passes import collect, evaluate, outline, propose, repair
from protopilot.spec import SLUG_RE

pytestmark = [pytest.mark.unit]

BREAD = GOOD["collect"]["dreams"][1]
PLAN_WITH_A_DREAM = {
    "slug": "p",
    "title": "t",
    "idea": "i",
    "dreams": [{"id": "d1", "title": "t", "what_if": "w", "lens": "l", "anchor": "a", "takes": "x"}],
}
#: Over the cap in `takes`, whichever other fields it carries.
RAMBLING = {**dream_row(word="rambling"), "takes": " ".join(["word"] * (DREAM_WORD_CAP + 1))}


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def invoke(*args: str):
    return CliRunner().invoke(cli.main, list(args))


def said(result) -> str:
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def changed(before: dict[str, bytes], after: dict[str, bytes]) -> set[str]:
    return {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}


def page(tree: Path, name: str = "dreams.md") -> str:
    return (tree / name).read_text(encoding="utf-8")


def model_plan(tree: Path, **overrides: object) -> Path:
    llm = FakeLLM(script(**overrides))
    assert pipeline.run_plan(job_for(), tree, llm).ok
    assert llm.responses == []
    return tree


def offline_plan(tree: Path) -> Path:
    assert invoke("plan", IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    return tree


def answer(*edges: dict, **fields: list[str]) -> dict:
    return {"edges": list(edges), "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"], **fields}


def round_of(*rows: dict, first: int = 3, proposed: int = 1) -> list[dict]:
    """Collect, evaluate and propose for `rows`, the first `proposed` proposed and the rest set aside."""
    ids = [f"d{first + offset}" for offset in range(len(rows))]
    judged = [judged_row(i, "proposed" if n < proposed else "set-aside") for n, i in enumerate(ids)]
    return [{"dreams": list(rows)}, {"dreams": judged}, {"proposals": [proposal_row(i) for i in ids[:proposed]]}]


class During(FakeLLM):
    """Does `act` to the tree just before answering the pass called `label`."""

    def __init__(self, responses: list[dict], label: str, act):
        super().__init__(responses)
        self.label, self.act = label, act

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == self.label:
            self.act()
        return super().structured(system=system, user=user, schema=schema, label=label)


class DiesAt(FakeLLM):
    def __init__(self, name: str, responses: list[dict]):
        super().__init__(responses)
        self.name = name

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == self.name:
            raise LLMError(f"pass {label!r} failed: out of credit")
        return super().structured(system=system, user=user, schema=schema, label=label)


# -- the suite cannot pass on a run it never made -------------------------


def test_a_script_that_stops_short_at_a_dream_pass_is_on_record(tmp_path):
    with pytest.raises(AssertionError, match="ran out of responses"):
        pipeline.run_plan(job_for(), tmp_path / "tree", FakeLLM(script()[:5]))
    assert FakeLLM.ran_dry == ["collect"]
    FakeLLM.ran_dry.clear()


def test_a_script_that_stops_short_at_repair_is_on_record(tmp_path):
    with pytest.raises(AssertionError, match="ran out of responses"):
        pipeline.run_plan(job_for(), tmp_path / "tree", FakeLLM(script(start={"steps": [step("lending")]})))
    assert FakeLLM.ran_dry == ["repair"]
    FakeLLM.ran_dry.clear()


# -- only a person promotes -----------------------------------------------


def test_repair_cannot_settle_a_dream_or_add_a_topic(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree)
    mended = repair_of([*GOOD["connect"]["edges"], edge("seeds_too", "members")], ["members"])
    forged = {
        **mended,
        "dreams": [{"id": "d2", "verdict": "promoted", "promoted_to": "members"}],
        "topics": [{"slug": "planted", "title": "Planted", "why": "A model said so."}],
    }
    llm = FakeLLM([answer(edge("seeds_too", "members"), edge("members", "seeds_too")), forged])
    assert pipeline.promote(job_for(), tree, "d1", llm).ok
    plan = Plan.load(tree)
    assert [topic.slug for topic in plan.topics] == [*SLUGS, "seeds_too"]
    assert plan.dreams[1] == before.dreams[1]


def test_the_promote_pass_cannot_settle_any_other_dream(tmp_path):
    tree = model_plan(tmp_path / "tree")
    sibling = Plan.load(tree).dreams[1]
    forged = {**answer(), "dreams": [{"id": "d2", "verdict": "dropped", "reason": "A model decided."}]}
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([forged])).ok
    assert Plan.load(tree).dreams[1] == sibling


def test_a_rerender_after_a_promotion_moves_no_byte_and_settles_nothing(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "promote", "d1", "--offline", "--dir", str(tree)).exit_code == 0
    before = snapshot(tree)
    assert invoke("plan", IDEA, "--dir", str(tree)).exit_code == 0
    assert snapshot(tree) == before


@pytest.mark.parametrize("dream_id", ["D1", "d1 ", " d1", "d99", "../d1", "d1\nd2", "%s", "d1;true", "\x1b[31md1"])
@pytest.mark.parametrize("verb", [("promote", "--offline"), ("drop", "--why", "no")])
def test_an_id_the_pool_does_not_hold_changes_nothing_and_is_said_back_inert(tmp_path, verb, dream_id):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("dream", verb[0], dream_id, *verb[1:], "--dir", str(tree))
    assert result.exit_code == 1
    assert f"no dream {dream_id!r}" in said(result)
    assert "\x1b" not in result.output
    assert snapshot(tree) == before


def test_a_promoted_dream_is_listed_once_and_links_to_a_page_that_exists(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    text = page(tree)
    promoted = text[text.index("## Promoted") :]
    assert text.count("### Seeds too (d1)") == 1 and "### Seeds too (d1)" in promoted
    assert "## Proposals" not in text
    target = re.search(r"Now the topic: \[Seeds too\]\((.+?)\)", promoted)
    assert target and (tree / target[1]).is_file()
    assert text.index("Nothing here is researched.") < text.index("## Promoted")


# -- promotion ------------------------------------------------------------


def test_a_promotion_moves_no_other_topic_step_edge_or_dream(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree)
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(edge("seeds_too", "money", "informs"))])).ok
    after = Plan.load(tree)
    assert after.topics[:-1] == before.topics and after.steps == before.steps
    assert after.edges[:-1] == before.edges and after.dreams[1:] == before.dreams[1:]


def test_a_link_leaving_every_topic_waiting_stops_before_repair(tmp_path):
    chain = {"edges": [edge(a, b) for a, b in zip(SLUGS[1:], SLUGS)]}
    tree = model_plan(tmp_path / "tree", connect=chain)
    before = snapshot(tree)
    llm = FakeLLM([answer(edge("members", "seeds_too"), edge("seeds_too", "safety"))])
    with pytest.raises(pipeline.PlanRefused, match="not promoted.*nothing was changed.*cycle"):
        pipeline.promote(job_for(), tree, "d1", llm)
    assert [call["label"] for call in llm.calls] == ["promote"]
    assert snapshot(tree) == before


def test_new_words_that_copy_a_sibling_dream_stop_the_promotion_and_cost_no_repair(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    llm = FakeLLM([answer(risks=[BREAD["what_if"]])])
    with pytest.raises(pipeline.PlanRefused, match=r"Nothing was changed.*\n\[dreams_apart\]"):
        pipeline.promote(job_for(), tree, "d1", llm)
    assert [call["label"] for call in llm.calls] == ["promote"]
    assert snapshot(tree) == before


def test_a_repair_that_lands_nothing_leaves_the_tree_as_it_was(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    llm = FakeLLM([answer(edge("members", "seeds_too")), {"edges": "nonsense", "steps": []}])
    with pytest.raises(pipeline.PlanRefused, match="the repair pass failed"):
        pipeline.promote(job_for(), tree, "d1", llm)
    assert snapshot(tree) == before


@pytest.mark.parametrize(
    "title",
    ["../../etc/passwd", "<script>alert(1)</script>", "日本語の夢", "123 go", "the a an", "a" * 90, "Members"],
    ids=["traversal", "html", "no-latin", "digits-first", "all-filler", "too-long", "a-topics-own-name"],
)
def test_a_hostile_title_becomes_a_safe_slug_and_a_page_inside_the_tree(tmp_path, title):
    tree = model_plan(tmp_path / "tree", collect={"dreams": [{**dream_row(), "title": title}, BREAD]})
    outside = sorted(path.name for path in tmp_path.iterdir())
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    new = Plan.load(tree).topics[-1]
    assert SLUG_RE.fullmatch(new.slug) and len(new.slug) <= MAX_SLUG_LENGTH
    assert (tree / "topics" / f"{new.slug}.md").is_file() and new.title == title
    assert "<script" not in page(tree, f"topics/{new.slug}.md")
    assert sorted(path.name for path in tmp_path.iterdir()) == outside


def test_two_titles_with_no_latin_letters_take_different_slugs(tmp_path):
    rows = [{**dream_row(), "title": "夢の図書館"}, {**BREAD, "title": "夢の種"}]
    tree = model_plan(tmp_path / "tree", collect={"dreams": rows})
    for dream_id in ("d1", "d2"):
        assert pipeline.promote(job_for(), tree, dream_id, FakeLLM([answer()])).ok
    assert [topic.slug for topic in Plan.load(tree).topics[-2:]] == ["plan", "plan_2"]


def test_a_promotion_offline_needs_no_backend_and_calls_nothing(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    calls = []
    real = cli.build_llm
    monkeypatch.setattr(cli, "build_llm", lambda **kw: calls.append(kw) or real(**kw))
    assert invoke("dream", "promote", "d2", "--offline", "--dir", str(tree)).exit_code == 0
    assert calls == [{"offline": True, "backend": None}]
    assert Plan.load(tree).dreams[1].verdict == "promoted"


# -- the race in `_land` --------------------------------------------------


def someone_else_saves(tree: Path):
    def act() -> None:
        plan = Plan.load(tree)
        reason = "Somebody else got here first."
        plan.revised(dreams=[plan.dreams[0].model_copy(update={"reason": reason}), plan.dreams[1]]).save(tree)

    return act


def test_a_promotion_that_lost_a_race_for_the_plan_writes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused, match="changed while this ran.*not written"):
        pipeline.promote(job_for(), tree, "d1", During([answer()], "promote", someone_else_saves(tree)))
    plan = Plan.load(tree)
    assert plan.dreams[0].reason == "Somebody else got here first." and plan.dreams[0].verdict == "proposed"
    assert [topic.slug for topic in plan.topics] == SLUGS
    assert not (tree / "topics" / "seeds_too.md").exists()


def test_a_promotion_that_lost_the_race_during_repair_writes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    mended = repair_of([*GOOD["connect"]["edges"], edge("members", "seeds_too")], ["seeds_too", "members"])
    llm = During([answer(edge("members", "seeds_too")), mended], "repair", someone_else_saves(tree))
    with pytest.raises(pipeline.PlanRefused, match="changed while this ran"):
        pipeline.promote(job_for(), tree, "d1", llm)
    assert [topic.slug for topic in Plan.load(tree).topics] == SLUGS


def test_a_plan_json_reformatted_during_a_promotion_is_no_race(tmp_path):
    tree = model_plan(tmp_path / "tree")

    def reformat() -> None:
        path = plan_path(tree)
        path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8"))), encoding="utf-8")

    assert pipeline.promote(job_for(), tree, "d1", During([answer()], "promote", reformat)).ok


def test_a_page_edited_during_a_promotion_is_drawn_over_and_the_person_is_told(tmp_path):
    tree, job = model_plan(tmp_path / "tree"), job_for()
    llm = During([answer()], "promote", lambda: (tree / "PLAN.md").write_text("mine", encoding="utf-8"))
    assert pipeline.promote(job, tree, "d1", llm).ok
    assert any("PLAN.md differed from plan.json" in line for line in job.lines)
    assert page(tree, "PLAN.md") != "mine"


# -- a dream against what the review changed ------------------------------


def reviewed(tree: Path, llm: FakeLLM, edit) -> None:
    job = job_for()
    plan = pipeline.outlined(job, llm, pipeline.scoped(job, llm))
    assert pipeline.build(job, tree, edit(plan), llm).ok


def test_a_dream_may_extend_a_topic_a_person_added_at_the_review(tmp_path):
    tree = tmp_path / "tree"
    rows = [dream_row(anchor="insurance"), dream_row("the-opposite", word="bread")]
    llm = FakeLLM(script(consider=consider_of([*SLUGS, "insurance"]), collect={"dreams": rows}))
    reviewed(tree, llm, lambda plan: outline.add(plan, "Insurance", "It decides liability."))
    shown = next(call for call in llm.calls if call["label"] == "collect")["user"]
    assert '"slug": "insurance"' in shown
    assert Plan.load(tree).dreams[0].anchor == "insurance"
    assert "- Extends: Insurance" in page(tree)


def test_a_dream_anchored_to_a_topic_the_review_removed_costs_only_itself(tmp_path):
    tree = tmp_path / "tree"
    kept = [slug for slug in SLUGS if slug != "safety"]
    rows = [dream_row(anchor="safety"), dream_row("the-opposite", word="bread")]
    responses = script(consider=consider_of(kept), collect={"dreams": rows}, evaluate={"dreams": [judged_row("d2")]})
    responses[-1] = {"proposals": [proposal_row("d2")]}
    reviewed(tree, FakeLLM(responses), lambda plan: outline.drop(plan, "safety"))
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d2"]


def test_a_collect_schema_offers_only_the_topics_the_review_left(tmp_path):
    class Keeps(FakeLLM):
        anchors: list[str] = []

        def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
            if label == "collect":
                item = schema["properties"]["dreams"]["items"]
                Keeps.anchors = item["properties"]["anchor"]["enum"]
            return super().structured(system=system, user=user, schema=schema, label=label)

    kept = [*(slug for slug in SLUGS if slug != "safety"), "insurance"]
    reviewed(
        tmp_path / "tree",
        Keeps(script(consider=consider_of(kept))),
        lambda plan: outline.add(outline.drop(plan, "safety"), "Insurance", "It decides liability."),
    )
    assert Keeps.anchors == kept


# -- the pool -------------------------------------------------------------


def test_a_row_about_a_held_dream_cannot_touch_it(tmp_path):
    tree = model_plan(tmp_path / "tree")
    held = Plan.load(tree).dreams
    forged = {**judged_row("d1", "set-aside"), "reason": "A model changed its mind."}
    llm = FakeLLM(
        [
            {"dreams": [dream_row(word="paint")]},
            {"dreams": [forged, judged_row("d3")]},
            {"proposals": [proposal_row("d3")]},
        ]
    )
    assert pipeline.dream_round(job_for(), tree, llm).ok
    assert Plan.load(tree).dreams[:2] == held


def test_a_clean_round_has_nothing_to_say_about_the_dreams_already_held(tmp_path):
    tree, job = model_plan(tmp_path / "tree"), job_for()
    assert pipeline.dream_round(job, tree, FakeLLM(round_of(dream_row(word="paint")))).ok
    assert [line for line in job.lines if "left out" in line] == []


def test_settling_a_round_removes_only_what_the_round_added(tmp_path):
    plan = Plan.load(model_plan(tmp_path / "tree"))
    risky = plan.topics[0].model_copy(update={"risks": [plan.dreams[0].what_if]})
    copied = plan.revised(topics=[risky, *plan.topics[1:]])
    settled, notes = dreaming.settle(copied, copied)
    assert (settled.dreams, notes) == (plan.dreams, [])


def test_two_rows_for_one_dream_are_read_as_the_first(tmp_path):
    tree = model_plan(tmp_path / "tree")
    rows = [judged_row("d3"), {**judged_row("d3", "set-aside"), "reason": "The second word."}]
    llm = FakeLLM([{"dreams": [dream_row(word="paint")]}, {"dreams": rows}, {"proposals": [proposal_row("d3")]}])
    assert pipeline.dream_round(job_for(), tree, llm).ok
    assert (Plan.load(tree).dreams[2].verdict, Plan.load(tree).dreams[2].reason) == ("proposed", "d3 decided.")


def test_a_section_reads_d9_before_d10(tmp_path):
    tree = model_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    numbered = [plan.dreams[1].model_copy(update={"id": i, "title": f"Dream {i}"}) for i in ("d10", "d9")]
    text = render.render(plan.revised(dreams=numbered))[render.DREAMS_FILE]
    assert text.index("(d9)") < text.index("(d10)")


def test_a_duplicate_of_a_held_dream_merges_the_new_one_and_leaves_the_old(tmp_path):
    tree = model_plan(tmp_path / "tree")
    held = Plan.load(tree).dreams
    llm = FakeLLM([{"dreams": [dream_row(word="paint")]}, {"dreams": [judged_row("d3", duplicate_of="d1")]}])
    assert pipeline.dream_round(job_for(), tree, llm).ok
    assert Plan.load(tree).dreams == held


def test_a_proposal_for_a_held_dream_stops_the_round_and_changes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    answers = round_of(dream_row(word="paint"))
    answers[-1] = {"proposals": [proposal_row("d1")]}
    with pytest.raises(pipeline.PlanRefused, match="nothing was changed.*'d1' is not on the shortlist"):
        pipeline.dream_round(job_for(), tree, FakeLLM(answers))
    assert snapshot(tree) == before


def test_ids_carry_on_past_a_drop_and_a_promotion(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert pipeline.drop(job_for(), tree, "d2", "No shelf.").ok
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    assert pipeline.dream_round(job_for(), tree, FakeLLM(round_of(dream_row(word="paint")))).ok
    assert [(d.id, d.verdict) for d in Plan.load(tree).dreams] == [
        ("d1", "promoted"),
        ("d2", "dropped"),
        ("d3", "proposed"),
    ]


@pytest.mark.parametrize("settle", ["drop", "keep"], ids=["dropped", "set-aside"])
@pytest.mark.parametrize(
    "respelt",
    [
        {"what_if": "the library lent bread as well as saws"},
        {"what_if": "What if the library lent bread as well as saws?"},
        {"what_if": "THE LIBRARY LENT BREAD, AS WELL AS SAWS"},
        {"title": "bread too!"},
    ],
    ids=["same", "opening-and-question-mark", "shouted", "title-only"],
)
def test_a_dream_ruled_out_is_not_offered_again_in_other_dress(tmp_path, settle, respelt):
    tree, job = model_plan(tmp_path / "tree"), job_for()
    if settle == "drop":
        assert pipeline.drop(job_for(), tree, "d2", "No shelf.").ok
    held = Plan.load(tree).dreams
    row = {**dream_row(word="paint"), **respelt}
    assert pipeline.dream_round(job, tree, FakeLLM([{"dreams": [row]}])).ok
    assert Plan.load(tree).dreams == held
    assert any("left out d3: it repeats d2" in line for line in job.lines)


def test_a_later_round_proposes_its_own_few_and_leaves_the_earlier_ones_alone(tmp_path):
    tree = model_plan(tmp_path / "tree")
    held = Plan.load(tree).dreams
    rows = [dream_row(word=word) for word in ("paint", "ladders", "kayaks", "tents", "tables")]
    answers = round_of(*rows, proposed=5)
    assert pipeline.dream_round(job_for(), tree, FakeLLM(answers)).ok
    dreams = Plan.load(tree).dreams
    assert dreams[:2] == held
    assert [d.id for d in dreams[2:] if d.verdict == "proposed"] == ["d3", "d4", "d5"]
    assert [d.reason.endswith(propose.PASSED_OVER) for d in dreams[5:]] == [True, True]


# -- what each pass may see and write -------------------------------------


def judged_pool(tree: Path) -> FakeLLM:
    llm = FakeLLM(round_of(dream_row(word="paint")))
    assert pipeline.dream_round(job_for(), tree, llm).ok
    return llm


def test_collect_never_sees_what_evaluate_or_propose_said(tmp_path):
    llm = judged_pool(model_plan(tmp_path / "tree"))
    collect_call = llm.calls[0]
    assert collect_call["label"] == "collect" and "Seeds too" in collect_call["user"]
    for word in ("decided", "if_adopted", "changes the first step", '"verdict"', '"pull"', '"reason"'):
        assert word not in collect_call["user"]


def test_evaluate_judges_against_the_plan_and_its_constraints(tmp_path):
    scope = {**GOOD["scope"], "constraints": ["Volunteers only."]}
    tree = model_plan(tmp_path / "tree", scope=scope)
    evaluate_call = judged_pool(tree).calls[1]
    assert evaluate_call["label"] == "evaluate"
    for word in ("Volunteers only.", "Decide.", '"risks"', '"unknowns"', '"decisions"', '"slug": "lending"'):
        assert word in evaluate_call["user"]


def test_propose_sees_only_the_shortlist(tmp_path):
    tree = model_plan(tmp_path / "tree")
    rows = [dream_row(word="paint"), dream_row(word="ladders")]
    llm = FakeLLM(round_of(*rows))
    assert pipeline.dream_round(job_for(), tree, llm).ok
    shown = llm.calls[2]["user"]
    assert "Paint too" in shown
    assert "Ladders too" not in shown and "Seeds too" not in shown and "Bread too" not in shown


@pytest.mark.parametrize("row", [{"id": "d9", "if_adopted": "x"}, {"id": "d2", "if_adopted": "x"}])
def test_propose_cannot_invent_a_dream_or_rescue_one(tmp_path, row):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script(propose={"proposals": [row]}))).ok
    plan = Plan.load(tree)
    assert plan.dreams == [] and "is not on the shortlist" in plan.dream_failure


# -- a failed dream pass --------------------------------------------------


def good_run_until(name: str) -> list[dict]:
    answers = script()
    return answers[: 5 + DREAM_PASS_NAMES.index(name)]


@pytest.mark.parametrize("name", DREAM_PASS_NAMES)
def test_a_failed_pass_lands_the_plan_a_plan_with_no_dreaming_would(tmp_path, monkeypatch, name):
    without, tree = tmp_path / "without", tmp_path / "tree"
    assert pipeline.run_plan(job_for(), without, FakeLLM(script()[:5]), dream=False).ok
    monkeypatch.setattr(cli, "build_llm", lambda **_: DiesAt(name, good_run_until(name)))
    result = invoke("plan", IDEA, "--yes", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert changed(snapshot(without), snapshot(tree)) == {"dreams.md", ".protopilot/plan.json"}
    assert Plan.load(tree).revised(dream_failure="") == Plan.load(without)
    assert f"the {name} pass stopped" in said(result) and "Dreaming failed, and this plan does not" in said(result)


@pytest.mark.parametrize("name", DREAM_PASS_NAMES)
def test_what_a_failed_pass_writes_is_true_and_its_retry_works(tmp_path, name):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, DiesAt(name, good_run_until(name))).ok
    text = page(tree)
    assert f"**Dreaming failed:** the {name} pass stopped" in text and "`proto dream` tries again." in text
    assert "Nothing here is researched." in text and "###" not in text
    assert pipeline.dream_round(job_for(), tree, FakeLLM(round_of(dream_row(), first=1))).ok
    assert "### Seeds too (d1)" in page(tree) and "Dreaming failed" not in page(tree)


@pytest.mark.parametrize("name", DREAM_PASS_NAMES)
def test_a_failed_round_exits_one_and_moves_no_byte(tmp_path, monkeypatch, name):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    answers = round_of(dream_row(word="paint"))[: DREAM_PASS_NAMES.index(name)]
    monkeypatch.setattr(cli, "build_llm", lambda **_: DiesAt(name, answers))
    result = invoke("dream", str(tree))
    assert result.exit_code == 1
    assert f"Dreaming failed, and nothing was changed: the {name} pass stopped" in said(result)
    assert "Rerun to try again." in said(result)
    assert snapshot(tree) == before


def test_the_console_reads_a_failed_dream_as_a_finished_plan(tmp_path):
    job = job_for()
    assert pipeline.run_plan(job, tmp_path / "tree", DiesAt("collect", good_run_until("collect"))).ok
    progress = fold(job.events)
    states = {state.name: state.state for state in progress.passes}
    assert progress.finished and progress.ok
    assert (states["collect"], states["render"]) == (FAILED, DONE)


# -- the cap --------------------------------------------------------------


def over_by(extra: int, word: str = "a") -> dict:
    """A dream of exactly the cap in words, plus `extra`, each field at its budget."""
    fields = {name: " ".join([word] * most) for name, most in DREAM_FIELD_WORDS.items()}
    return {**dream_row(), **fields, "takes": " ".join(["w"] * (DREAM_FIELD_WORDS["takes"] + extra))}


def test_a_dream_at_the_cap_enters_and_one_word_past_it_is_left_out_with_its_count(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    rows = [over_by(0), {**over_by(1, "b"), "lens": "the-opposite"}]
    llm = FakeLLM(script(collect={"dreams": rows}, evaluate={"dreams": [judged_row("d1")]}))
    assert pipeline.run_plan(job, tree, llm).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]
    note = f"left out d2: it runs to {DREAM_WORD_CAP + 1} words, past the cap of {DREAM_WORD_CAP}"
    assert any(note in line for line in job.lines)


def test_han_text_past_the_cap_is_left_out_even_though_it_has_no_spaces(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    han = {**dream_row(), "takes": "夢" * (2 * DREAM_WORD_CAP)}
    llm = FakeLLM(script(collect={"dreams": [han, BREAD]}, evaluate={"dreams": [judged_row("d2")]}))
    llm.responses[-1] = {"proposals": [proposal_row("d2")]}
    assert pipeline.run_plan(job, tree, llm).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d2"]
    assert any("left out d1: it runs to" in line for line in job.lines)


def test_a_model_of_nothing_but_overlong_dreams_costs_the_extras_and_says_why(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    rows = [{**RAMBLING, "title": f"Rambling {n}", "what_if": f"case {n}"} for n in range(3)]
    llm = FakeLLM(script(collect={"dreams": rows})[:6])
    result = pipeline.run_plan(job, tree, llm)
    assert result.ok and [call["label"] for call in llm.calls][-1] == "collect"
    assert len([line for line in job.lines if "left out" in line and "past the cap" in line]) == 3
    assert "**Dreaming failed:** no dream came through it whole." in page(tree)
    assert "dreams_shaped" not in result.summary.split("No subject")[0]


def test_a_round_of_nothing_but_overlong_dreams_keeps_the_pool_and_makes_no_more_calls(tmp_path):
    tree, job = model_plan(tmp_path / "tree"), job_for()
    before = snapshot(tree)
    llm = FakeLLM([{"dreams": [RAMBLING]}])
    assert pipeline.dream_round(job, tree, llm).ok
    assert [call["label"] for call in llm.calls] == ["collect"]
    assert any("0 new dream(s) in a pool of 2" in line for line in job.lines)
    assert snapshot(tree) == before


# -- `dreams_apart` -------------------------------------------------------


def judged(plan: Plan, **fields: list[str]) -> verify.PlanVerdict:
    first = plan.topics[0].model_copy(update=fields)
    changed_plan = plan.revised(topics=[first, *plan.topics[1:]])
    return verify.verdict(changed_plan, render.render(changed_plan))


@pytest.mark.parametrize("index", [0, 1], ids=["proposed", "set-aside"])
@pytest.mark.parametrize("where", ["risks", "unknowns", "decisions"])
def test_a_dream_still_on_offer_is_caught_in_each_place_a_topic_speaks(tmp_path, index: int, where: str):
    plan = Plan.load(model_plan(tmp_path / "tree"))
    result = judged(plan, **{where: [f"Worth asking: {plan.dreams[index].what_if}."]})
    assert result.stage == "dreams_apart"
    assert f"topics/members.md repeats the what_if of dream {plan.dreams[index].id}" in result.failed[0].problems


def test_a_topics_opening_line_is_read_unless_a_person_moved_it(tmp_path):
    plan = Plan.load(model_plan(tmp_path / "tree"))
    first = plan.topics[0].model_copy(update={"why": f"What if {plan.dreams[1].what_if}"})
    copied = plan.revised(topics=[first, *plan.topics[1:]])
    assert verify.verdict(copied, render.render(copied)).stage == "dreams_apart"


def test_a_new_topics_name_on_another_page_is_no_copy_of_a_sibling(tmp_path):
    name = "Seeds for every member"
    rows = [{**dream_row(), "title": name}, {**BREAD, "takes": name}]
    tree = model_plan(tmp_path / "tree", collect={"dreams": rows})
    link = edge("seeds_every_member", "members")
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(link)])).ok
    assert name in page(tree, "topics/members.md")
    assert verify.verdict(Plan.load(tree), render.read(tree)).ok


@pytest.mark.parametrize(
    ("line", "copy"),
    [
        ("a b c d e f", True),
        ("a b X d e f", True),
        ("a b X d Y f", False),
        ("a b c d e", True),
        ("a b c d", False),
        ("a b c X d e f", True),
        ("a b c X Y d e f", False),
        ("f e d c b a", False),
    ],
    ids=["same", "one-changed", "two-changed", "one-gone", "two-gone", "one-added", "two-added", "reversed"],
)
def test_six_words_may_differ_by_one_and_no_more(line, copy):
    assert verify.copied("a b c d e f", line) is copy


def test_five_words_are_too_few_to_differ_by_any():
    assert verify.copied("a b c d e", "a b c d e")
    assert not verify.copied("a b c d e", "a b X d e")


def test_twelve_words_may_differ_by_two(tmp_path):
    words = "one two three four five six seven eight nine ten eleven twelve"
    assert verify.copied(words, "one two X four five six seven eight Y ten eleven twelve")
    assert not verify.copied(words, "one two X four five Z seven eight Y ten eleven twelve")


@pytest.mark.parametrize(
    "text",
    [
        "Members may stop coming once the first year ends.",
        "The library lends saws to members who have paid.",
        "As well as saws the shelf holds ladders.",
        "What if nobody turns up to run the shelf at the weekend?",
    ],
)
def test_everyday_text_beside_a_real_dream_stays_green(tmp_path, text):
    plan = Plan.load(model_plan(tmp_path / "tree"))
    assert judged(plan, risks=[text]).ok


# -- honesty --------------------------------------------------------------


def test_a_round_touches_only_the_dreams_page_and_plan_json(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    judged_pool(tree)
    assert changed(before, snapshot(tree)) == {"dreams.md", ".protopilot/plan.json"}


def test_a_drop_touches_only_the_dreams_page_and_plan_json(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    assert pipeline.drop(job_for(), tree, "d1", "No shelf.").ok
    assert changed(before, snapshot(tree)) == {"dreams.md", ".protopilot/plan.json"}


def test_nothing_a_dream_does_reaches_researched_sources_or_findings(tmp_path):
    tree = model_plan(tmp_path / "tree")
    sources = page(tree, "sources.md")
    judged_pool(tree)
    assert pipeline.drop(job_for(), tree, "d2", "No shelf.").ok
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    plan = Plan.load(tree)
    assert (plan.researched, plan.sources) == (False, [])
    assert [topic for topic in plan.topics if topic.findings] == []
    assert page(tree, "sources.md") == sources
    assert "Nothing here is researched." in page(tree)
    assert "**Not researched.**" in page(tree, "topics/seeds_too.md")


def test_a_dreams_sentence_is_not_in_the_green_line_when_no_dream_check_held(tmp_path):
    no_dreams = pipeline.run_plan(job_for(), tmp_path / "a", FakeLLM(script()[:5]), dream=False)
    failed = pipeline.run_plan(job_for(), tmp_path / "b", DiesAt("collect", good_run_until("collect")))
    assert "Dreams are guesses" not in no_dreams.summary and "Dreams are guesses" not in failed.summary


# -- the command line -----------------------------------------------------


def piped(*args: str, cwd: Path, timeout: float = 60) -> subprocess.CompletedProcess:
    argv = [sys.executable, "-m", "protopilot.cli", *args]
    return subprocess.run(argv, cwd=cwd, input=b"", capture_output=True, timeout=timeout, check=False)


@pytest.mark.parametrize(
    "args", [("dream", "--offline"), ("dream", "promote", "d1", "--offline"), ("dream", "drop", "d1", "--why", "No.")]
)
def test_no_dream_verb_waits_on_a_terminal(tmp_path, args):
    tree = offline_plan(tmp_path / "tree")
    done = piped(*args, cwd=tree)
    assert done.returncode == 0, done.stdout.decode()


def test_a_repeated_lens_is_one_lens_and_two_lenses_are_those_two(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    known = {dream.id for dream in Plan.load(tree).dreams}
    twice = ("--lens", "who-else", "--lens", "who-else")
    assert invoke("dream", str(tree), "--offline", *twice).exit_code == 0
    new = [dream for dream in Plan.load(tree).dreams if dream.id not in known]
    assert [dream.lens for dream in new] == ["who-else", "who-else"]
    known |= {dream.id for dream in new}
    both = ("--lens", "the-opposite", "--lens", "who-else")
    assert invoke("dream", str(tree), "--offline", *both).exit_code == 0
    new = [dream for dream in Plan.load(tree).dreams if dream.id not in known]
    assert [dream.lens for dream in new] == ["who-else", "who-else", "the-opposite", "the-opposite"]


def test_no_dream_then_a_round_starts_the_pool(tmp_path):
    tree = tmp_path / "tree"
    assert invoke("plan", IDEA, "--offline", "--yes", "--no-dream", "--dir", str(tree)).exit_code == 0
    assert Plan.load(tree).dreams == []
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    assert len(Plan.load(tree).dreams) == 12


@pytest.mark.parametrize("verb", [("promote", "d1", "--offline"), ("drop", "d1", "--why", "No.")])
def test_a_verb_finds_the_plan_by_dir_or_by_the_current_directory(tmp_path, monkeypatch, verb):
    by_dir, by_cwd = offline_plan(tmp_path / "a"), offline_plan(tmp_path / "b")
    assert invoke("dream", *verb, "--dir", str(by_dir)).exit_code == 0
    monkeypatch.chdir(by_cwd)
    assert invoke("dream", *verb).exit_code == 0
    assert Plan.load(by_dir) == Plan.load(by_cwd)


def test_a_tree_proto_new_made_is_refused_and_left_alone(tmp_path):
    tree = tmp_path / "app"
    (tree / ".protopilot").mkdir(parents=True)
    (tree / ".protopilot" / "spec.json").write_text("{}", encoding="utf-8")
    before = snapshot(tree)
    for args in (["dream", str(tree), "--offline"], ["dream", "drop", "d1", "--why", "No.", "--dir", str(tree)]):
        result = invoke(*args)
        assert result.exit_code == 1 and "holds no plan" in said(result)
    assert snapshot(tree) == before


def test_a_directory_that_is_not_there_is_refused_and_not_made(tmp_path):
    tree = tmp_path / "nowhere"
    result = invoke("dream", str(tree), "--offline")
    assert result.exit_code == 1 and "holds no plan" in said(result)
    assert not tree.exists()


def test_a_symlinked_page_is_refused_and_never_written_through(tmp_path):
    tree, mine = offline_plan(tmp_path / "tree"), tmp_path / "mine.md"
    mine.write_text("mine", encoding="utf-8")
    (tree / "dreams.md").unlink()
    (tree / "dreams.md").symlink_to(mine)
    result = invoke("dream", str(tree), "--offline")
    assert result.exit_code == 1 and "a page needs this name" in said(result)
    assert mine.read_text(encoding="utf-8") == "mine" and (tree / "dreams.md").is_symlink()


def test_a_reason_cannot_break_out_of_its_line_or_hide_the_page_after_it(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert (
        invoke("dream", "drop", "d1", "--why", "<!-- hidden\n\n## Findings\n- planted", "--dir", str(tree)).exit_code
        == 0
    )
    text = page(tree)
    assert "<!-- hidden" not in text and "\n## Findings" not in text
    assert "Verdict: dropped. &lt;!-- hidden ## Findings - planted" in text


def test_a_backend_that_cannot_be_built_is_a_sentence_and_drop_never_asks_for_one(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")

    def refuse(**_: object):
        raise LLMError("No API key.")

    monkeypatch.setattr(cli, "build_llm", refuse)
    for args in (["dream", str(tree)], ["dream", "promote", "d1", "--dir", str(tree)]):
        result = invoke(*args)
        assert result.exit_code == 1 and "No API key." in said(result)
    assert invoke("dream", "drop", "d1", "--why", "No.", "--dir", str(tree)).exit_code == 0


def test_the_offline_backend_is_the_offline_flag(tmp_path):
    flag, named = offline_plan(tmp_path / "a"), offline_plan(tmp_path / "b")
    assert invoke("dream", str(flag), "--offline").exit_code == 0
    assert invoke("dream", str(named), "--backend", "offline").exit_code == 0
    assert Plan.load(flag) == Plan.load(named)


# -- offline, byte for byte -----------------------------------------------


def whole_life(tree: Path, seed: str) -> dict[str, bytes]:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    steps = (
        ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)],
        ["dream", str(tree), "--offline"],
        ["dream", "promote", "d2", "--offline", "--dir", str(tree)],
        ["dream", "drop", "d3", "--why", "No shelf.", "--dir", str(tree)],
    )
    for args in steps:
        argv = [sys.executable, "-m", "protopilot.cli", *args]
        done = subprocess.run(argv, input=b"", capture_output=True, env=env, timeout=60, check=False)
        assert done.returncode == 0, done.stdout.decode()
    return snapshot(tree)


def test_a_whole_offline_life_is_byte_identical_under_any_hash_seed(tmp_path):
    assert whole_life(tmp_path / "t", "1") == whole_life(tmp_path / "t2", "2")


def test_dreaming_offline_changes_only_the_dreams_page_and_plan_jsons_dreams(tmp_path):
    with_dreams, without = offline_plan(tmp_path / "a"), tmp_path / "b"
    assert invoke("plan", IDEA, "--offline", "--yes", "--no-dream", "--dir", str(without)).exit_code == 0
    assert changed(snapshot(without), snapshot(with_dreams)) == {"dreams.md", ".protopilot/plan.json"}
    assert Plan.load(with_dreams).revised(dreams=[]) == Plan.load(without)


# -- the defects a review found: each named for its finding ----------------


def test_H1_a_bad_rating_from_evaluate_must_not_cost_the_plan(tmp_path):
    """One out-of-range rating destroys a whole `proto plan` run, after every paid pass."""
    tree = tmp_path / "tree"
    bad = {**judged_row("d1"), "pull": "huge"}
    result = pipeline.run_plan(job_for(), tree, FakeLLM(script(evaluate={"dreams": [bad, judged_row("d2")]})))
    assert result.ok and (tree / "PLAN.md").is_file()


def test_H2_a_lone_surrogate_in_a_dream_must_not_cost_the_plan(tmp_path):
    """`"\\ud800"` is valid JSON, and json.loads yields a lone surrogate."""
    tree = tmp_path / "tree"
    row = {**dream_row(), "title": "Seeds \ud800 too"}
    result = pipeline.run_plan(job_for(), tree, FakeLLM(script(collect={"dreams": [row]})))
    assert result.ok and (tree / "PLAN.md").is_file()


@pytest.mark.parametrize("blocker", ["symlink", "directory", "read-only"])
def test_H3_a_dream_verb_that_cannot_draw_must_leave_the_tree_as_it_was(tmp_path, blocker):
    """`_land` promises "Red, or raced, leaves the tree as it was"; a blocked page does not."""
    tree = model_plan(tmp_path / "tree")
    page = tree / "dreams.md"
    if blocker == "symlink":
        (tmp_path / "mine.md").write_text("mine", encoding="utf-8")
        page.unlink()
        page.symlink_to(tmp_path / "mine.md")
    elif blocker == "directory":
        page.unlink()
        page.mkdir()
    else:
        os.chmod(page, 0o444)
    before = snapshot(tree)
    with pytest.raises((pipeline.PlanRefused, OSError)):
        pipeline.drop(job_for(), tree, "d1", "No shelf.")
    assert snapshot(tree) == before


def test_H4_repair_during_a_promotion_must_not_remove_a_settled_edge(tmp_path):
    """promote.py: "what the plan had settled stays settled". Repair can delete a settled link."""
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree)
    links = [edge("members", "seeds_too"), edge("seeds_too", "lending")]
    gives_up_the_settled_link = repair_of([edge("money", "space", "informs"), *links], ["lending"])
    try:
        pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(*links), gives_up_the_settled_link, NO_REPAIR]))
    except pipeline.PlanRefused:
        pass  # refusing is a correct answer
    assert all(held in Plan.load(tree).edges for held in before.edges)


def test_M1_repair_during_a_promotion_must_not_add_links_between_settled_topics(tmp_path):
    """`repair.rejected` looks only at edges lost, so a repair can add anything."""
    tree = model_plan(tmp_path / "tree")
    loop = [edge("seeds_too", "members"), edge("members", "seeds_too")]
    extra = edge("tools", "money", "conflicts-with")
    mended = repair_of([*GOOD["connect"]["edges"], edge("seeds_too", "members"), extra], ["members"])
    try:
        pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(*loop), mended, NO_REPAIR]))
    except pipeline.PlanRefused:
        pass
    assert ("tools", "money") not in {(e.from_topic, e.to_topic) for e in Plan.load(tree).edges}


def test_M2_a_programmer_error_in_a_dream_pass_must_not_read_as_dreaming_failed(tmp_path, monkeypatch):
    """Should a bug be hidden? No."""

    def broken(*_args, **_kwargs):
        raise NameError("name 'parts' is not defined")

    monkeypatch.setattr(collect, "build", broken)
    monkeypatch.setattr(cli, "build_llm", lambda **_: FakeLLM(script()))
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--yes", "--dir", str(tmp_path / "tree")])
    assert result.exit_code != 0


def test_M3_a_plan_json_corrupted_during_a_promotion_is_a_lost_race_with_a_true_message(tmp_path):
    """`_land`'s race check calls `Plan.load` unguarded."""
    tree = model_plan(tmp_path / "tree")
    llm = During([answer()], "promote", lambda: plan_path(tree).write_text("{", encoding="utf-8"))
    with pytest.raises(pipeline.PlanRefused, match="changed while this ran"):
        pipeline.promote(job_for(), tree, "d1", llm)


def test_M4_a_round_that_adds_nothing_must_not_erase_the_note_or_claim_dreaming_never_ran(tmp_path):
    """`dream_round` clears `dream_failure` whatever the round produced."""
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script(collect={"nonsense": 1}))).ok
    rambling = {**dream_row(), "takes": " ".join(["word"] * (DREAM_WORD_CAP + 1))}
    assert pipeline.dream_round(job_for(), tree, FakeLLM([{"dreams": [rambling]}])).ok
    assert "dreaming has not run" not in (tree / "dreams.md").read_text(encoding="utf-8")


def test_M5_the_word_cap_must_not_be_beaten_by_joining_words_with_what_it_does_not_break_on(tmp_path):
    """model.py records that a model joined 28 words with hyphens; other joiners still work."""
    words = [f"w{n}" for n in range(60)]
    for joined in (",".join(words), ".".join(words), "‑".join(words), "−".join(words), "​".join(words)):
        assert dream_words(joined) > DREAM_WORD_CAP, repr(joined[:12])
    assert dream_words("🚲 " * 100) > DREAM_WORD_CAP


def test_M6_a_field_over_its_own_budget_must_be_left_out(tmp_path):
    """The per-field budget is enforced nowhere the API backend can reach."""
    tree = tmp_path / "tree"
    title = " ".join(["word"] * 30)
    assert pipeline.run_plan(
        job_for(), tree, FakeLLM(script(collect={"dreams": [{**dream_row(), "title": title}, BREAD]}))
    )
    assert all(dream_words(d.title) <= DREAM_FIELD_WORDS["title"] for d in Plan.load(tree).dreams)


def test_L1_one_blank_field_must_cost_one_dream_not_the_round(tmp_path):
    """collect.py says "one bad dream costs only itself", but a blank field costs the round."""
    tree = tmp_path / "tree"
    rows = [dream_row(), {**BREAD, "what_if": "What if"}]
    answers = script(collect={"dreams": rows}, evaluate={"dreams": [judged_row("d1")]})
    assert pipeline.run_plan(job_for(), tree, FakeLLM(answers)).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]


@pytest.mark.parametrize("rating", ["not judged", None])
def test_L2_a_model_must_not_give_a_rating_only_the_twin_may(tmp_path, rating):
    """`MODEL_RATINGS` excludes "not judged" but `_judged` never reads it."""
    tree = tmp_path / "tree"
    bad = {**judged_row("d1"), "pull": rating}
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script(evaluate={"dreams": [bad, judged_row("d2")]})))
    assert all(dream.pull in ("low", "medium", "high") for dream in Plan.load(tree).dreams)


def test_L3_the_schema_must_agree_with_dream_words_about_han(tmp_path):
    """`word_pattern`'s docstring says "as `dream_words` counts them". It does not for Han or kana."""
    assert dream_words("夢" * 100) == 50
    assert re.fullmatch(collect.word_pattern(DREAM_FIELD_WORDS["title"]), "夢" * 100) is None


def test_L4_the_green_lines_dream_sentence_must_claim_only_what_held(tmp_path):
    """With every dream settled, `dreams_apart` is NO_SUBJECT, yet the line says they stay apart."""
    tree = model_plan(tmp_path / "tree")
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    result = pipeline.promote(job_for(), tree, "d2", FakeLLM([answer()]))
    assert "dreams_apart" in result.named(verify.NO_SUBJECT)
    assert "stay apart" not in result.summary


@pytest.mark.parametrize("said", ["out of credit.", ""])
def test_L5_a_failure_sentence_must_read_as_one_sentence(tmp_path, said):
    """`f"...stopped: {said}."` doubles a period and leaves "stopped: ." on an empty error."""

    class Dies(FakeLLM):
        def structured(self, *, system, user, schema, label):
            if label == "collect":
                raise LLMError(said)
            return super().structured(system=system, user=user, schema=schema, label=label)

    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, Dies(script())).ok
    failure = Plan.load(tree).dream_failure
    assert not failure.endswith("..") and not failure.endswith(": .")


def test_L6_a_dream_merged_into_one_that_did_not_survive_must_not_vanish(tmp_path):
    """`evaluate.apply` merges d1 into d2, then `settle` removes d2, so neither lands."""
    tree = tmp_path / "tree"
    answers = script(evaluate={"dreams": [judged_row("d1", duplicate_of="d2")]})
    assert pipeline.run_plan(job_for(), tree, FakeLLM(answers)).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]


def test_L7_after_failure_must_not_promise_a_free_rerun_of_a_dream_verb(tmp_path):
    """`_plan_step` appends `after_failure`, written for `proto plan`, to dream verbs."""
    tree = model_plan(tmp_path / "tree")
    os.chmod(tree / "sources.md", 0o444)
    result = CliRunner().invoke(cli.main, ["dream", "drop", "d1", "--why", "No.", "--dir", str(tree)])
    assert result.exit_code == 1
    assert "no model call" not in " ".join(result.output.split())


def test_L8_llm_a_moved_pattern_must_not_overwrite_a_description(tmp_path):
    """py recomputes that for `proto new`)."""
    moved = _without_patterns({"type": "string", "description": "A slug.", "pattern": "^a$"})
    assert "A slug." in moved["description"] and "^a$" in moved["description"]
    assert _without_patterns({"const": {"pattern": "b"}}) == {"const": {"pattern": "b"}}


def test_R1_a_promotion_may_pass_the_outlines_eight_topics(tmp_path):
    """A person chose it, and four to eight is the outline's rule, not the plan's."""
    tree = tmp_path / "tree"
    names = list("abcdefgh")
    llm = FakeLLM(
        script(
            outline=outline_of(names),
            connect={"edges": []},
            consider=consider_of(names),
            start={"steps": [step("a")]},
            collect={"dreams": [dream_row(anchor="a")]},
            evaluate={"dreams": [judged_row("d1")]},
        )
    )
    job = job_for()
    assert pipeline.build(job, tree, pipeline.outlined(job, llm, pipeline.scoped(job, llm, "deep")), llm).ok
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer()])).ok
    assert len(Plan.load(tree).topics) == MAX_TOPICS + 1


@pytest.mark.parametrize(
    ("first", "label"),
    [("d1", "Dropped before: Too dear"), ("d2", "Set aside before: d2 decided.")],
    ids=["dropped", "set-aside"],
)
def test_R2_a_promoted_dream_labels_its_earlier_reason_as_earlier(tmp_path, first, label):
    """A dropped or set-aside dream's reason argued against it, so it must not read as why it was promoted."""
    tree = model_plan(tmp_path / "tree")
    assert pipeline.drop(job_for(), tree, "d1", "Too dear for a volunteer group").ok
    assert pipeline.promote(job_for(), tree, first, FakeLLM([answer()])).ok
    text = (tree / "dreams.md").read_text(encoding="utf-8")
    assert "- Verdict: promoted\n" in text and label in text


def test_R3_only_why_is_exempt_on_a_dropped_dream(tmp_path):
    """What a person rejected must not read as a risk; only the person's own reason may repeat a topic."""
    tree = model_plan(tmp_path / "tree")
    assert pipeline.drop(job_for(), tree, "d2", "No shelf.").ok
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="dreams_apart"):
        pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(risks=["the library lent bread as well as saws"])]))
    assert snapshot(tree) == before


def test_R4_an_ordinary_phrase_in_a_dreams_takes_must_not_block_a_promotion(tmp_path):
    """The fuzzy rule is sound; the false reds come from MIN_LEAK_CHARS on `takes`."""
    row = {**dream_row(), "takes": "A part-time coordinator."}
    tree = model_plan(tmp_path / "tree", collect={"dreams": [row, BREAD]})
    risk = "Everything leans on a part time coordinator who may leave."
    assert pipeline.promote(job_for(), tree, "d2", FakeLLM([answer(risks=[risk])])).ok


# -- what the fixes above must also hold ----------------------------------


def test_a_blocked_page_is_refused_before_any_model_call(tmp_path):
    tree = model_plan(tmp_path / "tree")
    os.chmod(tree / "sources.md", 0o444)
    llm = FakeLLM([])
    with pytest.raises(pipeline.PlanRefused, match="Nothing was changed, because a page needs this name"):
        pipeline.dream_round(job_for(), tree, llm)
    assert llm.calls == []


def test_a_write_that_dies_after_the_save_puts_the_tree_back(tmp_path, monkeypatch):
    tree, real = model_plan(tmp_path / "tree"), Path.write_text
    before = snapshot(tree)
    armed = [True]

    def dies(self, text, *args, **kwargs):
        if self.name == "sources.md" and armed.pop() if armed else False:
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.drop(job_for(), tree, "d1", "No.")
    assert snapshot(tree) == before


def test_a_write_that_cannot_be_put_back_says_so(tmp_path, monkeypatch):
    tree, real = model_plan(tmp_path / "tree"), Path.write_text

    def dies(self, text, *args, **kwargs):
        if self.name == "sources.md":
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)
    with pytest.raises(pipeline.PlanRefused, match="may disagree, and a rerun may repeat it"):
        pipeline.drop(job_for(), tree, "d1", "No.")


def test_a_bug_in_a_dream_verb_says_nothing_of_a_free_rerun(tmp_path, monkeypatch):
    tree = model_plan(tmp_path / "tree")

    def broken(*_args, **_kwargs):
        raise NameError("a bug")

    monkeypatch.setattr(dreaming, "dropped", broken)
    result = invoke("dream", "drop", "d1", "--why", "No.", "--dir", str(tree))
    assert result.exit_code == 1 and "NameError: a bug" in result.output
    assert "before rerunning" in said(result) and "no model call" not in said(result)


def test_a_bug_in_a_repair_surfaces_rather_than_reading_as_a_failed_repair(tmp_path, monkeypatch):
    def broken(*_args, **_kwargs):
        raise NameError("a bug")

    monkeypatch.setattr(repair, "failure", broken)
    with pytest.raises(NameError):
        pipeline.run_plan(job_for(), tmp_path / "tree", FakeLLM(script(start={"steps": [step("lending")]})))


def test_a_bug_in_apply_is_not_labelled_as_a_models_output(tmp_path, monkeypatch):
    def broken(_plan, _data):
        raise KeyError("a bug")

    monkeypatch.setattr(propose, "apply", broken)
    with pytest.raises(KeyError):
        pipeline.run_plan(job_for(), tmp_path / "tree", FakeLLM(script()))


@pytest.mark.parametrize(
    ("value", "said_"),
    [([], "an object was wanted"), ({"dreams": "x"}, "must be a list"), ({"dreams": [{"id": 1}]}, "missing field")],
    ids=["not-an-object", "not-a-list", "row-short"],
)
def test_a_response_of_the_wrong_shape_is_named_as_that(value, said_):
    assert said_ in passes.misshapen(evaluate.schema(Plan.model_validate(PLAN_WITH_A_DREAM)), value)


def test_a_repair_during_a_promotion_is_told_what_is_settled(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM([answer(edge("members", "seeds_too")), NO_REPAIR])
    with pytest.raises(pipeline.PlanRefused):
        pipeline.promote(job_for(), tree, "d1", llm)
    assert repair.SETTLED_RULE in llm.calls[-1]["user"]


def test_a_repair_may_mend_a_promotion_at_a_new_link_and_keep_every_settled_step(tmp_path):
    tree = model_plan(tmp_path / "tree")
    links = [edge("members", "seeds_too"), edge("seeds_too", "lending")]
    mended = repair_of([*GOOD["connect"]["edges"], links[1]], ["members"])
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(*links), mended])).ok
    assert edge("members", "seeds_too") not in [e.model_dump() for e in Plan.load(tree).edges]


def test_a_repair_that_drops_a_settled_step_is_thrown_away(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    gone = repair_of([*GOOD["connect"]["edges"], edge("members", "seeds_too")], ["seeds_too"])
    with pytest.raises(pipeline.PlanRefused, match="changed settled steps"):
        pipeline.promote(job_for(), tree, "d1", FakeLLM([answer(edge("members", "seeds_too")), gone, NO_REPAIR]))
    assert snapshot(tree) == before


def test_an_empty_round_after_no_dream_says_a_round_ran(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script()[:5]), dream=False).ok
    assert pipeline.dream_round(job_for(), tree, FakeLLM([{"dreams": [RAMBLING]}])).ok
    assert "a round ran" in page(tree) and "dreaming has not run" not in page(tree)


def test_an_empty_round_keeps_the_note_it_found(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script(collect={"nonsense": 1}))).ok
    said_before = Plan.load(tree).dream_failure
    assert pipeline.dream_round(job_for(), tree, FakeLLM([{"dreams": [RAMBLING]}])).ok
    assert Plan.load(tree).dream_failure == said_before


@pytest.mark.parametrize(
    ("text", "words"),
    [("don't stop", 2), ("3.5 tools", 3), ("a" * 25, 2), ("\U0001f6b2\U0001f6b2", 2), ("a, b; c: d", 4)],
    ids=["apostrophe", "decimal", "long-run", "emoji", "punctuation"],
)
def test_the_exact_count_of_words(text, words):
    assert dream_words(text) == words


def test_an_ordinary_sentence_with_punctuation_fits_the_pattern():
    sentence = "the town's depot, with repair bays: open daily."
    assert re.fullmatch(collect.word_pattern(DREAM_FIELD_WORDS["what_if"]), sentence)


def test_the_pattern_refuses_every_joiner_the_count_refuses():
    for join in (",", ".", "\u2011", "\u2212", "\u200b", "\u00b7"):
        assert not re.fullmatch(collect.word_pattern(5), join.join(["w"] * 30)), repr(join)


def test_a_lone_surrogate_in_what_evaluate_says_costs_the_round_and_not_the_plan(tmp_path):
    tree = tmp_path / "tree"
    bad = {**judged_row("d1"), "reason": "bad \ud800 reason"}
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script(evaluate={"dreams": [bad, judged_row("d2")]}))).ok
    assert Plan.load(tree).dream_failure
