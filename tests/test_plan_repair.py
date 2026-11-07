"""The repair loop on a fake model: what it may touch, when it stops, and what the floor leaves."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, edge, repair_of, script, step

from protopilot import cli
from protopilot.console import progress
from protopilot.jobs import Job
from protopilot.llm import OfflineLLM
from protopilot.plan import baseline, pipeline, render, verify
from protopilot.plan.model import Dream, Finding, Plan, Source, Step
from protopilot.plan.passes import PlanPassError, repair

pytestmark = [pytest.mark.unit]

GOOD_EDGES = GOOD["connect"]["edges"]
LOOP = [edge("lending", "space"), edge("space", "lending"), edge("tools", "lending")]
MENDED = [edge("lending", "space"), edge("tools", "lending")]
OUT_OF_ORDER = {"steps": [step("lending"), step("members")]}
IN_ORDER = ["members", "lending"]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def run(tree: Path, *repairs: dict, **overrides: object) -> tuple[Job, FakeLLM, verify.PlanVerdict]:
    job, llm = job_for(), FakeLLM([*script(**overrides), *repairs])
    return job, llm, pipeline.run_plan(job, tree, llm)


def kinds(job: Job) -> list[str]:
    return [event["kind"] for event in job.events]


def labels(llm: FakeLLM) -> list[str]:
    return [call["label"] for call in llm.calls]


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


# -- a repair that works --------------------------------------------------


def test_a_bad_order_reaches_repair_and_a_good_repair_goes_green(tmp_path):
    tree = tmp_path / "tree"
    job, llm, result = run(tree, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    assert result.ok
    assert labels(llm)[-1] == "repair"
    assert [s.topic for s in Plan.load(tree).steps] == IN_ORDER
    assert not (tree / "RUNBOOK.md").exists()
    assert job.events[-1]["ok"] is True and job.events[-1]["attempts"] == 2


def test_a_partial_cycle_reaches_repair_and_a_good_repair_goes_green(tmp_path):
    tree = tmp_path / "tree"
    _, llm, result = run(tree, repair_of(MENDED, ["members"]), connect={"edges": LOOP})
    assert result.ok
    assert verify.cycle_edges(Plan.load(tree)) == []


def test_repair_is_fed_the_failing_check_and_what_it_said(tmp_path):
    _, llm, _ = run(tmp_path / "tree", repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    told = llm.calls[-1]["user"]
    assert "[start_order]" in told and "step 1 (lending) waits on members" in told
    assert '"from_topic": "lending"' in told and '"topic": "members"' in told


def test_a_green_plan_makes_no_repair_call(tmp_path):
    _, llm, result = run(tmp_path / "tree")
    assert result.ok and "repair" not in labels(llm)


def test_the_console_fold_counts_a_repair(tmp_path):
    job, _, _ = run(tmp_path / "tree", repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    folded = progress.fold(job.events)
    assert (folded.repairs, folded.verify_attempt, folded.verify_state) == (1, 2, progress.DONE)
    assert folded.finished and folded.ok


# -- what a repair may not do ---------------------------------------------

FORGED = {
    "researched": True,
    "sources": [{"id": "s1", "title": "A study", "url": "https://example.com", "fetched": True}],
    "topics": [{"slug": "members", "findings": [{"text": "Proven.", "assumption": False, "source_ids": ["s1"]}]}],
    "findings": [{"text": "Proven.", "assumption": False, "source_ids": ["s1"]}],
    "dreams": [{"id": "d", "title": "t", "what_if": "w", "lens": "l", "anchor": "members", "takes": "x"}],
}


def test_a_repair_cannot_reach_anything_but_edges_and_steps(tmp_path):
    tree = tmp_path / "tree"
    forged = {**repair_of(GOOD_EDGES, IN_ORDER), **FORGED}
    forged["steps"] = [{**row, **FORGED} for row in forged["steps"]]
    _, _, result = run(tree, forged, start=OUT_OF_ORDER)
    plan = Plan.load(tree)
    assert result.ok
    assert (plan.researched, plan.sources, plan.dreams) == (False, [], [])
    assert [t.findings for t in plan.topics] == [[] for _ in plan.topics]
    assert render.NOT_RESEARCHED in (tree / "PLAN.md").read_text(encoding="utf-8")


def test_a_repair_naming_a_ghost_topic_stops_the_loop_at_the_floor(tmp_path):
    tree = tmp_path / "tree"
    job, llm, result = run(tree, repair_of([edge("ghost", "members")], IN_ORDER), start=OUT_OF_ORDER)
    assert not result.ok
    assert labels(llm).count("repair") == 1
    assert "repair_failed" in kinds(job)
    assert "the repair pass failed" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def test_a_repair_with_an_unsafe_step_slug_writes_no_path_of_its_own(tmp_path):
    tree = tmp_path / "tree"
    bad = repair_of(GOOD_EDGES, ["../../evil"])
    _, _, result = run(tree, bad, start=OUT_OF_ORDER)
    assert not result.ok
    assert sorted(p.name for p in tmp_path.iterdir()) == ["tree"]


def test_a_repair_that_fixes_one_check_and_breaks_another_stays_red(tmp_path):
    tree = tmp_path / "tree"
    two_faults = {"steps": [step("lending"), step("members"), step("lending")]}
    _, llm, result = run(tree, repair_of(GOOD_EDGES + LOOP, ["members"]), start=two_faults)
    assert not result.ok
    assert result.stage == "no_cycles"
    assert labels(llm).count("repair") == 2  # the second had no scripted answer


def test_a_later_repair_can_land_after_one_that_broke_more_is_thrown_away(tmp_path):
    broke = repair_of(GOOD_EDGES + LOOP, ["members"])
    mended = repair_of(GOOD_EDGES + MENDED, ["members"])
    _, _, result = run(tmp_path / "tree", broke, mended, start=OUT_OF_ORDER)
    assert result.ok


def test_a_repair_that_bends_the_graph_to_fit_the_steps_is_thrown_away(tmp_path):
    tree = tmp_path / "tree"
    bent = {"edges": [GOOD_EDGES[1]], "steps": OUT_OF_ORDER["steps"]}
    job, _, result = run(tree, bent, start=OUT_OF_ORDER)
    assert not result.ok and "repair_rejected" in kinds(job)
    assert "removed edges on no loop: lending depends-on members" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")
    assert len(Plan.load(tree).edges) == len(GOOD_EDGES)


def test_a_repair_that_drops_a_step_nothing_was_wrong_with_is_thrown_away(tmp_path):
    tree = tmp_path / "tree"
    repeated = {"steps": [step("members"), step("lending"), step("tools"), step("tools")]}
    job, _, result = run(tree, repair_of(GOOD_EDGES, ["members"]), start=repeated)
    assert not result.ok and "repair_rejected" in kinds(job)
    assert "dropped steps nothing was wrong with: lending" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def test_a_repair_that_empties_a_loop_of_every_link_is_thrown_away(tmp_path):
    tree = tmp_path / "tree"
    job, _, result = run(tree, repair_of([edge("tools", "lending")], ["members"]), connect={"edges": LOOP})
    assert not result.ok
    assert progress.fold(job.events).rejected == 1
    assert [e.to_topic for e in Plan.load(tree).edges] == ["space", "lending", "lending"]


def test_a_rejected_repair_is_told_why_on_the_next_attempt(tmp_path):
    bad = repair_of([], ["lending"])
    bad["steps"] = OUT_OF_ORDER["steps"]
    _, llm, result = run(tmp_path / "tree", bad, repair_of(GOOD_EDGES, IN_ORDER), start=OUT_OF_ORDER)
    assert result.ok
    assert "Your last repair was thrown away: it removed edges on no loop" in llm.calls[-1]["user"]


def with_edges(plan: Plan, edges: list[dict]) -> Plan:
    return repair.apply(plan, {"edges": edges, "steps": [s.model_dump() for s in plan.steps]})


def test_a_repair_that_retypes_one_link_of_a_loop_is_allowed():
    plan = with_edges(baseline.build_plan(IDEA), [edge("scope", "risks"), edge("risks", "scope")])
    after = with_edges(plan, [edge("scope", "risks"), edge("risks", "scope", "informs")])
    assert repair.rejected(plan, after) == ""


# -- the bound ------------------------------------------------------------


def test_repair_stops_at_three_attempts_and_verifies_a_fourth_time(tmp_path):
    growing = ["lending", "members", "space", "tools", "money"]
    keeps_failing = [repair_of(GOOD_EDGES, growing[:count]) for count in (3, 4, 5)]
    job, llm, result = run(tmp_path / "tree", *keeps_failing, start=OUT_OF_ORDER)
    assert not result.ok
    assert labels(llm).count("repair") == repair.ATTEMPTS
    assert kinds(job).count("verify_started") == repair.ATTEMPTS + 1
    assert kinds(job)[-2:] == ["pass_done", "finished"]
    assert job.events[-1]["attempts"] == repair.ATTEMPTS + 1
    assert "exhausted" in kinds(job)


def test_a_repair_that_changes_nothing_stops_the_loop(tmp_path):
    same = {"edges": GOOD_EDGES, "steps": OUT_OF_ORDER["steps"]}
    job, llm, result = run(tmp_path / "tree", same, start=OUT_OF_ORDER)
    assert not result.ok
    assert labels(llm).count("repair") == 1 and "repair_empty" in kinds(job)


class Backendless(FakeLLM):
    """Good for the passes, and dead the moment repair calls."""

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == "repair":
            raise RuntimeError("the backend went away")
        return super().structured(system=system, user=user, schema=schema, label=label)


def test_a_backend_that_dies_in_repair_still_hands_the_tree_back(tmp_path):
    tree, job = tmp_path / "tree", job_for()
    assert not pipeline.run_plan(job, tree, Backendless(script(start=OUT_OF_ORDER))).ok
    assert "the backend went away" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")
    assert [s.topic for s in Plan.load(tree).steps] == ["lending", "members"]


def cyclic() -> Plan:
    return with_edges(baseline.build_plan(IDEA), [edge("risks", "scope"), edge("scope", "risks")])


def test_the_offline_twin_changes_nothing_and_stops_the_loop_saying_so():
    job = job_for()
    checked = pipeline.repaired(job, cyclic(), OfflineLLM())
    assert not checked.verdict.ok
    assert checked.attempts == 1
    assert "offline mode cannot repair" in checked.tried[0]
    assert kinds(job) == ["verify_started", "verify_failed", "repair_started", "repair_empty", "exhausted"]


# -- checks repair cannot reach -------------------------------------------


def hand_built(**changes: object) -> Plan:
    return baseline.build_plan(IDEA).revised(**changes)


TYPED_SOURCE = Source(id="s1", title="A study", url="https://example.com")
UNEVALUATED = Dream(id="d1", title="Seeds", what_if="it lent seeds", lens="l", anchor="audience", takes="A shelf")


@pytest.mark.parametrize(
    ("plan", "stage"),
    [(hand_built(sources=[TYPED_SOURCE]), "sources_fetched"), (hand_built(dreams=[UNEVALUATED]), "dreams_shaped")],
    ids=["source", "dream"],
)
def test_a_failure_repair_cannot_reach_makes_no_call_and_goes_to_the_floor(tmp_path, plan, stage):
    tree, job, llm = tmp_path / "tree", job_for(), FakeLLM([])
    llm.offline = True  # the twin's passes rebuild the plan's edges and steps, which is all this needs
    result = pipeline.build(job, tree, plan, llm)
    assert not result.ok and result.stage == stage
    assert llm.calls == []
    assert "repair_started" not in kinds(job)
    assert "repair cannot reach" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def test_a_finding_with_no_source_cannot_be_green_by_any_repair():
    first = baseline.build_plan(IDEA).topics[0]
    finding = Finding(text="It is so.", assumption=False)
    plan = hand_built(topics=[first.model_copy(update={"findings": [finding]})], edges=[], steps=[])
    plan = plan.revised(steps=[Step(topic=first.slug, action="Do.", why="Now.")])
    assert repair.fixable(verify.verdict(plan, render.render(plan))) == []


# -- the floor ------------------------------------------------------------


@pytest.fixture
def red_tree(tmp_path) -> tuple[Path, Job]:
    tree = tmp_path / "tree"
    job, _, result = run(tree, connect={"edges": LOOP})
    assert not result.ok
    return tree, job


def test_the_floor_writes_the_whole_tree_and_a_runbook(red_tree):
    tree, _ = red_tree
    names = {str(p.relative_to(tree)) for p in tree.rglob("*") if p.is_file()}
    assert {"PLAN.md", "RUNBOOK.md", "dreams.md", "sources.md", ".protopilot/plan.json"} <= names
    said = (tree / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "Nothing here is verified" in said and "[no_cycles]" in said
    assert "lending depends on space, and that link is on a loop" in said
    assert "- sources_fetched: The plan has no sources to check." in said


def test_the_floor_keeps_the_stamp_and_reads_as_unverified_everywhere(red_tree):
    tree, job = red_tree
    entry = (tree / "PLAN.md").read_text(encoding="utf-8")
    assert render.NOT_RESEARCHED in entry and render.NOT_VERIFIED in entry
    assert "RUNBOOK.md" in job.lines[-1]
    assert not any(line.startswith("Green") for line in job.lines)
    assert not any(line.startswith("Plan at") for line in job.lines)
    assert job.events[-1]["kind"] == "finished" and job.events[-1]["ok"] is False


def test_the_console_fold_reads_the_floor_as_gave_up(red_tree):
    _, job = red_tree
    folded = progress.fold(job.events)
    assert folded.gave_up and folded.stage == "no_cycles"


def test_a_red_plan_exits_non_zero_from_the_cli(tmp_path, monkeypatch):
    llm = FakeLLM(script(connect={"edges": LOOP}))
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    tree = tmp_path / "tree"
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--yes", "--dir", str(tree)])
    assert result.exit_code == 1
    assert "Not verified: red at no_cycles" in result.output
    assert "RUNBOOK.md" in result.output
    assert "Green" not in result.output


def test_a_green_plan_prints_the_limit_and_exits_zero(tmp_path, monkeypatch):
    llm = FakeLLM(script())
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--yes", "--dir", str(tmp_path / "tree")])
    said = " ".join(result.output.split())
    assert result.exit_code == 0
    assert "coherent and traceable, which is not the same as true" in said
    assert "No subject, so these proved nothing: findings_traced, sources_fetched" in said


def test_a_page_that_did_not_land_is_red_though_the_plan_drew_green(tmp_path, monkeypatch):
    real = render.write

    def drops_a_page(plan: Plan, tree: Path, runbook: str = "") -> list[str]:
        written = real(plan, tree, runbook)
        if not runbook:
            (Path(tree) / "topics" / "members.md").unlink()
        return written

    monkeypatch.setattr(render, "write", drops_a_page)
    tree = tmp_path / "tree"
    job, _, result = run(tree)
    assert not result.ok and result.stage == "topic_map"
    assert "topics/members.md is missing" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")
    assert job.events[-1]["ok"] is False


# -- a re-render re-verifies ----------------------------------------------


def rerun(tree: Path) -> tuple[Job, verify.PlanVerdict]:
    job = job_for()
    return job, pipeline.run_plan(job, tree, FakeLLM([]))


def test_a_rerender_of_a_red_plan_stays_red_with_no_model_call(red_tree):
    tree, _ = red_tree
    job, result = rerun(tree)
    assert not result.ok
    assert "repair_started" not in kinds(job)
    assert "A re-render calls no model" in (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def test_a_rerender_of_a_red_plan_is_byte_stable(red_tree):
    tree, _ = red_tree
    rerun(tree)
    first = snapshot(tree)
    rerun(tree)
    assert snapshot(tree) == first


def test_a_rerender_finds_a_fault_planted_in_plan_json_and_exits_one(tmp_path):
    tree = tmp_path / "tree"
    assert CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)]).exit_code == 0
    plan = Plan.load(tree)
    plan.steps = [plan.steps[1], plan.steps[0]]
    plan.edges = [*plan.edges, *[e.model_copy(update={"to_topic": "ghost"}) for e in plan.edges[:1]]]
    plan.save(tree)
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 1
    assert "Not verified: red at topic_map" in result.output
    assert (tree / "RUNBOOK.md").is_file()


def test_a_plan_fixed_by_hand_goes_green_and_loses_its_runbook_and_its_banner(red_tree):
    tree, _ = red_tree
    plan = Plan.load(tree)
    plan.edges = [e for e in plan.edges if e.from_topic != "space"]
    plan.save(tree)
    _, result = rerun(tree)
    assert result.ok
    assert not (tree / "RUNBOOK.md").exists()
    assert render.NOT_VERIFIED not in (tree / "PLAN.md").read_text(encoding="utf-8")


def test_a_runbook_named_directory_blocks_the_floor_with_a_sentence(red_tree):
    tree, _ = red_tree
    (tree / "RUNBOOK.md").unlink()
    (tree / "RUNBOOK.md").mkdir()
    with pytest.raises(pipeline.PlanRefused, match="a page needs this name"):
        rerun(tree)


def test_the_golden_offline_run_writes_no_runbook(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree).ok
    assert not (tree / "RUNBOOK.md").exists()


def test_planpasserror_is_still_what_a_malformed_start_raises(tmp_path):
    bad = copy.deepcopy(GOOD["start"])
    bad["steps"][0]["topic"] = "ghost"
    with pytest.raises(PlanPassError, match="does not exist"):
        run(tmp_path / "tree", start=bad)
    assert list(tmp_path.iterdir()) == []
