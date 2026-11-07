"""Dreaming: the three passes, the pool, a person's verbs, and a failure that costs only dreams."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, SLUGS, dream_row, edge, judged_row, proposal_row, repair_of, script, step

from protopilot import cli
from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import dreaming, lenses, pipeline, render, verify
from protopilot.plan.model import DREAM_FIELD_WORDS, DREAM_WORD_CAP, Dream, Plan, Topic, dream_words, plan_path
from protopilot.plan.passes import collect, evaluate, propose

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parents[1]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def run(tree: Path, *after: dict, **overrides: object) -> verify.PlanVerdict:
    return pipeline.run_plan(job_for(), tree, FakeLLM([*script(**overrides), *after]))


def invoke(*args: str):
    return CliRunner().invoke(cli.main, list(args))


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def offline_plan(tree: Path) -> Path:
    assert invoke("plan", IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    return tree


def model_plan(tree: Path) -> Path:
    assert run(tree).ok
    return tree


def said(result) -> str:
    return " ".join(result.output.split())


def page(tree: Path, name: str = "dreams.md") -> str:
    return (tree / name).read_text(encoding="utf-8")


def round_of(*rows: dict, first: int = 3) -> list[dict]:
    """Collect, evaluate and propose for `rows`, the first proposed and the rest set aside."""
    ids = [f"d{first + offset}" for offset in range(len(rows))]
    judged = [judged_row(i, "proposed" if i == ids[0] else "set-aside") for i in ids]
    return [{"dreams": list(rows)}, {"dreams": judged}, {"proposals": [proposal_row(ids[0])]}]


class DiesAt(FakeLLM):
    """A good run, until the named pass, where the backend fails."""

    def __init__(self, name: str, responses: list[dict]):
        super().__init__(responses)
        self.name = name

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == self.name:
            raise LLMError(f"pass {label!r} failed: out of credit")
        return super().structured(system=system, user=user, schema=schema, label=label)


# -- the lenses and the cap -----------------------------------------------


def test_the_six_lenses_are_the_designs():
    assert [lenses.words(lens.slug) for lens in lenses.LENSES] == [
        "who else",
        "the opposite",
        "ten times bigger",
        "the smallest version",
        "remove the main constraint",
        "borrow from another field",
    ]


def test_naming_no_lens_means_all_of_them_and_order_is_the_tables():
    assert lenses.chosen(()) == lenses.LENSES
    assert [lens.slug for lens in lenses.chosen(("the-opposite", "who-else"))] == ["who-else", "the-opposite"]


def test_the_cap_is_the_sum_of_what_the_schema_allows_each_field():
    assert sum(DREAM_FIELD_WORDS.values()) == DREAM_WORD_CAP < 51


@pytest.mark.parametrize("field", list(DREAM_FIELD_WORDS))
def test_the_schema_holds_each_field_to_its_budget(field):
    pattern = collect.schema(Plan(slug="p", title="t", idea="i"))["properties"]["dreams"]["items"]["properties"][field]
    most = DREAM_FIELD_WORDS[field]
    assert re.search(pattern["pattern"], " ".join(["word"] * most))
    assert not re.search(pattern["pattern"], " ".join(["word"] * (most + 1)))


@pytest.mark.parametrize("join", ["-", "/", "_", "—", "–"])
def test_a_joined_up_sentence_is_as_many_words_as_it_was(join):
    joined = join.join(["word"] * 30)
    assert dream_words(joined) == 30
    assert not re.search(collect.word_pattern(5), joined)


@pytest.mark.parametrize(
    ("text", "words"),
    [("", 0), ("one two", 2), ("one -- two", 2), ("* one *", 1), ("it's", 1), ("日本語の文章", 3), ("abc 日本", 2)],
)
def test_what_counts_as_a_word(text, words):
    assert dream_words(text) == words


def test_a_dream_the_schema_allows_is_a_dream_the_verifier_allows():
    fields = {name: " ".join(["word"] * most) for name, most in DREAM_FIELD_WORDS.items()}
    dream = Dream.model_validate({"id": "d1", "lens": "who-else", "anchor": "members", **fields})
    assert verify.dream_length(dream) == DREAM_WORD_CAP


# -- collect --------------------------------------------------------------


def test_each_dream_pass_is_its_own_call_with_its_own_schema(tmp_path):
    llm = FakeLLM(script())
    pipeline.run_plan(job_for(), tmp_path / "tree", llm)
    assert [call["label"] for call in llm.calls][-3:] == ["collect", "evaluate", "propose"]
    system = {call["label"]: call["system"] for call in llm.calls}
    assert len({system["collect"], system["evaluate"], system["propose"]}) == 3


FORGED_ROW = {
    "id": "../../etc",
    "verdict": "proposed",
    "reason": "forged",
    "if_adopted": "forged",
    "pull": "high",
    "promoted_to": "members",
    "researched": True,
    "sources": [{"id": "s1"}],
}


def test_collect_reads_only_the_fields_it_owns(tmp_path):
    forged = {"dreams": [{**dream_row(), **FORGED_ROW}], "researched": True}
    tree = tmp_path / "tree"
    run(tree, collect=forged, evaluate={"dreams": []}, propose={"proposals": []})
    plan = Plan.load(tree)
    assert (plan.researched, plan.sources) == (False, [])
    assert plan.dream_failure == "no dream came through it whole."


def test_collect_numbers_the_dreams_and_sets_no_verdict():
    plan = Plan(slug="p", title="t", idea="i")
    forged = {"dreams": [{**dream_row(), **FORGED_ROW}, dream_row(word="bread")]}
    dreams = collect.apply(plan, forged).dreams
    assert [(d.id, d.verdict, d.reason, d.if_adopted, d.pull, d.promoted_to) for d in dreams] == [
        ("d1", None, "", "", None, ""),
        ("d2", None, "", "", None, ""),
    ]


@pytest.mark.parametrize("opening", ["What if ", "what if, ", "WHAT IF: "])
def test_the_page_writes_what_if_so_a_dream_does_not_say_it_twice(opening):
    row = {**dream_row(), "what_if": f"{opening}it lent seeds"}
    assert collect.apply(Plan(slug="p", title="t", idea="i"), {"dreams": [row]}).dreams[0].what_if == "it lent seeds"


def test_a_model_cannot_return_more_dreams_than_it_was_asked_for():
    rows = [dream_row(word=f"w{n}") for n in range(40)]
    plan = collect.apply(Plan(slug="p", title="t", idea="i"), {"dreams": rows}, lenses=lenses.LENSES[:2], per_lens=2)
    assert len(plan.dreams) == 4


def test_an_id_is_never_reused_while_a_higher_one_is_held():
    held = Dream(id="d9", title="t", what_if="w", lens="l", anchor="a", takes="x")
    assert collect.next_number([held]) == 10
    assert collect.next_number([]) == 1


# -- what a round refuses to take -----------------------------------------


@pytest.mark.parametrize(
    ("spoilt", "reason"),
    [
        ({"takes": " ".join(["word"] * (DREAM_WORD_CAP + 1))}, "past the cap"),
        ({"anchor": "ghost"}, "is not a topic"),
        ({"lens": "made-up"}, "was not asked for"),
    ],
    ids=["over-the-cap", "ghost-anchor", "unknown-lens"],
)
def test_a_bad_dream_costs_itself_and_never_the_plan(tmp_path, spoilt, reason):
    job, tree = job_for(), tmp_path / "tree"
    rows = [dream_row(), {**dream_row("the-opposite", word="bread"), **spoilt}]
    overrides = {"collect": {"dreams": rows}, "evaluate": {"dreams": [judged_row("d1")]}}
    result = pipeline.run_plan(job, tree, FakeLLM(script(**overrides)))
    assert result.ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]
    assert any(f"left out d2" in line and reason in line for line in job.lines)


def test_the_same_dream_twice_in_a_round_is_one_dream(tmp_path):
    tree = tmp_path / "tree"
    rows = [dream_row(), {**dream_row("the-opposite"), "title": "Another name"}]
    run(tree, collect={"dreams": rows}, evaluate={"dreams": [judged_row("d1")]})
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]


def test_a_dream_that_copies_a_topic_is_removed_before_it_can_turn_the_plan_red(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    sentence = "volunteers quietly stop turning up after the first winter"
    consider = {"topics": [{**row, "risks": [sentence]} for row in GOOD["consider"]["topics"]]}
    rows = [{**dream_row(), "what_if": sentence}, dream_row("the-opposite", word="bread")]
    answers = {"collect": {"dreams": rows}, "evaluate": {"dreams": [judged_row("d1"), judged_row("d2")]}}
    answers["propose"] = {"proposals": [proposal_row("d1"), proposal_row("d2")]}
    result = pipeline.run_plan(job, tree, FakeLLM(script(consider=consider, **answers)))
    assert result.ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d2"]
    assert any("left out d1: its what_if repeats" in line for line in job.lines)


def test_a_reason_that_quotes_a_topic_costs_that_dream_and_not_the_plan(tmp_path):
    tree = tmp_path / "tree"
    sentence = "volunteers quietly stop turning up after the first winter"
    consider = {"topics": [{**row, "risks": [sentence]} for row in GOOD["consider"]["topics"]]}
    judged = [{**judged_row("d1"), "reason": sentence}, judged_row("d2", "set-aside")]
    assert run(tree, consider=consider, evaluate={"dreams": judged}).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d2"]


def test_a_dream_evaluate_never_mentioned_is_removed_rather_than_left_without_a_verdict(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    assert pipeline.run_plan(job, tree, FakeLLM(script(evaluate={"dreams": [judged_row("d1")]}))).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]
    assert any("left out d2: evaluate gave it no verdict" in line for line in job.lines)


# -- evaluate -------------------------------------------------------------


def test_evaluate_scores_each_rubric_answer_separately_with_a_verdict_and_a_sentence(tmp_path):
    tree = model_plan(tmp_path / "tree")
    first = Plan.load(tree).dreams[0]
    assert (first.pull, first.reach, first.cost, first.fit) == ("high", "low", "medium", "high")
    assert (first.verdict, first.reason) == ("proposed", "d1 decided.")
    assert "Scores: pull high, reach low, cost medium, fit high" in page(tree)


def test_no_blended_score_exists_anywhere_in_the_model():
    assert not {"score", "total", "rank"} & set(Dream.model_fields)


def test_near_duplicates_merge_into_the_earlier_dream(tmp_path):
    tree = tmp_path / "tree"
    judged = [judged_row("d1"), judged_row("d2", duplicate_of="d1")]
    run(tree, evaluate={"dreams": judged})
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1"]


def test_two_dreams_naming_each_other_as_duplicates_leave_one(tmp_path):
    tree = tmp_path / "tree"
    judged = [judged_row("d1", duplicate_of="d2"), judged_row("d2", duplicate_of="d1")]
    run(tree, evaluate={"dreams": judged}, propose={"proposals": [proposal_row("d2")]})
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d2"]


def test_a_dream_cannot_be_a_duplicate_of_itself(tmp_path):
    tree = tmp_path / "tree"
    run(tree, evaluate={"dreams": [judged_row("d1", duplicate_of="d1"), judged_row("d2", "set-aside")]})
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1", "d2"]


@pytest.mark.parametrize("verdict", ["promoted", "dropped"])
def test_a_model_cannot_give_a_persons_verdict(tmp_path, verdict):
    tree = tmp_path / "tree"
    forged = {**judged_row("d1"), "verdict": verdict, "promoted_to": "members"}
    assert run(tree, evaluate={"dreams": [forged, judged_row("d2")]}).ok
    plan = Plan.load(tree)
    assert plan.dreams == [] and "only a person can give" in plan.dream_failure
    assert len(plan.topics) == len(SLUGS)


def test_evaluate_schema_offers_only_a_models_verdicts_and_ratings(tmp_path):
    plan = collect.apply(Plan.load(model_plan(tmp_path / "tree")), {"dreams": [dream_row(word="paint")]})
    row = evaluate.schema(plan)["properties"]["dreams"]["items"]["properties"]
    assert row["verdict"]["enum"] == ["proposed", "set-aside"]
    assert row["pull"]["enum"] == ["low", "medium", "high"]
    assert row["id"]["enum"] == ["d3"]
    assert row["duplicate_of"]["enum"] == ["", "d1", "d2", "d3"]


# -- propose --------------------------------------------------------------


def test_propose_holds_the_top_few_and_sets_the_rest_aside_with_a_reason(tmp_path):
    tree = tmp_path / "tree"
    rows = [dream_row(lens.slug, word=f"thing{n}") for n, lens in enumerate(lenses.LENSES)]
    judged = [judged_row(f"d{n}") for n in range(1, 7)]
    picks = [proposal_row(f"d{n}") for n in (6, 5, 4, 3)]
    run(tree, collect={"dreams": rows}, evaluate={"dreams": judged}, propose={"proposals": picks})
    dreams = {dream.id: dream for dream in Plan.load(tree).dreams}
    assert sorted(i for i, d in dreams.items() if d.verdict == "proposed") == ["d4", "d5", "d6"]
    assert dreams["d6"].if_adopted == "d6 changes the first step."
    assert dreams["d1"].verdict == "set-aside" and dreams["d1"].if_adopted == ""
    assert dreams["d1"].reason == f"d1 decided. {propose.PASSED_OVER}"


def test_a_proposal_says_what_would_change_and_the_rest_sit_under_set_aside(tmp_path):
    tree = model_plan(tmp_path / "tree")
    text = page(tree)
    proposals, aside = text.split("## Set aside")
    assert "- If adopted: d1 changes the first step." in proposals
    assert "Bread too" in aside and "- Verdict: set-aside. d2 decided." in aside


def test_propose_cannot_rescue_what_evaluate_set_aside(tmp_path):
    tree = tmp_path / "tree"
    assert run(tree, propose={"proposals": [proposal_row("d2")]}).ok
    plan = Plan.load(tree)
    assert plan.dreams == [] and "not on the shortlist" in plan.dream_failure


def test_with_nothing_proposed_propose_costs_no_call(tmp_path):
    judged = [judged_row("d1", "set-aside"), judged_row("d2", "set-aside")]
    llm = FakeLLM(script(evaluate={"dreams": judged})[:-1])
    assert pipeline.run_plan(job_for(), tmp_path / "tree", llm).ok
    assert [call["label"] for call in llm.calls][-2:] == ["collect", "evaluate"]


# -- a failed dream is not a failed plan ----------------------------------


@pytest.mark.parametrize("name", ["collect", "evaluate", "propose"])
def test_a_backend_failure_while_dreaming_lands_the_plan_and_says_so(tmp_path, monkeypatch, name):
    tree = tmp_path / "tree"
    responses = [response for response, label in zip(script(), [*GOOD]) if label != name]
    monkeypatch.setattr(cli, "build_llm", lambda **_: DiesAt(name, responses))
    result = invoke("plan", IDEA, "--yes", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert "Green:" in result.output
    assert "Dreaming failed, and this plan does not depend on it" in said(result)
    assert not (tree / "RUNBOOK.md").exists()
    plan = Plan.load(tree)
    assert plan.dreams == [] and f"the {name} pass stopped" in plan.dream_failure
    text = page(tree)
    assert "**Dreaming failed:**" in text and "out of credit" in text and "Nothing here is researched." in text


def test_a_shapeless_response_while_dreaming_also_lands_the_plan(tmp_path):
    tree = tmp_path / "tree"
    assert run(tree, collect={"nonsense": True}).ok
    assert "the collect pass stopped" in Plan.load(tree).dream_failure


def test_a_failed_dream_leaves_nothing_of_itself_in_the_pool(tmp_path):
    tree = tmp_path / "tree"
    run(tree, propose="nonsense")
    assert Plan.load(tree).dreams == []


def test_a_failure_says_its_checks_had_no_subject_rather_than_that_they_held(tmp_path):
    result = run(tmp_path / "tree", collect={"nonsense": True})
    assert set(result.named(verify.NO_SUBJECT)) >= {"dreams_shaped", "dreams_apart"}
    assert "Dreams are guesses" not in result.summary


def test_a_long_failure_is_cut_down_to_a_line(tmp_path):
    class Rambles(DiesAt):
        def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
            if label == "collect":
                raise LLMError("line one\n" * 500)
            return super().structured(system=system, user=user, schema=schema, label=label)

    tree = tmp_path / "tree"
    pipeline.run_plan(job_for(), tree, Rambles("none", script()))
    failure = Plan.load(tree).dream_failure
    assert "\n" not in failure and len(failure) < pipeline.MOST_FAILURE_CHARS + 50


def test_a_red_plan_whose_dreaming_failed_says_both(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    overrides = {"start": {"steps": [step("lending")]}, "collect": {"nonsense": True}}
    llm = FakeLLM([*script(**overrides), *([repair_of([], ["lending"])] * 3)])
    result = pipeline.run_plan(job, tree, llm)
    assert not result.ok
    assert any(line.startswith("Dreaming failed") for line in job.lines)
    assert any(line.startswith("Not verified") for line in job.lines)


# -- `--no-dream`, and the checkpoint -------------------------------------


def test_no_dream_makes_no_dream_call_and_leaves_the_page_saying_so(tmp_path, monkeypatch):
    llm = FakeLLM(script()[:5])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    tree = tmp_path / "tree"
    result = invoke("plan", IDEA, "--yes", "--no-dream", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert [call["label"] for call in llm.calls] == ["scope", "outline", "connect", "consider", "start"]
    assert "No dreams yet: dreaming has not run for this plan." in page(tree)
    assert "Estimated model calls: 5 in all, 3 still to come (connect, consider, start)" in said(result)
    assert "pass collect" not in result.output and "Dreaming failed" not in result.output


def test_dreaming_is_on_by_default_at_a_small_count():
    plan = Plan(slug="p", title="t", idea="i")
    schema = collect.schema(plan, lenses=lenses.LENSES, per_lens=dreaming.PLAN_PER_LENS)
    assert schema["properties"]["dreams"]["maxItems"] == len(lenses.LENSES)


def test_the_estimate_names_the_dream_passes(tmp_path):
    said_ = pipeline.call_estimate(FakeLLM([]))
    assert "8 in all, 6 still to come (connect, consider, start, collect, evaluate, propose)" in said_
    assert "5 in all" in pipeline.call_estimate(FakeLLM([]), dream=False)


# -- offline --------------------------------------------------------------


def test_offline_dreams_read_as_templates_and_never_as_ideas(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    assert len(plan.dreams) == len(lenses.LENSES)
    for dream in plan.dreams:
        assert dream.title.startswith("Template ") and "template" in dream.what_if
        assert {dream.pull, dream.reach, dream.cost, dream.fit} == {"not judged"}
    assert "Nothing here is researched." in page(tree)


def test_an_offline_plan_holds_proposals_and_set_aside_each_with_a_verdict_and_none_under_topics(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    verdicts = [dream.verdict for dream in plan.dreams]
    assert verdicts.count("proposed") == propose.MOST and verdicts.count("set-aside") == 3
    assert "## Proposals" in page(tree) and "## Set aside" in page(tree)
    for path in (tree / "topics").glob("*.md"):
        assert all(dream.what_if not in path.read_text(encoding="utf-8") for dream in plan.dreams)


def test_the_offline_templates_fit_every_cap_at_every_lens():
    for lens in lenses.LENSES:
        row = collect._template(lens, 9, "topic")
        for field, most in DREAM_FIELD_WORDS.items():
            assert dream_words(row[field]) <= most, (lens.slug, field)


def test_an_offline_round_on_a_person_added_topic_needs_no_baseline_row(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    assert collect.offline(plan.revised(dreams=[]))["dreams"][0]["anchor"] == plan.topics[0].slug


# -- the pool -------------------------------------------------------------


def test_two_offline_rounds_grow_one_pool_with_no_repeats_and_stable_ids(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    first = Plan.load(tree).dreams
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    second = Plan.load(tree).dreams
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    third = Plan.load(tree).dreams
    assert len(first) < len(second) < len(third)
    assert third[: len(second)] == second and second[: len(first)] == first
    ids, titles = [d.id for d in third], [d.title for d in third]
    assert len(set(ids)) == len(ids) and len(set(titles)) == len(titles)
    assert page(tree).count("# Dreams") == 1


def test_two_offline_rounds_are_byte_identical_on_two_trees(tmp_path):
    a, b = offline_plan(tmp_path / "a"), offline_plan(tmp_path / "b")
    for tree in (a, b):
        assert invoke("dream", str(tree), "--offline").exit_code == 0
    assert snapshot(a) == snapshot(b)


def test_a_pool_with_nothing_left_to_offer_reports_nothing_new_and_stays_green(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    for _ in range(4):
        assert invoke("dream", str(tree), "--offline").exit_code == 0
    full = Plan.load(tree).dreams
    assert len(full) == len(lenses.LENSES) * len(Plan.load(tree).topics)
    result = invoke("dream", str(tree), "--offline")
    assert result.exit_code == 0 and "0 new dream(s)" in result.output
    assert Plan.load(tree).dreams == full


def test_lens_narrows_a_round(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    before = len(Plan.load(tree).dreams)
    assert invoke("dream", str(tree), "--offline", "--lens", "the-opposite").exit_code == 0
    fresh = Plan.load(tree).dreams[before:]
    assert {dream.lens for dream in fresh} == {"the-opposite"}


def test_an_unknown_lens_is_refused_by_the_command_line(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", str(tree), "--offline", "--lens", "made-up").exit_code == 2


def test_a_model_round_reaches_the_collect_prompt_with_only_the_asked_lens(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM(round_of(dream_row("the-opposite", word="paint")))
    pipeline.dream_round(job_for(), tree, llm, lenses.chosen(("the-opposite",)))
    assert "- the-opposite:" in llm.calls[0]["user"] and "- who-else:" not in llm.calls[0]["user"]


def test_a_round_never_rewrites_a_dream_already_held(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree).dreams
    assert pipeline.dream_round(job_for(), tree, FakeLLM(round_of(dream_row(word="paint")))).ok
    assert Plan.load(tree).dreams[:2] == before


def test_a_set_aside_dream_collected_again_is_not_new(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree).dreams
    llm = FakeLLM([{"dreams": [dream_row("the-opposite", word="bread")]}])
    assert pipeline.dream_round(job_for(), tree, llm).ok
    assert Plan.load(tree).dreams == before
    assert [call["label"] for call in llm.calls] == ["collect"]


def test_a_dropped_dream_reworded_is_merged_by_evaluate_and_stays_dropped(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert pipeline.drop(job_for(), tree, "d1", "Not what a library is for.").ok
    reworded = {**dream_row(word="seedlings"), "title": "A seedling shelf"}
    answers = [{"dreams": [reworded]}, {"dreams": [judged_row("d3", duplicate_of="d1")]}]
    assert pipeline.dream_round(job_for(), tree, FakeLLM(answers)).ok
    plan = Plan.load(tree)
    assert [dream.id for dream in plan.dreams] == ["d1", "d2"]
    assert plan.dreams[0].verdict == "dropped"


def test_evaluate_is_shown_the_pool_it_must_merge_into(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM(round_of(dream_row(word="paint")))
    pipeline.dream_round(job_for(), tree, llm)
    assert "Already in the pool" in llm.calls[1]["user"] and '"id": "d2"' in llm.calls[1]["user"]


def test_ids_read_in_number_order_past_nine(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    text = page(tree)
    assert text.index("(d9)") < text.index("(d10)")


def test_a_failed_round_changes_nothing_and_exits_one(tmp_path, monkeypatch):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    monkeypatch.setattr(cli, "build_llm", lambda **_: DiesAt("evaluate", round_of(dream_row(word="paint"))[:1]))
    result = invoke("dream", str(tree))
    assert result.exit_code == 1
    assert "Dreaming failed, and nothing was changed" in said(result) and "out of credit" in said(result)
    assert snapshot(tree) == before


def test_a_round_that_lost_a_race_for_the_plan_writes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")

    class Races(FakeLLM):
        def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
            if label == "propose":
                Plan.load(tree).revised(goal="Someone else was here.").save(tree)
            return super().structured(system=system, user=user, schema=schema, label=label)

    with pytest.raises(pipeline.PlanRefused, match="changed while this ran"):
        pipeline.dream_round(job_for(), tree, Races(round_of(dream_row(word="paint"))))
    assert Plan.load(tree).goal == "Someone else was here."


# -- what `proto dream` will work on --------------------------------------


def red_tree(tree: Path) -> Path:
    plan = Plan.load(offline_plan(tree))
    plan.revised(steps=list(reversed(plan.steps))).save(tree)
    return tree


@pytest.mark.parametrize(
    "args",
    [
        ("dream", "{tree}"),
        ("dream", "promote", "d1", "--dir", "{tree}"),
        ("dream", "drop", "d1", "--why", "x", "--dir", "{tree}"),
    ],
    ids=["round", "promote", "drop"],
)
def test_a_red_plan_is_refused_with_no_model_call_and_no_change(tmp_path, monkeypatch, args):
    tree = red_tree(tmp_path / "tree")
    before = snapshot(tree)
    llm = FakeLLM([])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    result = invoke(*(arg.format(tree=tree) for arg in args))
    assert result.exit_code == 1
    assert "fails its checks" in said(result) and "start_order" in said(result)
    assert llm.calls == [] and snapshot(tree) == before


def test_a_directory_with_no_plan_is_refused(tmp_path):
    result = invoke("dream", str(tmp_path), "--offline")
    assert result.exit_code == 1 and "holds no plan" in said(result)


def test_a_plan_that_will_not_parse_is_refused(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    plan_path(tree).write_text("{", encoding="utf-8")
    result = invoke("dream", str(tree), "--offline")
    assert result.exit_code == 1 and "cannot be read as a plan" in said(result)


def test_a_hand_edited_page_is_drawn_over_and_the_person_is_told(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    (tree / "PLAN.md").write_text("my edit", encoding="utf-8")
    result = invoke("dream", str(tree), "--offline")
    assert result.exit_code == 0
    assert "PLAN.md differed from plan.json" in said(result)
    assert "my edit" not in page(tree, "PLAN.md")


def test_a_hand_edited_plan_json_that_still_holds_is_the_truth(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    Plan.load(tree).revised(goal="My own goal.").save(tree)
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    assert Plan.load(tree).goal == "My own goal."


def test_a_leftover_runbook_goes_once_the_plan_is_green_again(tmp_path):
    tree = red_tree(tmp_path / "tree")
    pipeline.run_plan(job_for(), tree)
    assert (tree / "RUNBOOK.md").exists()
    plan = Plan.load(tree)
    plan.revised(steps=list(reversed(plan.steps))).save(tree)
    assert invoke("dream", str(tree), "--offline").exit_code == 0
    assert not (tree / "RUNBOOK.md").exists()


# -- the shape of the command ---------------------------------------------


def test_the_bare_word_runs_a_round_in_the_current_directory(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    monkeypatch.chdir(tree)
    assert invoke("dream", "--offline").exit_code == 0
    assert len(Plan.load(tree).dreams) > len(lenses.LENSES)


def test_a_directory_named_like_a_verb_is_written_as_a_path(tmp_path, monkeypatch):
    offline_plan(tmp_path / "promote")
    monkeypatch.chdir(tmp_path)
    assert invoke("dream", "./promote", "--offline").exit_code == 0
    assert len(Plan.load(tmp_path / "promote").dreams) > len(lenses.LENSES)


def test_the_verb_wins_over_a_directory_and_says_what_it_lacks(tmp_path, monkeypatch):
    offline_plan(tmp_path / "promote")
    monkeypatch.chdir(tmp_path)
    result = invoke("dream", "promote")
    assert result.exit_code == 2 and "Missing argument 'ID'" in result.output


def test_round_is_also_typed_out_so_a_directory_named_round_is_reachable(tmp_path, monkeypatch):
    offline_plan(tmp_path / "round")
    monkeypatch.chdir(tmp_path)
    assert invoke("dream", "round", "round", "--offline").exit_code == 0


def test_help_describes_the_group_and_each_verb():
    shown = invoke("dream", "--help").output
    assert "promote" in shown and "drop" in shown and "./promote" in shown
    assert "--lens" in invoke("dream", "round", "--help").output


def test_why_is_required_by_the_command_line(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "drop", "d1", "--dir", str(tree)).exit_code == 2


# -- drop -----------------------------------------------------------------


def test_drop_records_why_calls_no_model_and_keeps_the_dream(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("drop called for a model"))
    result = invoke("dream", "drop", "d1", "--why", "  Too far  from it. ", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    dream = Plan.load(tree).dreams[0]
    assert (dream.verdict, dream.reason) == ("dropped", "Too far from it.")
    assert "## Dropped" in page(tree) and "- Verdict: dropped. Too far from it." in page(tree)


def test_a_reason_a_person_wrote_may_repeat_a_topic(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    risk = Plan.load(tree).topics[0].risks[0]
    assert pipeline.drop(job_for(), tree, "d1", risk).ok


@pytest.mark.parametrize(
    ("why", "first", "said_"),
    [("   ", "d1", "needs a reason"), ("x", "d99", "no dream 'd99'")],
    ids=["blank-why", "unknown-id"],
)
def test_drop_refuses_what_it_cannot_do(tmp_path, why, first, said_):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("dream", "drop", first, "--why", why, "--dir", str(tree))
    assert result.exit_code == 1 and said_ in said(result)
    assert snapshot(tree) == before


def test_a_dream_is_dropped_once(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "drop", "d1", "--why", "first", "--dir", str(tree)).exit_code == 0
    result = invoke("dream", "drop", "d1", "--why", "second", "--dir", str(tree))
    assert result.exit_code == 1 and "already dropped: first" in said(result)
    assert Plan.load(tree).dreams[0].reason == "first"


def test_a_promoted_dream_cannot_be_dropped(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "promote", "d1", "--offline", "--dir", str(tree)).exit_code == 0
    result = invoke("dream", "drop", "d1", "--why", "x", "--dir", str(tree))
    assert result.exit_code == 1 and "a topic is not dropped here" in said(result)


# -- promote --------------------------------------------------------------

NEW = "seeds"


def promote_answer(*edges: dict, **fields: list[str]) -> dict:
    return {"edges": list(edges), "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"], **fields}


def test_promote_offline_adds_a_verified_topic_tied_to_its_anchor(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    result = invoke("dream", "promote", "d2", "--offline", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    new, dream = plan.topics[-1], plan.dreams[1]
    assert (dream.verdict, dream.promoted_to) == ("promoted", new.slug)
    assert (new.title, new.why) == (dream.title, f"What if {dream.what_if}")
    assert (new.risks, new.unknowns, new.decisions, new.findings) == ([], [], [], [])
    assert any((e.from_topic, e.kind, e.to_topic) == (new.slug, "depends-on", dream.anchor) for e in plan.edges)
    assert (tree / "topics" / f"{new.slug}.md").is_file()
    assert f"topics/{new.slug}.md" in page(tree, "PLAN.md")
    assert verify.verdict(plan, render.read(tree)).ok
    assert "## Promoted" in page(tree) and f"[{new.title}](topics/{new.slug}.md)" in page(tree)


def test_a_promoted_topic_says_it_is_not_researched(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    result = invoke("dream", "promote", "d1", "--offline", "--dir", str(tree))
    plan = Plan.load(tree)
    assert plan.researched is False
    assert render.NOT_RESEARCHED in page(tree, f"topics/{plan.topics[-1].slug}.md")
    assert "it is not researched" in said(result)


def test_a_promoted_dreams_own_words_on_its_topic_are_not_a_leak(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "promote", "d1", "--offline", "--dir", str(tree)).exit_code == 0
    plan = Plan.load(tree)
    assert plan.dreams[0].what_if in page(tree, f"topics/{plan.topics[-1].slug}.md")
    assert verify.dreams_apart(plan, render.read(tree)).state == verify.PASSED


def test_with_a_model_a_promoted_topic_is_connected_and_considered(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM([promote_answer(edge("seeds_too", "members"), edge("space", "seeds_too", "informs"))])
    assert pipeline.promote(job_for(), tree, "d1", llm).ok
    plan = Plan.load(tree)
    new = plan.topics[-1]
    assert (new.slug, new.risks, new.unknowns, new.decisions) == ("seeds_too", ["r"], ["u?"], ["d"])
    assert plan.steps == Plan.load(tree).steps
    assert "- Seeds too depends on Members" in page(tree, "topics/seeds_too.md")


def test_promote_leaves_every_other_topic_and_edge_alone(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = Plan.load(tree)
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([promote_answer(edge("seeds_too", "members"))])).ok
    after = Plan.load(tree)
    assert after.topics[:-1] == before.topics and after.edges[: len(before.edges)] == before.edges
    assert after.steps == before.steps


def test_a_link_that_leaves_out_the_new_topic_is_refused_and_nothing_changes(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="leaves out the new topic"):
        pipeline.promote(job_for(), tree, "d1", FakeLLM([promote_answer(edge("space", "money"))]))
    assert snapshot(tree) == before


def test_the_promote_pass_cannot_write_a_finding_or_a_source(tmp_path):
    tree = model_plan(tmp_path / "tree")
    forged = {
        **promote_answer(),
        "findings": [{"text": "x", "assumption": False}],
        "researched": True,
        "sources": ["s"],
    }
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([forged])).ok
    plan = Plan.load(tree)
    assert (plan.topics[-1].findings, plan.researched, plan.sources) == ([], False, [])


def test_a_link_that_breaks_the_start_goes_through_the_verifier_and_repair(tmp_path):
    tree = model_plan(tmp_path / "tree")
    links = [*GOOD["connect"]["edges"], edge("members", "seeds_too")]
    mended = repair_of(links, ["seeds_too", "members"])
    llm = FakeLLM([promote_answer(edge("members", "seeds_too")), mended])
    job = job_for()
    assert pipeline.promote(job, tree, "d1", llm).ok
    assert [call["label"] for call in llm.calls] == ["promote", "repair"]
    assert any(e["kind"] == "verify_failed" and e["stage"] == "start_order" for e in job.events)
    assert [s.topic for s in Plan.load(tree).steps] == ["seeds_too", "members"]


def test_a_link_that_closes_a_loop_goes_through_repair_and_its_rules(tmp_path):
    tree = model_plan(tmp_path / "tree")
    loop = [edge("seeds_too", "members"), edge("members", "seeds_too")]
    # Repair may give up one link on the loop, never an edge on no loop.
    mended = repair_of([*GOOD["connect"]["edges"], edge("seeds_too", "members")], ["members"])
    llm = FakeLLM([promote_answer(*loop), mended])
    assert pipeline.promote(job_for(), tree, "d1", llm).ok
    assert sum(e.to_topic == "seeds_too" for e in Plan.load(tree).edges) == 0


def test_a_repair_that_deletes_a_real_edge_is_still_thrown_away(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    lost = repair_of([edge("seeds_too", "members")], ["members"])
    answers = [promote_answer(edge("seeds_too", "members"), edge("members", "seeds_too")), lost, lost, lost]
    with pytest.raises(pipeline.PlanRefused, match="failed its checks"):
        pipeline.promote(job_for(), tree, "d1", FakeLLM(answers))
    assert snapshot(tree) == before


def test_a_promotion_that_stays_red_changes_nothing_and_exits_one(tmp_path, monkeypatch):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    stuck = repair_of([*GOOD["connect"]["edges"], edge("members", "seeds_too")], ["members"])
    llm = FakeLLM([promote_answer(edge("members", "seeds_too")), stuck, stuck, stuck])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    result = invoke("dream", "promote", "d1", "--dir", str(tree))
    assert result.exit_code == 1
    assert "Nothing was changed" in said(result) and "start_order" in said(result)
    assert snapshot(tree) == before and not (tree / "RUNBOOK.md").exists()


def test_a_backend_failure_while_promoting_changes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="was not promoted"):
        pipeline.promote(job_for(), tree, "d1", DiesAt("promote", []))
    assert snapshot(tree) == before


def test_a_dream_is_promoted_once(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "promote", "d1", "--offline", "--dir", str(tree)).exit_code == 0
    topics = len(Plan.load(tree).topics)
    result = invoke("dream", "promote", "d1", "--offline", "--dir", str(tree))
    assert result.exit_code == 1 and "already the topic" in said(result)
    assert len(Plan.load(tree).topics) == topics


def test_promote_refuses_an_id_the_pool_does_not_hold(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    result = invoke("dream", "promote", "../../etc", "--offline", "--dir", str(tree))
    assert result.exit_code == 1 and "no dream '../../etc'" in said(result)


def test_a_set_aside_dream_can_be_promoted_because_a_person_may_disagree(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert Plan.load(tree).dreams[1].verdict == "set-aside"
    assert pipeline.promote(job_for(), tree, "d2", FakeLLM([promote_answer()])).ok
    assert Plan.load(tree).dreams[1].verdict == "promoted"


def test_a_promoted_title_that_collides_takes_a_number(tmp_path):
    tree = model_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    taken = plan.dreams[0].model_copy(update={"title": "Members"})
    plan.revised(dreams=[taken, *plan.dreams[1:]]).save(tree)
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([promote_answer()])).ok
    assert Plan.load(tree).topics[-1].slug == "members_2"


def test_a_promoted_slug_stays_inside_the_length_a_file_can_have():
    plan = Plan(slug="p", title="t", idea="i", topics=[Topic(slug="a" * 64, title="T", why="w")])
    assert len(dreaming._free_slug(plan, "a" * 64)) == 64


def test_a_later_round_treats_a_promoted_dream_as_taken(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([promote_answer()])).ok
    llm = FakeLLM([{"dreams": [dream_row()]}])
    assert pipeline.dream_round(job_for(), tree, llm).ok
    assert [dream.id for dream in Plan.load(tree).dreams] == ["d1", "d2"]


def test_collect_is_asked_for_every_lens_and_shown_the_pool(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM(round_of(dream_row(word="paint")))
    pipeline.dream_round(job_for(), tree, llm)
    shown = llm.calls[0]["user"]
    assert all(lens.slug in shown for lens in lenses.LENSES)
    assert "Seeds too" in shown and "Bread too" in shown


def test_a_rerender_keeps_the_note_and_a_good_round_clears_it(tmp_path):
    tree = tmp_path / "tree"
    run(tree, collect={"nonsense": True})
    assert pipeline.run_plan(job_for(), tree, FakeLLM([])).ok
    assert "**Dreaming failed:**" in page(tree)
    assert pipeline.dream_round(job_for(), tree, FakeLLM(round_of(dream_row(), first=1))).ok
    assert "**Dreaming failed:**" not in page(tree)
    assert "dream_failure" not in json.loads(plan_path(tree).read_text(encoding="utf-8"))


def test_a_sibling_dream_close_to_a_promoted_one_does_not_block_the_promotion(tmp_path):
    tree = tmp_path / "tree"
    close = {**dream_row("the-opposite", word="seedlings"), "title": "Another shelf"}
    run(tree, collect={"dreams": [dream_row(), close]})
    assert pipeline.promote(job_for(), tree, "d1", FakeLLM([promote_answer()])).ok


# -- nothing else crosses -------------------------------------------------


def test_no_run_of_any_pass_turns_a_dream_into_a_topic(tmp_path):
    tree = model_plan(tmp_path / "tree")
    assert [topic.slug for topic in Plan.load(tree).topics] == SLUGS
    assert pipeline.dream_round(job_for(), tree, FakeLLM(round_of(dream_row(word="paint")))).ok
    assert [topic.slug for topic in Plan.load(tree).topics] == SLUGS


def test_only_the_promote_verb_calls_the_one_function_that_crosses():
    callers = [
        path.relative_to(REPO).as_posix()
        for path in (REPO / "protopilot").rglob("*.py")
        if re.search(r"dreaming\.promoted\(", path.read_text(encoding="utf-8"))
    ]
    assert callers == ["protopilot/plan/pipeline.py"]
    source = (REPO / "protopilot" / "plan" / "pipeline.py").read_text(encoding="utf-8")
    assert source.count("dreaming.promoted(") == 1
    assert source.index("dreaming.promoted(") > source.index("def promote(")
    assert (REPO / "protopilot" / "cli.py").read_text(encoding="utf-8").count("pipeline.promote(") == 1


# -- honesty --------------------------------------------------------------


def test_a_dreams_page_always_says_nothing_here_is_researched(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("dream", "drop", "d1", "--why", "no", "--dir", str(tree)).exit_code == 0
    assert invoke("dream", "promote", "d2", "--offline", "--dir", str(tree)).exit_code == 0
    assert "Nothing here is researched." in page(tree)


def test_html_a_model_writes_in_a_dream_stays_inert(tmp_path):
    tree = tmp_path / "tree"
    row = {**dream_row(), "title": "<!-- hide"}
    run(tree, collect={"dreams": [row, dream_row("the-opposite", word="bread")]})
    assert "&lt;!-- hide" in page(tree)


@pytest.mark.parametrize("dream_id", ["../../etc", "D1", "", "a b", "d" * 40, "d1/x"])
def test_a_dream_id_is_validated_when_the_plan_loads(dream_id):
    with pytest.raises(ValueError, match="dream id"):
        Dream(id=dream_id, title="t", what_if="w", lens="l", anchor="a", takes="x")


@pytest.mark.parametrize("link", ["../../etc", "a/b", "A"])
def test_a_promoted_link_is_a_slug_because_it_is_drawn_as_a_path(link):
    with pytest.raises(ValueError, match="slug"):
        Dream(id="d1", title="t", what_if="w", lens="l", anchor="a", takes="x", promoted_to=link)
