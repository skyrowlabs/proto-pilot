"""A topic research could not back is flagged where a person starts: its step and the open questions (#49)."""

from __future__ import annotations

from pathlib import Path

import pytest
from plan_script import GOOD, IDEA, script
from research_script import ResearchingLLM

from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import pipeline, render
from protopilot.plan.model import Plan

pytestmark = [pytest.mark.unit]

FIRST = GOOD["start"]["steps"][0]["topic"]


def entry(tree: Path) -> str:
    return (tree / render.PLAN_FILE).read_text(encoding="utf-8")


def failed_plan(tree: Path) -> Path:
    assert pipeline.run_plan(Job(id="t", idea=IDEA), tree, ResearchingLLM(script(), {FIRST: LLMError("down")})).ok
    return tree


def test_the_step_on_a_topic_whose_research_failed_says_so_and_names_the_way_back(tmp_path):
    page = entry(failed_plan(tmp_path / "tree"))
    step = page.split("## Where to start")[1].split("\n1. ")[1].split("\n2. ")[0]
    assert f"Not researched: run `proto research {FIRST}` before relying on this step." in step


def test_an_open_question_names_the_topic_and_is_drawn_not_stored(tmp_path):
    tree = failed_plan(tmp_path / "tree")
    title = next(t.title for t in Plan.load(tree).topics if t.slug == FIRST)
    questions = entry(tree).split("## Open questions")[1].split("\n## ")[0]
    assert f"What would research find for {title}?" in questions and f"`proto research {FIRST}`" in questions
    assert not [q for q in Plan.load(tree).questions if title in q]


def test_researched_topics_draw_no_flag(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(Job(id="t", idea=IDEA), tree, ResearchingLLM(script(), {})).ok
    assert "Not researched: run `proto research" not in entry(tree) and "What would research find" not in entry(tree)


def test_the_flag_leaves_once_the_topic_is_researched_again(tmp_path):
    tree = failed_plan(tmp_path / "tree")
    links = [e for e in GOOD["connect"]["edges"] if FIRST in (e["from_topic"], e["to_topic"])]
    notes = {"topics": [{"slug": FIRST, "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]}]}
    assert pipeline.research_topic(
        Job(id="t", idea=IDEA), tree, FIRST, ResearchingLLM([{"edges": links}, notes], {})
    ).ok
    assert "Not researched: run `proto research" not in entry(tree) and "What would research find" not in entry(tree)
