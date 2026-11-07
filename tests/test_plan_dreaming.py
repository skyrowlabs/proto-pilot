"""Dreaming: the three passes, the pool, a person's verbs, and a failure that costs only dreams."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, SLUGS, dream_row, judged_row, proposal_row, repair_of, script, step

from protopilot import cli
from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import dreaming, lenses, pipeline, verify
from protopilot.plan.model import DREAM_FIELD_WORDS, DREAM_WORD_CAP, Dream, Plan, dream_words
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
