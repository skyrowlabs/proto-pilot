"""A research stream whose answer was not used: kept apart, never evidence, and asked once more after a slip (#56).

The research call is the real `ClaudeCodeLLM.research`, fed by a scripted runner, so the
refusal and the retry are the ones a live run takes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plan_script import IDEA, script
from research_script import ResearchingLLM, transcript

from protopilot.jobs import Job
from protopilot.llm import ClaudeCodeLLM, LLMError, Researched
from protopilot.plan import ledger, pipeline
from protopilot.plan.model import Plan
from protopilot.runner import CommandResult

pytestmark = [pytest.mark.unit]

TOPIC = "money"


def stray(name: str = "text") -> str:
    """A good answer that also calls a tool the session never held, as the run in #56 did."""
    events = [json.loads(line) for line in transcript().splitlines()]
    use = {"type": "tool_use", "id": "toolu_x", "name": name, "input": {}}
    events.insert(1, {"type": "assistant", "message": {"content": [use]}})
    return "\n".join(json.dumps(event) for event in events) + "\n"


class Streams:
    """Answers the research call for `TOPIC` with each (code, stdout, stderr) in turn, then a good stream."""

    def __init__(self, *said: tuple[int, str, str]) -> None:
        self.said, self.asked = list(said), 0

    def run(self, argv, cwd=None, timeout=None):  # noqa: ANN001, ANN201
        self.asked += 1
        code, stdout, stderr = self.said.pop(0) if self.said else (0, transcript(), "")
        return CommandResult(list(argv), code, stdout, stderr)


class Live(ResearchingLLM):
    def __init__(self, streams: Streams, responses: list | None = None) -> None:
        super().__init__(script() if responses is None else responses, {})
        self.streams = streams

    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched:
        if label.endswith(f" {TOPIC}"):
            return ClaudeCodeLLM(runner=self.streams).research(system=system, user=user, schema=schema, label=label)
        return super().research(system=system, user=user, schema=schema, label=label)


def planned(tree: Path, *said: tuple[int, str, str]) -> tuple[Plan, Streams, Job]:
    streams, job = Streams(*said), Job(id="test", idea=IDEA)
    pipeline.run_plan(job, tree, Live(streams))  # type: ignore[arg-type]
    return Plan.load(tree), streams, job


def kept(tree: Path) -> list[str]:
    return sorted(p.name for p in ledger.research_dir(tree).glob(f"{TOPIC}.*"))


def test_a_stray_tool_is_refused_and_its_stream_kept_where_no_reader_of_evidence_looks(tmp_path):
    tree = tmp_path / "tree"
    plan, streams, _ = planned(tree, (0, stray(), ""), (0, stray(), ""))
    record = plan.research_of(TOPIC)
    assert record is not None and record.state == "failed" and "used text" in record.failure
    assert record.transcript == "" and ledger.read_transcript(tree, TOPIC) is None
    assert kept(tree) == [ledger.refused_name(TOPIC, 1), ledger.refused_name(TOPIC, 2)]
    assert f"kept at {ledger.RESEARCH_DIR}/{ledger.refused_name(TOPIC, 2)}" in record.failure
    assert (ledger.research_dir(tree) / ledger.refused_name(TOPIC, 1)).read_text(encoding="utf-8") == stray()
    assert streams.asked == 2


def test_one_slip_is_asked_once_more_and_the_second_answer_is_used(tmp_path):
    tree = tmp_path / "tree"
    plan, streams, job = planned(tree, (0, stray(), ""))
    assert plan.research_of(TOPIC).state == "researched"  # type: ignore[union-attr]
    assert streams.asked == 2 and kept(tree) == sorted([ledger.refused_name(TOPIC, 1), ledger.transcript_name(TOPIC)])
    assert any("asking once more" in line for line in job.lines)


def test_a_reconciled_plan_never_counts_a_kept_refusal_as_evidence(tmp_path):
    tree = tmp_path / "tree"
    plan, _, _ = planned(tree, (0, stray(), ""), (0, stray(), ""))
    redrawn = ledger.reconciled(plan, tree).research_of(TOPIC)
    assert redrawn is not None and redrawn.state == "failed" and redrawn.fetches == []


def test_a_session_that_held_a_shell_is_not_asked_again(tmp_path):
    tree = tmp_path / "tree"
    shell = transcript(tools=["StructuredOutput", "WebFetch", "WebSearch", "Bash"])
    plan, streams, _ = planned(tree, (0, shell, ""))
    assert streams.asked == 1 and plan.research_of(TOPIC).state == "failed"  # type: ignore[union-attr]
    assert kept(tree) == [ledger.refused_name(TOPIC, 1)]


def test_a_timeout_is_not_asked_again(tmp_path):
    tree = tmp_path / "tree"
    plan, streams, _ = planned(tree, (124, "", "[timed out after 2700.0s]"))
    record = plan.research_of(TOPIC)
    assert streams.asked == 1 and record is not None and "timed out" in record.failure and kept(tree) == []


def test_a_failed_process_reports_its_result_events_error_not_the_streams_tail(tmp_path):
    tree = tmp_path / "tree"
    error = {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "overloaded"}
    usage = {"type": "result_usage", "usage": {"outputTokens": 0, "costUSD": 0.0958, "pad": "x" * 600}}
    failed = transcript(result=error) + json.dumps(usage) + "\n"
    plan, _, _ = planned(tree, (1, failed, ""), (1, failed, ""))
    record = plan.research_of(TOPIC)
    assert record is not None and "failed: overloaded" in record.failure and "costUSD" not in record.failure


def test_a_resumed_run_adds_kept_streams_and_never_overwrites_the_first_runs(tmp_path):
    tree, down = tmp_path / "tree", LLMError("the backend went away")
    with pytest.raises(LLMError):
        pipeline.run_plan(
            Job(id="t", idea=IDEA), tree, Live(Streams((0, stray(), ""), (0, stray(), "")), script(connect=down))
        )
    first = {name: (ledger.research_dir(tree) / name).read_bytes() for name in kept(tree)}
    assert sorted(first) == [ledger.refused_name(TOPIC, 1), ledger.refused_name(TOPIC, 2)]
    again = Live(Streams((0, stray("other"), ""), (0, stray("other"), "")), script()[2:])
    pipeline.run_plan(Job(id="t", idea=IDEA), tree, again)  # type: ignore[arg-type]
    assert kept(tree) == [ledger.refused_name(TOPIC, n) for n in (1, 2, 3, 4)]
    assert all((ledger.research_dir(tree) / name).read_bytes() == said for name, said in first.items())


def test_next_refused_ignores_evidence_temp_files_symlinks_and_other_topics(tmp_path):
    folder = ledger.research_dir(tmp_path)
    folder.mkdir(parents=True)
    assert ledger.next_refused(tmp_path, TOPIC) == 1
    for name in (ledger.refused_name(TOPIC, 3), ledger.transcript_name(TOPIC), ledger.refused_name("other", 8)):
        (folder / name).write_text("x", encoding="utf-8")
    (folder / f".{ledger.refused_name(TOPIC, 9)}.tmp").write_text("x", encoding="utf-8")
    (folder / ledger.refused_name(TOPIC, 7)).symlink_to(folder / ledger.transcript_name(TOPIC))
    assert ledger.next_refused(tmp_path, TOPIC) == 4
