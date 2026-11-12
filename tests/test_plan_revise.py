"""Revising a finished plan: what the outline's edits and the ledger do to one."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from plan_script import IDEA, script
from research_script import ResearchingLLM

from protopilot import cli
from protopilot.jobs import Job
from protopilot.plan import ledger, pipeline, render, verify
from protopilot.plan.model import Plan
from protopilot.plan.passes import outline

pytestmark = [pytest.mark.unit]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def invoke(*args: str, **options: object):
    return CliRunner().invoke(cli.main, list(args), **options)  # type: ignore[arg-type]


def said(result) -> str:
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def offline_plan(tree: Path) -> Path:
    assert invoke("plan", IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    return tree


def researched_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {})).ok
    return tree


def judged(plan: Plan) -> verify.PlanVerdict:
    return verify.verdict(plan, render.render(plan))


# -- what the review's edits do to a finished plan ------------------------


def test_a_rename_on_a_finished_plan_changes_the_title_and_nothing_else(tmp_path):
    before = Plan.load(offline_plan(tmp_path / "tree"))
    after = outline.rename(before, "scope", "The boundary")
    assert [t.slug for t in after.topics] == [t.slug for t in before.topics]
    assert after.topics[1].title == "The boundary"
    assert after.topics[1].model_copy(update={"title": before.topics[1].title}) == before.topics[1]
    assert (after.edges, after.steps, after.dreams, after.research) == (
        before.edges,
        before.steps,
        before.dreams,
        before.research,
    )
    assert judged(after).ok


def test_a_drop_on_a_finished_plan_removes_the_topic_alone_and_leaves_the_plan_red(tmp_path):
    before = Plan.load(offline_plan(tmp_path / "tree"))
    after = outline.drop(before, "audience")
    assert "audience" not in [t.slug for t in after.topics]
    assert (after.edges, after.steps, after.dreams) == (before.edges, before.steps, before.dreams)
    result = judged(after)
    assert result.named(verify.FAILED) == ["topic_map", "start_order", "dreams_shaped"]


# -- which transcript the ledger reads ------------------------------------


def test_the_ledger_is_redrawn_from_the_transcript_each_record_names(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    forged = [r.model_copy(update={"fetches": [], "state": "nothing cited"}) for r in plan.research]
    redrawn = ledger.reconciled(plan.revised(research=[r.model_dump() for r in forged]), tree)
    assert redrawn.research == plan.research


def test_a_record_that_names_another_topics_transcript_has_no_evidence(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    theirs = plan.research_of("lending")
    assert theirs is not None
    borrowed = [
        r.model_copy(update={"transcript": theirs.transcript, "sha256": theirs.sha256}) if r.topic == "members" else r
        for r in plan.research
    ]
    record = ledger.reconciled(plan.revised(research=[r.model_dump() for r in borrowed]), tree).research_of("members")
    assert record is not None
    assert (record.state, record.failure, record.fetches) == ("failed", ledger.NO_EVIDENCE, [])


def test_a_second_transcript_for_a_topic_is_not_one_the_ledger_reads_today(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    said_again = ledger.read_transcript(tree, "members")
    assert said_again is not None
    (ledger.research_dir(tree) / "members.2.jsonl").write_text(said_again, encoding="utf-8")
    moved = [
        r.model_copy(update={"transcript": "members.2.jsonl"}) if r.topic == "members" else r for r in plan.research
    ]
    record = ledger.reconciled(plan.revised(research=[r.model_dump() for r in moved]), tree).research_of("members")
    assert record is not None
    assert (record.state, record.failure) == ("failed", ledger.NO_EVIDENCE)
