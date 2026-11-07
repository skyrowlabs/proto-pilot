"""What a repair may and may not get away with: review edits, mixed reds, the cut, the guard, the bound."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, NO_REPAIR, SLUGS, consider_of, edge, repair_of, script, step

from protopilot import cli
from protopilot.jobs import Job
from protopilot.plan import baseline, pipeline, render, verify
from protopilot.plan.model import Dream, Finding, Plan, Source
from protopilot.plan.passes import PlanPassError, outline, repair, start

pytestmark = [pytest.mark.unit]

GOOD_EDGES = GOOD["connect"]["edges"]
OUT_OF_ORDER = {"steps": [step("lending"), step("members")]}
IN_ORDER = ["members", "lending"]
LOOP = [edge("lending", "space"), edge("space", "lending"), edge("tools", "lending")]
MENDED = [edge("lending", "space"), edge("tools", "lending")]
TYPED_SOURCE = Source(id="s1", title="A study", url="https://example.com")


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def run(tree: Path, *repairs: Any, **overrides: object) -> tuple[Job, FakeLLM, verify.PlanVerdict]:
    job, llm = job_for(), FakeLLM([*script(**overrides), *repairs, NO_REPAIR])
    return job, llm, pipeline.run_plan(job, tree, llm)


def kinds(job: Job) -> list[str]:
    return [event["kind"] for event in job.events]


def repairs_in(llm: FakeLLM) -> int:
    return [call["label"] for call in llm.calls].count("repair")


def runbook(tree: Path) -> str:
    return (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def plan_of(edges: list[dict], steps: list[str]) -> Plan:
    """The script's six topics, holding exactly `edges` and `steps`, whatever is wrong with them."""
    return Plan.model_validate(
        {
            "slug": "tool_library",
            "title": "Tool library",
            "idea": IDEA,
            "topics": [{"slug": s, "title": s.title(), "why": "Why."} for s in SLUGS],
            "edges": edges,
            "steps": [step(topic) for topic in steps],
        }
    )


# -- review edits and a repair --------------------------------------------


def reviewed(
    tree: Path, edit: Callable[[Plan], Plan], slugs: list[str], *after: dict, **overrides: object
) -> tuple[Job, FakeLLM, verify.PlanVerdict]:
    """A run whose outline `edit` changes at the review, then `after` as the repair answers."""
    passes = {**GOOD, "consider": consider_of(slugs), **overrides}
    job = job_for()
    llm = FakeLLM(
        [GOOD["scope"], GOOD["outline"], passes["connect"], passes["consider"], passes["start"], *after, NO_REPAIR]
    )
    draft = edit(pipeline.outlined(job, llm, pipeline.scoped(job, llm)))
    return job, llm, pipeline.build(job, tree, draft, llm, dream=False)


def adding_insurance(plan: Plan) -> Plan:
    return outline.add(plan, "Insurance", "It decides what can be lent.")


def dropping_safety(plan: Plan) -> Plan:
    return outline.drop(plan, "safety")


def test_a_repair_can_place_a_topic_added_at_the_review(tmp_path):
    tree = tmp_path / "tree"
    connect = {"edges": [*GOOD_EDGES, edge("members", "insurance")]}
    bad = {"steps": [step("members"), step("insurance")]}
    answer = repair_of(connect["edges"], ["insurance", "members", "lending"])
    _, llm, result = reviewed(tree, adding_insurance, [*SLUGS, "insurance"], answer, connect=connect, start=bad)
    assert result.ok and repairs_in(llm) == 1
    assert [s.topic for s in Plan.load(tree).steps] == ["insurance", "members", "lending"]
    assert "It decides what can be lent." in (tree / "topics" / "insurance.md").read_text(encoding="utf-8")


