"""Revising a plan: which transcript a research replays, and what a drop leaves the plan saying."""

from __future__ import annotations

import pytest
from fakes import FakeLLM
from research_script import ResearchingLLM, assumed, cited, transcript
from test_plan_revise_edges import (
    AGAIN,
    BARE,
    THIRD,
    THIRD_URL,
    NeverAsked,
    again,
    invoke,
    job_for,
    offline_plan,
    refit,
    researched_plan,
    said,
    snapshot,
    stamp,
    unresearched_plan,
)

from protopilot.llm import LLMError
from protopilot.plan import ledger, pipeline, render
from protopilot.plan.model import Plan
from protopilot.plan.passes import research

pytestmark = [pytest.mark.unit]


def test_a_topic_dropped_and_added_again_is_researched_afresh_not_replayed_from_its_old_transcript(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert again(tree, "tools", AGAIN, [{"edges": []}, refit("tools")[1]]).ok  # its record names tools.2.jsonl
    assert pipeline.drop_topic(job_for(), tree, "tools", "No.", pipeline.OfflineLLM).ok
    assert pipeline.add_topic(job_for(), tree, "Tools", "A different question now.", FakeLLM([BARE])).ok
    llm_answers = [{"edges": []}, refit("tools")[1]]
    llm = ResearchingLLM(llm_answers, {"tools": THIRD})
    assert pipeline.research_topic(job_for(), tree, "tools", llm).ok
    plan = Plan.load(tree)
    assert llm.researched == ["tools"]  # today: [], the superseded tools.jsonl is replayed
    assert [f.text for f in plan.topics[-1].findings] == ["Third."]
    assert [f.url for f in plan.research_of("tools").fetches] == [THIRD_URL]  # type: ignore[union-attr]


def test_the_only_researched_topic_of_a_plan_can_be_dropped(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    assert again(tree, "lending").ok
    assert pipeline.drop_topic(job_for(), tree, "lending", "No.", pipeline.OfflineLLM).ok  # today: PlanRefused
    plan = Plan.load(tree)
    assert (plan.researched, plan.sources, plan.research) == (False, [], [])
    assert stamp(tree).startswith(render.NOT_RESEARCHED)


def test_a_deeper_try_that_stopped_does_not_wedge_the_plain_rerun(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    Plan.load(tree).revised(depth="shallow").save(tree)
    most = research.EFFORT["standard"][1]
    big = transcript([cited(), *(assumed(f"Guess {n}.") for n in range(most - 1))])
    with pytest.raises(pipeline.PlanRefused, match="a rerun replays it"):
        again(tree, "members", big, [LLMError("out of credit")], deeper=True)
    before = snapshot(tree)
    # The refusal promised a rerun replays it. Today: "6 findings, past the 4 this depth allows", every time.
    assert pipeline.research_topic(job_for(), tree, "members", NeverAsked(refit())).ok, before.keys()


def test_a_plain_try_that_stopped_is_not_replayed_for_a_deeper_rerun(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    Plan.load(tree).revised(depth="shallow").save(tree)
    with pytest.raises(pipeline.PlanRefused, match="a rerun replays it"):
        again(tree, "members", AGAIN, [LLMError("out of credit")])
    lo, hi, _ = research.EFFORT["standard"]
    seen: list[dict] = []

    class Watching(ResearchingLLM):
        def research(self, *, system: str, user: str, schema: dict, label: str):
            seen.append(schema["properties"]["findings"])
            return super().research(system=system, user=user, schema=schema, label=label)

    big = transcript([cited(), *(assumed(f"Guess {n}.") for n in range(hi - 1))])
    llm = Watching(refit(), {"members": big})
    assert pipeline.research_topic(job_for(), tree, "members", llm, True).ok
    plan = Plan.load(tree)
    assert llm.researched == ["members"] and (seen[0]["minItems"], seen[0]["maxItems"]) == (lo, hi)
    # The plain try's transcript keeps number 2 as a leftover, and the deeper call takes the next.
    assert plan.research_of("members").transcript == "members.3.jsonl"  # type: ignore[union-attr]
    assert len(plan.topics[0].findings) == hi and plan.depth == "shallow"


def test_a_try_that_lands_leaves_no_mark_and_the_next_research_asks_again(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert again(tree, "members", AGAIN).ok
    assert not (ledger.research_dir(tree) / "members.pending.json").exists()
    llm = ResearchingLLM(refit(), {"members": THIRD})
    assert pipeline.research_topic(job_for(), tree, "members", llm).ok
    assert llm.researched == ["members"]
    assert Plan.load(tree).research_of("members").transcript == "members.3.jsonl"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "mark", ["{", '{"number": "x"}', '{"number": 2, "depth": "bottomless", "since": "members.jsonl"}']
)
def test_a_mark_that_cannot_be_read_replays_nothing(tmp_path, mark):
    tree = researched_plan(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused, match="a rerun replays it"):
        again(tree, "members", AGAIN, [LLMError("out of credit")])
    (ledger.research_dir(tree) / "members.pending.json").write_text(mark, encoding="utf-8")
    llm = ResearchingLLM(refit(), {"members": THIRD})
    assert pipeline.research_topic(job_for(), tree, "members", llm).ok
    assert llm.researched == ["members"]
    assert Plan.load(tree).research_of("members").transcript == "members.3.jsonl"  # type: ignore[union-attr]


def test_a_try_that_stopped_before_a_drop_is_not_replayed_for_the_topic_added_again(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused, match="a rerun replays it"):
        again(tree, "tools", AGAIN, [LLMError("out of credit")])
    assert pipeline.drop_topic(job_for(), tree, "tools", "No.", pipeline.OfflineLLM).ok
    assert not (ledger.research_dir(tree) / "tools.pending.json").exists()
    assert (ledger.research_dir(tree) / "tools.2.jsonl").is_file()
    assert pipeline.add_topic(job_for(), tree, "Tools", "Another question.", FakeLLM([BARE])).ok
    llm = ResearchingLLM([{"edges": []}, refit("tools")[1]], {"tools": THIRD})
    assert pipeline.research_topic(job_for(), tree, "tools", llm).ok
    assert llm.researched == ["tools"]
    assert Plan.load(tree).research_of("tools").transcript == "tools.3.jsonl"  # type: ignore[union-attr]


def test_dropping_one_of_two_researched_topics_leaves_the_plan_researched(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert pipeline.drop_topic(job_for(), tree, "tools", "No.", pipeline.OfflineLLM).ok
    assert Plan.load(tree).researched and stamp(tree).startswith(render.RESEARCHED)


@pytest.mark.parametrize("title", ["What it takes", "  what IT takes "], ids=["same", "other-case-and-spacing"])
def test_a_rename_to_a_title_another_topic_has_is_refused_in_a_sentence(tmp_path, title):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("topic", "rename", "scope", title, "--dir", str(tree))
    assert result.exit_code == 1
    assert "Nothing was changed: the topic resources is already called 'What it takes'." in said(result)
    assert snapshot(tree) == before
