"""The mark a stopped research try leaves: what makes it replayable, and what happens when it is not."""

from __future__ import annotations

import json

import pytest
from fakes import FakeLLM
from research_script import ResearchingLLM, assumed, cited, transcript
from test_plan_revise_edges import (
    BARE,
    THIRD,
    again,
    asked_again,
    job_for,
    mark_of,
    refit,
    researched_plan,
    stopped,
    unresearched_plan,
)

from protopilot.llm import LLMError
from protopilot.plan import ledger, pipeline
from protopilot.plan.model import Plan
from protopilot.plan.passes import research

pytestmark = [pytest.mark.unit]


def _damaged(tree):
    (ledger.research_dir(tree) / "members.2.jsonl").write_text("garbage\n", encoding="utf-8")


def _depth_typed_down(tree):
    mark = json.loads(mark_of(tree).read_text(encoding="utf-8"))
    mark_of(tree).write_text(json.dumps({**mark, "depth": "shallow"}), encoding="utf-8")


def deeper_try_stopped(tree) -> None:
    Plan.load(tree).revised(depth="shallow").save(tree)
    most = research.EFFORT["standard"][1]
    stopped(tree, said_=transcript([cited(), *(assumed(f"Guess {n}.") for n in range(most - 1))]), deeper=True)


def test_a_marked_try_whose_replay_fails_is_refused_once_and_then_asked_afresh(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    deeper_try_stopped(tree)
    _depth_typed_down(tree)
    with pytest.raises(pipeline.PlanRefused, match="the next run asks again") as refused:
        asked_again(tree)
    assert "a rerun replays it" not in str(refused.value) and not mark_of(tree).exists()
    assert (ledger.research_dir(tree) / "members.2.jsonl").is_file()
    assert asked_again(tree) == (["members"], "members.3.jsonl")


def test_a_marked_try_whose_transcript_was_damaged_is_never_replayed_and_stays_on_disk(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    deeper_try_stopped(tree)
    _damaged(tree)
    job = job_for()
    llm = ResearchingLLM(refit(), {"members": THIRD})
    assert pipeline.research_topic(job, tree, "members", llm).ok
    assert llm.researched == ["members"]
    assert any("not replayed, because its transcript is missing or was altered" in line for line in job.lines)
    assert (ledger.research_dir(tree) / "members.2.jsonl").read_text(encoding="utf-8") == "garbage\n"
    assert Plan.load(tree).research_of("members").transcript == "members.3.jsonl"  # type: ignore[union-attr]


def test_a_stopped_try_says_when_a_rerun_will_not_replay_it(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused, match="unless that rerun asks for more depth or the plan has changed"):
        again(tree, "members", THIRD, [LLMError("out of credit")])


def test_a_mark_in_the_format_before_hashes_is_not_replayed(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    stopped(tree)
    old = {k: v for k, v in json.loads(mark_of(tree).read_text(encoding="utf-8")).items() if k in OLD_FIELDS}
    mark_of(tree).write_text(json.dumps(old), encoding="utf-8")
    assert asked_again(tree) == (["members"], "members.3.jsonl")


OLD_FIELDS = ("number", "depth", "since")


def test_an_answer_given_after_a_try_stopped_reaches_the_research_that_follows(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    Plan.load(tree).revised(questions=["Who runs it?"]).save(tree)
    assert pipeline.rerender(job_for(), tree).ok
    stopped(tree)
    assert pipeline.answer(job_for(), tree, {"Who runs it?": "Volunteers"}).ok
    seen: list[str] = []

    class Watching(ResearchingLLM):
        def research(self, *, system: str, user: str, schema: dict, label: str):
            seen.append(user)
            return super().research(system=system, user=user, schema=schema, label=label)

    assert pipeline.research_topic(job_for(), tree, "members", Watching(refit(), {"members": THIRD})).ok
    assert seen and "Volunteers" in seen[0]


def test_the_log_says_why_a_stopped_try_was_asked_again(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    stopped(tree)
    assert pipeline.rename_topic(job_for(), tree, "space", "Room").ok
    job = job_for()
    assert pipeline.research_topic(job, tree, "members", ResearchingLLM(refit(), {"members": THIRD})).ok
    assert any("because what research would be asked has changed since; asking again" in line for line in job.lines)


def test_a_mark_for_a_slug_is_cleared_when_a_topic_takes_that_slug(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    stopped(tree, "tools")
    mark = mark_of(tree, "tools").read_bytes()
    assert pipeline.drop_topic(job_for(), tree, "tools", "No.", pipeline.OfflineLLM).ok
    mark_of(tree, "tools").write_bytes(mark)
    # The same title and reason as before, so nothing a fingerprint reads tells the two topics apart.
    assert pipeline.add_topic(job_for(), tree, "Tools", "tools matters", FakeLLM([BARE])).ok
    assert not mark_of(tree, "tools").exists()


def test_a_mark_that_outlived_its_topics_drop_is_not_replayed_for_the_topic_added_again(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    stopped(tree, "tools")
    mark = mark_of(tree, "tools").read_bytes()
    assert pipeline.drop_topic(job_for(), tree, "tools", "No.", pipeline.OfflineLLM).ok
    mark_of(tree, "tools").write_bytes(mark)  # as a stop between the landing and the forgetting leaves it
    assert pipeline.add_topic(job_for(), tree, "Tools", "Another question.", FakeLLM([BARE])).ok
    llm = ResearchingLLM([{"edges": []}, refit("tools")[1]], {"tools": THIRD})
    assert pipeline.research_topic(job_for(), tree, "tools", llm).ok
    assert llm.researched == ["tools"]
