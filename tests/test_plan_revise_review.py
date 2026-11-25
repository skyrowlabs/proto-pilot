"""What the review of the revise verbs found: a paid answer kept, repair told the truth, refusals that say what is left."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeLLM
from plan_script import IDEA, NO_REPAIR, edge, repair_of, script, step
from research_script import OTHER, ResearchingLLM, assumed, cited, fetched, transcript

from protopilot.jobs import Job
from protopilot.llm import LLMError, OfflineLLM
from protopilot.plan import ledger, pipeline
from protopilot.plan.model import Plan
from protopilot.plan.passes import consider, repair

pytestmark = [pytest.mark.unit]

AGAIN = transcript([cited("Loans run a week.", url=OTHER, title="Cover"), assumed()], [fetched(OTHER)])
UNUSABLE = transcript(result={"type": "result", "subtype": "success", "structured_output": {"findings": "many"}})


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def landed(tree: Path, llm: FakeLLM | None = None) -> Path:
    assert pipeline.run_plan(job_for(), tree, llm or ResearchingLLM(script(), {})).ok
    return tree


def noted(slug: str = "members") -> dict:
    return {"topics": [{"slug": slug, "risks": ["new r"], "unknowns": ["new u?"], "decisions": ["new d"]}]}


def test_an_answer_research_cannot_use_is_kept_apart_and_the_refusal_says_where(tmp_path):
    tree = landed(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="cannot be used") as refused:
        pipeline.research_topic(job_for(), tree, "members", ResearchingLLM([], {"members": UNUSABLE}))
    kept = f"{ledger.RESEARCH_DIR}/{ledger.refused_name('members', 1)}"
    assert f"Its stream is kept at {kept}." in str(refused.value)
    assert (tree / kept).read_text(encoding="utf-8") == UNUSABLE
    assert {k: v for k, v in snapshot(tree).items() if k != kept} == before


def test_a_plan_run_keeps_the_stream_of_an_answer_it_cannot_use(tmp_path):
    tree = landed(tmp_path / "tree", ResearchingLLM(script(), {"tools": UNUSABLE}))
    record = Plan.load(tree).research_of("tools")
    assert record is not None and record.state == "failed" and "its stream is kept at" in record.failure
    assert (ledger.research_dir(tree) / ledger.refused_name("tools", 1)).is_file()


def test_after_a_drop_starts_the_steps_again_repair_is_told_no_step_is_settled(tmp_path):
    tree = landed(tmp_path / "tree", FakeLLM(script()))
    Plan.load(tree).revised(edges=[edge("lending", "space")]).save(tree)
    llm = FakeLLM([{"steps": [step("lending")]}, repair_of([edge("lending", "space")], ["space", "lending"])])
    assert pipeline.drop_topic(job_for(), tree, "members", "Known.", lambda: llm).ok
    told = llm.calls[1]["user"]
    assert repair.RESTARTED_RULE.splitlines()[0] in told and "A person has just changed" not in told


@pytest.mark.parametrize("title", ["What it takes", "  what IT takes "], ids=["same", "other-case-and-spacing"])
def test_an_added_topic_with_a_title_another_has_is_refused_as_a_rename_is(tmp_path, title):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree).ok
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="the topic resources is already called 'What it takes'"):
        pipeline.add_topic(job_for(), tree, title, "Why not.", OfflineLLM())
    assert snapshot(tree) == before


def test_a_research_that_lands_red_says_its_transcript_is_kept_for_a_rerun(tmp_path):
    tree = landed(tmp_path / "tree")
    loop = [edge("members", "lending"), edge("lending", "members")]
    llm = ResearchingLLM([{"edges": loop}, noted(), NO_REPAIR], {"members": AGAIN})
    with pytest.raises(pipeline.PlanRefused, match="failed its checks") as refused:
        pipeline.research_topic(job_for(), tree, "members", llm)
    assert pipeline.KEPT.strip() in str(refused.value)


def test_a_replayed_research_lists_no_file_as_written(tmp_path):
    tree = landed(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused):
        pipeline.research_topic(job_for(), tree, "members", ResearchingLLM([NO_REPAIR], {"members": AGAIN}))
    job = job_for()
    edges = [link for link in script()[2]["edges"] if "members" in (link["from_topic"], link["to_topic"])]
    asked = ResearchingLLM([{"edges": edges}, noted()], {"members": LLMError("asked again, not replayed")})
    assert pipeline.research_topic(job, tree, "members", asked).ok
    assert any("replayed from the transcript" in line for line in job.lines)
    assert not any("file(s): .protopilot/research/" in line for line in job.lines)


def test_consider_narrowed_to_one_topic_shows_the_others_notes(tmp_path):
    assert pipeline.run_plan(job_for(), tmp_path / "tree").ok
    plan = Plan.load(tmp_path / "tree")
    other = next(t for t in plan.topics if t.slug != "members" and t.risks)
    assert other.risks[0] in consider.build(plan, only="members")[1]


def test_research_on_the_api_backend_names_only_the_backend_to_use(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from protopilot import cli
    from protopilot.llm import API_RESEARCH, API_RESEARCH_ONE

    class Api(FakeLLM):
        research_refusal = API_RESEARCH

    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree).ok
    monkeypatch.setattr(cli, "build_llm", lambda **_: Api([]))
    result = CliRunner().invoke(cli.main, ["research", "scope", "--dir", str(tree)])
    assert result.exit_code == 1 and "--no-research" not in result.output
    assert API_RESEARCH_ONE in " ".join(result.output.split())
