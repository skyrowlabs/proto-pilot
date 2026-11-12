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
    assert pipeline.run_plan(job_for(), tree).ok
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


# -- proto answer ---------------------------------------------------------

QUESTIONS = ["Who runs it?", "Which town?"]


def questioned(tree: Path) -> Path:
    """An offline plan holding two open questions, drawn as `proto plan` would draw it."""
    Plan.load(offline_plan(tree)).revised(questions=QUESTIONS).save(tree)
    assert pipeline.rerender(job_for(), tree).ok
    return tree


def changed(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


@pytest.fixture
def no_backend(monkeypatch):
    """Building any backend fails the test that tried."""

    def refuse(**_: object):
        raise AssertionError("a backend was built")

    monkeypatch.setattr(cli, "build_llm", refuse)


def dying_write(monkeypatch, name: str = "PLAN.md") -> None:
    """The first write of `name` fails, as a full disk would, and every later one works."""
    real, armed = Path.write_text, [True]

    def dies(self, text, *args, **kwargs):
        if self.name == name and armed and armed.pop():
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)


def test_an_answer_becomes_a_constraint_and_only_the_entry_page_moves(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "2", "--dir", str(tree), input="One town only\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert (plan.constraints, plan.questions) == (["Which town? One town only"], ["Who runs it?"])
    assert changed(before, snapshot(tree)) == [".protopilot/plan.json", "PLAN.md"]
    assert "- Which town? One town only" in (tree / "PLAN.md").read_text(encoding="utf-8")
    assert "1 answer(s) are constraints now, and 1 question(s) stay open." in said(result)


def test_with_no_number_each_question_is_asked_and_enter_leaves_one_open(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    result = invoke("answer", "--dir", str(tree), input="\nOne town only\n")
    assert result.exit_code == 0, result.output
    assert "1. Who runs it?" in said(result) and "2. Which town?" in said(result)
    assert Plan.load(tree).questions == ["Who runs it?"]


def test_an_answer_reruns_no_pass_and_leaves_every_topic_as_it_was(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    before = Plan.load(tree)
    assert invoke("answer", "1", "--dir", str(tree), input="Volunteers\n").exit_code == 0
    after = Plan.load(tree)
    assert (after.topics, after.edges, after.steps, after.dreams) == (
        before.topics,
        before.edges,
        before.steps,
        before.dreams,
    )


@pytest.mark.parametrize("typed", ["\n", "   \n"], ids=["enter", "spaces"])
def test_no_answer_changes_nothing_and_is_not_an_error(tmp_path, no_backend, typed):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "1", "--dir", str(tree), input=typed)
    assert result.exit_code == 0 and "No answer was given" in said(result)
    assert snapshot(tree) == before


def test_a_plan_with_no_open_question_says_so_and_exits_zero(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "--dir", str(tree))
    assert result.exit_code == 0 and "no open question" in said(result)
    assert snapshot(tree) == before


def test_a_number_past_the_last_question_is_refused(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    result = invoke("answer", "3", "--dir", str(tree))
    assert result.exit_code == 1 and "there is no question 3" in said(result)


def test_answer_refuses_a_folder_with_no_plan_and_a_plan_that_is_red(tmp_path, no_backend):
    empty = invoke("answer", "--dir", str(tmp_path))
    assert empty.exit_code == 1 and "there is nothing here to revise" in said(empty)
    tree = questioned(tmp_path / "tree")
    plan = Plan.load(tree)
    plan.revised(steps=list(reversed(plan.steps))).save(tree)
    red = invoke("answer", "1", "--dir", str(tree), input="x\n")
    assert red.exit_code == 1 and "fails its checks" in said(red)


def test_a_question_closed_while_the_answer_was_typed_is_refused(tmp_path):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="not an open question"):
        pipeline.answer(job_for(), tree, {"Who pays?": "Nobody"})
    with pytest.raises(pipeline.PlanRefused, match="No answer was given"):
        pipeline.answer(job_for(), tree, {"Who runs it?": " "})
    assert snapshot(tree) == before


def test_an_answer_that_cannot_be_drawn_puts_the_tree_back(tmp_path, monkeypatch):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.answer(job_for(), tree, {"Who runs it?": "Volunteers"})
    assert snapshot(tree) == before