def test_a_repair_naming_a_topic_dropped_at_the_review_is_refused_and_it_stays_dropped(tmp_path):
    tree, kept = tmp_path / "tree", SLUGS[:-1]
    answer = repair_of([*GOOD_EDGES, edge("safety", "members")], IN_ORDER)
    job, llm, result = reviewed(tree, dropping_safety, kept, answer, start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == 1 and "repair_failed" in kinds(job)
    assert "an edge names topics that do not exist: safety" in runbook(tree)
    assert [t.slug for t in Plan.load(tree).topics] == kept
    assert not (tree / "topics" / "safety.md").exists()


def test_a_step_on_a_topic_dropped_at_the_review_is_refused(tmp_path):
    tree = tmp_path / "tree"
    answer = repair_of(GOOD_EDGES, ["members", "safety"])
    _, _, result = reviewed(tree, dropping_safety, SLUGS[:-1], answer, start=OUT_OF_ORDER)
    assert not result.ok
    assert "step 2 names a topic that does not exist: safety" in runbook(tree)


def test_a_rename_at_the_review_survives_a_repair(tmp_path):
    tree = tmp_path / "tree"
    answer = repair_of(GOOD_EDGES, IN_ORDER)
    _, _, result = reviewed(
        tree, lambda plan: outline.rename(plan, "members", "Who joins"), SLUGS, answer, start=OUT_OF_ORDER
    )
    assert result.ok
    entry = (tree / "PLAN.md").read_text(encoding="utf-8")
    assert "1. **Who joins:**" in entry and "[Who joins](topics/members.md)" in entry


class Recording(FakeLLM):
    """Keeps the schema each pass was held to."""

    def __init__(self, responses: list) -> None:
        super().__init__(responses)
        self.schemas: dict[str, dict] = {}

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        self.schemas[label] = schema
        return super().structured(system=system, user=user, schema=schema, label=label)


def test_a_repair_is_offered_only_the_topics_the_review_left(tmp_path, monkeypatch):
    kept = [*SLUGS[:-1], "insurance"]
    llm = Recording([*script(consider=consider_of(kept), start=OUT_OF_ORDER), repair_of(GOOD_EDGES, IN_ORDER)])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    monkeypatch.setattr(cli, "_stdin_is_terminal", lambda: True)
    typed = "add Insurance\nIt decides what can be lent.\ndrop 6\n\n"
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--dir", str(tmp_path / "tree")], input=typed)
    assert result.exit_code == 0, result.output
    assert llm.schemas["repair"]["properties"]["steps"]["items"]["properties"]["topic"]["enum"] == kept
    assert [t.slug for t in Plan.load(tmp_path / "tree").topics] == kept


# -- fixable and unfixable in one run -------------------------------------


def unfixable_too(plan: Plan) -> Plan:
    return plan.revised(sources=[TYPED_SOURCE])


def test_a_mixed_run_mends_what_it_can_then_stops_without_another_call(tmp_path):
    tree = tmp_path / "tree"
    job, llm, result = reviewed(tree, unfixable_too, SLUGS, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    assert not result.ok and result.stage == "sources_fetched"
    assert repairs_in(llm) == 1
    assert [s.topic for s in Plan.load(tree).steps] == IN_ORDER
    said = runbook(tree)
    assert "[sources_fetched]" in said and "[start_order]" not in said
    assert "steps now members, lending" in said
    assert "2. attempt 2 (sources_fetched): repair cannot reach sources_fetched, so none ran" in said


def test_a_mixed_run_tells_repair_only_what_it_can_reach(tmp_path):
    _, llm, _ = reviewed(tmp_path / "tree", unfixable_too, SLUGS, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    told = llm.calls[-1]["user"]
    assert "[start_order]" in told and "[sources_fetched]" not in told


def test_a_mixed_run_where_repair_fails_keeps_both_faults_on_the_page(tmp_path):
    tree = tmp_path / "tree"
    _, llm, result = reviewed(tree, unfixable_too, SLUGS, {"edges": "nonsense"}, start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == 1
    said = runbook(tree)
    assert "[sources_fetched]" in said and "[start_order]" in said


def test_two_unfixable_checks_are_both_named_and_cost_no_call():
    plan = plan_of(GOOD_EDGES, ["members"]).revised(
        sources=[TYPED_SOURCE],
        dreams=[Dream(id="d1", title="Seeds", what_if="it lent seeds", lens="l", anchor="ghost", takes="A shelf")],
    )
    llm = FakeLLM([])
    checked = pipeline.repaired(job_for(), plan, llm)
    assert llm.calls == []
    assert checked.tried == [
        "attempt 1 (sources_fetched): repair cannot reach sources_fetched, dreams_shaped, so none ran"
    ]


# -- the cut at MAX_STEPS -------------------------------------------------

KEPT = ["members", "lending", "money", "space", "tools"]


def test_a_fault_past_the_cut_is_cut_with_its_step_and_costs_no_repair(tmp_path):
    tree = tmp_path / "tree"
    too_many = {"steps": [step(s) for s in [*KEPT, "safety", "safety"]]}
    _, llm, result = run(tree, start=too_many)
    assert result.ok and repairs_in(llm) == 0
    assert [s.topic for s in Plan.load(tree).steps] == KEPT


def test_a_fault_inside_the_cut_still_reaches_repair(tmp_path):
    tree = tmp_path / "tree"
    inside = {"steps": [step(s) for s in ["lending", "members", "money", "space", "tools", "safety"]]}
    _, llm, result = run(tree, repair_of(GOOD_EDGES, KEPT), start=inside)
    assert result.ok and repairs_in(llm) == 1


def test_a_ghost_past_the_cut_is_still_refused_rather_than_cut(tmp_path):
    with pytest.raises(PlanPassError, match="step 6 names a topic that does not exist: ghost"):
        run(tmp_path / "tree", start={"steps": [step(s) for s in [*KEPT, "ghost"]]})


def test_a_repair_cannot_hold_more_steps_than_the_cut_allows(tmp_path):
    tree = tmp_path / "tree"
    bad = {"steps": [step(s) for s in ["lending", "members", "money", "space"]]}
    answer = repair_of(GOOD_EDGES, [*KEPT, "safety"])
    _, _, result = run(tree, answer, start=bad)
    assert result.ok
    assert len(Plan.load(tree).steps) == start.MAX_STEPS


# -- what a repair says it did --------------------------------------------


@pytest.mark.parametrize(
    ("edges", "steps", "said"),
    [
        (GOOD_EDGES, ["lending", "members"], ""),
        (list(reversed(GOOD_EDGES)), ["lending", "members"], ""),
        (GOOD_EDGES, IN_ORDER, "steps now members, lending"),
        (GOOD_EDGES[1:], ["lending", "members"], "removed lending depends-on members"),
        ([*GOOD_EDGES, edge("tools", "money")], ["lending", "members"], "added tools depends-on money"),
        (
            [edge("lending", "members", "informs"), GOOD_EDGES[1]],
            ["lending", "members"],
            "removed lending depends-on members; added lending informs members",
        ),
        (
            [edge("safety", "tools"), edge("tools", "money", "conflicts-with")],
            ["members"],
            "removed lending depends-on members; removed money informs space; "
            "added safety depends-on tools; added tools conflicts-with money; steps now members",
        ),
    ],
    ids=["nothing", "edges-reordered", "steps", "removed", "added", "retyped", "all-at-once-in-a-fixed-order"],
)
def test_changes_reads_the_data_and_says_what_moved(edges, steps, said):
    assert repair.changes(plan_of(GOOD_EDGES, ["lending", "members"]), plan_of(edges, steps)) == said


def test_what_a_repair_did_reads_the_same_in_the_event_and_the_runbook(tmp_path):
    tree = tmp_path / "tree"
    keeps_failing = repair_of(GOOD_EDGES, ["lending", "members", "space"])
    job, _, _ = run(tree, keeps_failing, {"edges": 1}, start=OUT_OF_ORDER)
    done = next(event for event in job.events if event["kind"] == "repair_done")
    assert done["notes"] == "steps now lending, members, space"
    assert f"1. attempt 1 (start_order): {done['notes']}" in runbook(tree)


# -- a repair that goes after the plan ------------------------------------


def rich() -> Plan:
    sourced = Finding(text="Lending works.", assumption=False, source_ids=["s1"])
    fetched = Source(id="s1", title="A study", url="https://example.com", fetched=True)
    plan = baseline.build_plan(IDEA)
    first = plan.topics[0].model_copy(update={"findings": [sourced]})
    dream = Dream(id="d1", title="Seeds", what_if="it lent seeds", lens="l", anchor="scope", takes="A shelf")
    return plan.revised(researched=True, sources=[fetched], topics=[first, *plan.topics[1:]], dreams=[dream])


def test_a_repair_leaves_every_field_but_edges_and_steps_as_it_found_them():
    plan = rich()
    forged = {"researched": False, "sources": [], "topics": [], "dreams": [], "title": "Forged", "idea": "Forged"}
    rows = [{**e.model_dump(), **forged} for e in plan.edges[1:]]
    after = repair.apply(plan, {**forged, "edges": rows, "steps": [s.model_dump() for s in plan.steps[:1]]})
    untouched = {"edges", "steps"}
    assert after.model_dump(exclude=untouched) == plan.model_dump(exclude=untouched)
    assert (len(after.edges), len(after.steps)) == (len(plan.edges) - 1, 1)


@pytest.mark.parametrize(
    ("answer", "problem"),
    [
        (repair_of(GOOD_EDGES, []), "no steps, and a plan has to say where to begin"),
        ({"edges": GOOD_EDGES}, "missing field 'steps'"),
        ({"steps": [step("members")]}, "missing field 'edges'"),
        ({"edges": "nonsense", "steps": [step("members")]}, "a field that must be a list held str"),
        ({"edges": GOOD_EDGES, "steps": None}, "cannot be used"),
        ([], "cannot be used"),
        (repair_of([edge("members", "members")], IN_ORDER), "joins 'members' to itself"),
        (
            repair_of([edge(a, b) for a, b in zip(SLUGS, SLUGS[1:] + SLUGS[:1])], IN_ORDER),
            "every topic depends on another",
        ),
    ],
    ids=[
        "empty-steps",
        "no-steps-key",
        "no-edges-key",
        "edges-a-string",
        "steps-null",
        "not-an-object",
        "self",
        "ring",
    ],
)
def test_a_repair_a_plan_cannot_hold_stops_the_loop_and_changes_nothing(tmp_path, answer, problem):
    tree = tmp_path / "tree"
    job, llm, result = run(tree, answer, start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == 1 and "repair_failed" in kinds(job)
    assert problem in runbook(tree)
    plan = Plan.load(tree)
    assert [s.topic for s in plan.steps] == ["lending", "members"]
    assert [(e.from_topic, e.to_topic) for e in plan.edges] == [("lending", "members"), ("money", "space")]


@pytest.mark.parametrize(
    "edges",
    [
        [],
        GOOD_EDGES[1:],
        [edge("lending", "members", "informs"), GOOD_EDGES[1]],
        [edge("lending", "members", "conflicts-with"), GOOD_EDGES[1]],
        [edge("members", "lending"), GOOD_EDGES[1]],
    ],
    ids=["every-edge-deleted", "the-edge-deleted", "retyped-informs", "retyped-conflicts", "reversed"],
)
def test_no_way_of_losing_a_dependency_buys_green_for_a_bad_order(tmp_path, edges):
    tree = tmp_path / "tree"
    job, _, result = run(tree, repair_of(edges, ["lending", "members"]), start=OUT_OF_ORDER)
    assert not result.ok and "repair_rejected" in kinds(job)
    assert any(e.from_topic == "lending" and e.kind == "depends-on" for e in Plan.load(tree).edges)


def test_mending_a_loop_does_not_license_dropping_an_edge_off_it():
    plan = plan_of(LOOP, ["members"])
    after = plan_of([edge("lending", "space")], ["members"])
    assert repair.rejected(plan, after) == "it removed edges on no loop: tools depends-on lending"


# -- the shrink guard: honest fixes pass, evasions do not -----------------

TWO_LOOPS = [edge("lending", "space"), edge("space", "lending"), edge("tools", "money"), edge("money", "tools")]
SHARED = [edge("lending", "space"), edge("space", "lending"), edge("space", "tools"), edge("tools", "space")]
RING = [edge("lending", "space"), edge("space", "tools"), edge("tools", "lending")]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (plan_of(LOOP, ["members"]), plan_of(MENDED, ["members"])),
        (plan_of(LOOP, ["members"]), plan_of([*MENDED, edge("space", "lending", "informs")], ["members"])),
        (plan_of(LOOP, ["members"]), plan_of([*MENDED, edge("space", "lending", "conflicts-with")], ["members"])),
        (plan_of(RING, ["members"]), plan_of(RING[:2], ["members"])),
        (plan_of(TWO_LOOPS, ["members"]), plan_of([TWO_LOOPS[0], TWO_LOOPS[2]], ["members"])),
        (plan_of(SHARED, ["members"]), plan_of([SHARED[1], SHARED[3]], ["members"])),
        (plan_of(GOOD_EDGES, ["lending", "members"]), plan_of(GOOD_EDGES, IN_ORDER)),
        (plan_of(GOOD_EDGES, ["lending"]), plan_of(GOOD_EDGES, IN_ORDER)),
        (plan_of(GOOD_EDGES, ["lending", "tools"]), plan_of(GOOD_EDGES, ["tools"])),
        (plan_of(GOOD_EDGES, ["tools", "tools"]), plan_of(GOOD_EDGES, ["tools"])),
        (plan_of(GOOD_EDGES, ["members"]), plan_of([*GOOD_EDGES, edge("tools", "money")], ["members"])),
    ],
    ids=[
        "one-link-removed",
        "one-link-retyped-informs",
        "one-link-retyped-conflicts",
        "one-link-of-a-ring",
        "one-link-of-each-of-two-loops",
        "two-links-of-two-loops-sharing-a-topic",
        "steps-reordered",
        "prerequisite-added",
        "faulted-step-dropped",
        "repeat-dropped",
        "edge-added",
    ],
)
def test_an_honest_fix_is_never_refused(before, after):
    assert repair.rejected(before, after) == ""


def test_retyping_every_link_of_a_loop_is_removing_every_link_of_it():
    plan = plan_of(RING, ["members"])
    retyped = [{**row, "kind": "informs"} for row in RING]
    assert (
        repair.rejected(plan, plan_of(retyped, ["members"])) == "it removed every link on the loop, and one is enough"
    )


def test_a_single_self_link_is_the_one_loop_that_may_lose_every_link():
    plan = plan_of([edge("members", "members")], ["members"])
    assert repair.rejected(plan, plan_of([], ["members"])) == ""


def test_keeping_a_steps_topic_but_moving_it_is_not_a_drop():
    plan = plan_of(GOOD_EDGES, ["tools", "money", "space"])
    assert repair.rejected(plan, plan_of(GOOD_EDGES, ["space", "tools", "money"])) == ""


def test_every_healthy_step_lost_is_named():
    plan = plan_of(GOOD_EDGES, ["tools", "money", "space"])
    reason = repair.rejected(plan, plan_of(GOOD_EDGES, ["money"]))
    assert reason == "it dropped steps nothing was wrong with: space, tools"


# -- the bound ------------------------------------------------------------


def rejected_answer() -> dict:
    return repair_of([], ["members"])


def landed_but_red() -> dict:
    return repair_of(GOOD_EDGES, ["lending", "members", "space"])


def test_every_repair_rejected_costs_exactly_the_bound(tmp_path):
    job, llm, result = run(tmp_path / "tree", *[rejected_answer() for _ in range(9)], start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == repair.ATTEMPTS
    assert kinds(job).count("repair_rejected") == repair.ATTEMPTS
    assert kinds(job).count("exhausted") == 1


def test_rejected_and_landed_repairs_share_one_bound(tmp_path):
    answers = [rejected_answer(), landed_but_red(), rejected_answer(), rejected_answer()]
    job, llm, _ = run(tmp_path / "tree", *answers, start=OUT_OF_ORDER)
    assert repairs_in(llm) == repair.ATTEMPTS
    assert (kinds(job).count("repair_rejected"), kinds(job).count("repair_done")) == (2, 1)


def test_a_repair_that_lands_on_the_last_attempt_is_verified_and_goes_green(tmp_path):
    tree = tmp_path / "tree"
    answers = [rejected_answer(), rejected_answer(), repair_of(GOOD_EDGES, IN_ORDER)]
    job, llm, result = run(tree, *answers, start=OUT_OF_ORDER)
    assert result.ok and repairs_in(llm) == repair.ATTEMPTS
    assert job.events[-1]["ok"] is True and job.events[-1]["attempts"] == repair.ATTEMPTS + 1
    assert "exhausted" not in kinds(job)
    assert not (tree / "RUNBOOK.md").exists()


@pytest.mark.parametrize("bound", [1, 2, 5])
def test_the_bound_is_the_constant_and_not_a_literal(tmp_path, monkeypatch, bound):
    monkeypatch.setattr(repair, "ATTEMPTS", bound)
    _, llm, result = run(tmp_path / "tree", *[rejected_answer() for _ in range(9)], start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == bound


class Tireless(FakeLLM):
    """Answers every repair with something new and still red, so only the loop's own bound can end it."""

    def __init__(self, responses: list) -> None:
        super().__init__(responses)
        self.answered = 0

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label != "repair":
            return super().structured(system=system, user=user, schema=schema, label=label)
        self.answered += 1
        more = [edge("safety", slug, "informs") for slug in SLUGS[: self.answered]]
        return repair_of([*GOOD_EDGES, *more], ["lending", "members"])


def test_a_model_that_never_stops_answering_is_stopped_by_the_bound(tmp_path):
    llm = Tireless(script(start=OUT_OF_ORDER))
    assert not pipeline.run_plan(job_for(), tmp_path / "tree", llm).ok
    assert llm.answered == repair.ATTEMPTS


def test_a_crash_on_a_later_attempt_stops_there_and_keeps_what_landed(tmp_path):
    tree = tmp_path / "tree"
    job, llm, result = run(tree, landed_but_red(), start=OUT_OF_ORDER)  # the fake runs dry on the second
    assert not result.ok and repairs_in(llm) == 2
    assert kinds(job).count("repair_failed") == 1 and kinds(job).count("exhausted") == 1
    assert [s.topic for s in Plan.load(tree).steps] == ["lending", "members", "space"]


def test_an_empty_repair_after_a_landed_one_stops_the_loop(tmp_path):
    same = landed_but_red()
    job, llm, result = run(tmp_path / "tree", same, same, start=OUT_OF_ORDER)
    assert not result.ok and repairs_in(llm) == 2
    assert kinds(job).count("repair_empty") == 1


def test_a_rejection_is_forgotten_once_a_repair_lands(tmp_path):
    answers = [rejected_answer(), landed_but_red(), repair_of(GOOD_EDGES, [*IN_ORDER, "space"])]
    _, llm, result = run(tmp_path / "tree", *answers, start=OUT_OF_ORDER)
    assert result.ok
    told = [call["user"] for call in llm.calls if call["label"] == "repair"]
    assert ["thrown away" in user for user in told] == [False, True, False]


def test_the_page_is_drawn_from_the_repaired_plan_not_the_one_that_failed(tmp_path):
    tree = tmp_path / "tree"
    run(tree, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    assert render.render(Plan.load(tree)) == render.read(tree)


# -- the guard judges against the plan repair started from ----------------


def test_two_attempts_cannot_reverse_a_real_dependency(tmp_path):
    first = repair_of([*GOOD_EDGES, edge("members", "lending")], ["lending", "members"])
    second = repair_of([GOOD_EDGES[1], edge("members", "lending")], ["lending", "members"])
    tree = tmp_path / "tree"
    run(tree, first, second, start=OUT_OF_ORDER)
    assert any(e.from_topic == "lending" and e.to_topic == "members" for e in Plan.load(tree).edges)


def test_two_attempts_cannot_drop_a_healthy_step(tmp_path):
    healthy = {"steps": [step("members"), step("lending"), step("tools")]}
    first = {"edges": [*LOOP, edge("members", "tools")], "steps": healthy["steps"]}
    second = {
        "edges": [edge("lending", "space"), edge("tools", "lending"), edge("members", "tools")],
        "steps": [step("space"), step("lending"), step("tools")],
    }
    tree = tmp_path / "tree"
    run(tree, first, second, connect={"edges": LOOP}, start=healthy)
    assert "members" in [s.topic for s in Plan.load(tree).steps]


# -- the cap on steps -----------------------------------------------------

PREREQUISITE = [edge("space", "money"), edge("tools", "space")]
FULL_LIST = ["members", "lending", "space", "tools", "safety"]


def test_a_full_list_can_make_room_for_a_prerequisite(tmp_path):
    five = {"steps": [step(s) for s in FULL_LIST]}
    honest = repair_of(PREREQUISITE, ["members", "lending", "money", "space", "tools"])
    assert run(tmp_path / "tree", honest, connect={"edges": PREREQUISITE}, start=five)[2].ok


def test_the_tools_cut_does_not_count_as_the_model_dropping_a_step(tmp_path):
    five = {"steps": [step(s) for s in FULL_LIST]}
    all_six = repair_of(PREREQUISITE, ["members", "lending", "money", "space", "tools", "safety"])
    assert run(tmp_path / "tree", all_six, connect={"edges": PREREQUISITE}, start=five)[2].ok


def test_a_full_list_cannot_swap_a_healthy_step_for_one_nothing_needs():
    after = plan_of([], ["members", "lending", "space", "tools", "money"])
    assert repair.rejected(plan_of([], FULL_LIST), after) == "it dropped steps nothing was wrong with: safety"


def test_a_list_with_room_cannot_lose_a_healthy_step_to_a_prerequisite():
    entry = plan_of(PREREQUISITE, ["members", "lending", "space"])
    after = plan_of(PREREQUISITE, ["members", "money", "space"])
    assert repair.rejected(entry, after) == "it dropped steps nothing was wrong with: lending"


# -- healthy steps stay word for word -------------------------------------


def test_a_repair_cannot_rewrite_a_healthy_step(tmp_path):
    kept = {"topic": "tools", "action": "Buy tools.", "why": "Later."}
    bad = {"steps": [step("lending"), step("members"), kept]}
    answer = {
        "edges": GOOD_EDGES,
        "steps": [step("members"), step("lending"), {**kept, "action": "Sell the building."}],
    }
    tree = tmp_path / "tree"
    job, _, _ = run(tree, answer, start=bad)
    assert Plan.load(tree).steps[-1].action == "Buy tools."
    assert "it rewrote steps nothing was wrong with: tools" in runbook(tree)
    assert "repair_rejected" in kinds(job)


@pytest.mark.parametrize("field", ["action", "why"])
def test_either_text_of_a_healthy_step_is_compared(field):
    entry = plan_of(GOOD_EDGES, ["tools"])
    after = entry.revised(steps=[entry.steps[0].model_copy(update={field: "Something else."})])
    assert repair.rejected(entry, after) == "it rewrote steps nothing was wrong with: tools"


def test_a_step_at_fault_may_be_reworded():
    entry = plan_of(GOOD_EDGES, ["lending", "members"])
    after = plan_of(GOOD_EDGES, ["members", "lending"])
    moved = after.steps[1].model_copy(update={"action": "Lend one thing."})
    assert repair.rejected(entry, after.revised(steps=[after.steps[0], moved])) == ""


# -- one link per loop, loop by loop --------------------------------------


def test_a_whole_loop_cannot_go_because_another_loop_kept_a_link(tmp_path):
    tree = tmp_path / "tree"
    run(tree, repair_of([edge("tools", "money")], ["members"]), connect={"edges": TWO_LOOPS})
    kept = {(e.from_topic, e.to_topic) for e in Plan.load(tree).edges}
    assert kept & {("lending", "space"), ("space", "lending")}


def test_a_loop_sharing_a_topic_is_judged_on_its_own():
    entry = plan_of(SHARED, ["members"])
    after = plan_of(SHARED[2:], ["members"])
    assert repair.rejected(entry, after) == "it removed every link on the loop, and one is enough"


def test_the_healthy_first_occurrence_of_a_repeated_step_stays():
    entry = plan_of(GOOD_EDGES, ["tools", "money", "tools"])
    assert repair.rejected(entry, plan_of(GOOD_EDGES, ["money"])) == "it dropped steps nothing was wrong with: tools"


# -- a repair may not leave more wrong than it found ----------------------


def test_a_repair_that_makes_the_count_worse_is_rejected_and_the_plan_stays(tmp_path):
    tree = tmp_path / "tree"
    worse = repair_of([*GOOD_EDGES, *LOOP], ["lending", "members"])
    job, _, result = run(tree, worse, start=OUT_OF_ORDER)
    assert not result.ok and result.stage == "start_order"
    assert "it left more wrong than it found" in runbook(tree)
    assert len(Plan.load(tree).edges) == len(GOOD_EDGES)
    assert kinds(job).count("repair_rejected") == 1


def test_the_floor_is_never_worse_than_what_repair_started_with(tmp_path):
    tree = tmp_path / "tree"
    even = repair_of(GOOD_EDGES, ["lending", "members", "space"])
    worse = repair_of([*GOOD_EDGES, *LOOP], ["lending", "members", "space"])
    _, _, result = run(tree, even, worse, start=OUT_OF_ORDER)
    assert sum(len(check.problems) for check in result.failed) == 1


# -- what a repair says about its steps -----------------------------------


def test_a_repair_that_only_rewords_a_step_says_so_and_claims_no_reorder():
    entry = plan_of(GOOD_EDGES, ["lending", "members"])
    moved = entry.steps[0].model_copy(update={"why": "Said better."})
    assert repair.changes(entry, entry.revised(steps=[moved, entry.steps[1]])) == "reworded lending"


def test_a_repair_that_moves_and_rewords_says_both():
    entry = plan_of(GOOD_EDGES, ["lending", "members"])
    moved = entry.steps[0].model_copy(update={"why": "Said better."})
    said = repair.changes(entry, entry.revised(steps=[entry.steps[1], moved]))
    assert said == "steps now members, lending; reworded lending"


# -- what a repair is labelled with ---------------------------------------


def test_a_repair_is_labelled_with_the_check_it_worked_on_not_the_first_red(tmp_path):
    tree = tmp_path / "tree"
    job, _, _ = reviewed(tree, unfixable_too, SLUGS, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    assert "1. attempt 1 (start_order): steps now members, lending" in runbook(tree)
    assert [e["stage"] for e in job.events if e["kind"] == "repair_started"] == ["start_order"]
