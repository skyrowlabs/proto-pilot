"""`proto plan --offline`: the tree it writes, and the targets it refuses."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"


def plan(*args: str):
    return CliRunner().invoke(cli.main, ["plan", *args])


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def test_two_fresh_runs_are_byte_identical(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    assert plan(IDEA, "--offline", "--yes", "--dir", str(first)).exit_code == 0
    assert plan(IDEA, "--offline", "--yes", "--dir", str(second)).exit_code == 0
    written = snapshot(first)
    assert written == snapshot(second)
    assert {"PLAN.md", "dreams.md", "sources.md", ".protopilot/plan.json", "topics/audience.md"} <= set(written)
    assert b"Not researched" in written["PLAN.md"]


def test_default_directory_is_named_from_the_idea(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert plan(IDEA, "--offline", "--yes").exit_code == 0
    assert (tmp_path / "community_tool_library" / "PLAN.md").is_file()


@pytest.mark.parametrize("idea", ["", "   ", "\n\t"])
def test_an_empty_idea_is_refused_before_any_directory_is_chosen(tmp_path, monkeypatch, idea):
    monkeypatch.chdir(tmp_path)
    result = plan(idea, "--offline", "--yes")
    assert result.exit_code == 1
    assert "needs an idea" in result.output
    assert list(tmp_path.iterdir()) == []


def test_two_ideas_sharing_a_default_directory_do_not_share_a_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert plan("build a shed", "--offline", "--yes").exit_code == 0
    before = snapshot(tmp_path / "shed")
    result = plan("make a shed", "--offline", "--yes")
    assert result.exit_code == 1
    assert "build a shed" in " ".join(result.output.split())
    assert snapshot(tmp_path / "shed") == before


def test_a_directory_without_a_plan_is_refused(tmp_path):
    (tmp_path / "keep.txt").write_text("mine")
    result = plan(IDEA, "--offline", "--yes", "--dir", str(tmp_path))
    assert result.exit_code == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]


def test_a_rerender_restores_the_markdown_from_plan_json(tmp_path):
    tree = tmp_path / "tree"
    plan(IDEA, "--offline", "--yes", "--dir", str(tree))
    before = snapshot(tree)
    (tree / "PLAN.md").write_text("hand edit")
    (tree / "topics" / "gone.md").write_text("stale")
    assert plan(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    assert snapshot(tree) == before


@pytest.mark.parametrize("asked", [("another idea",), (IDEA, "--direction", "two towns")])
def test_a_plan_for_something_else_is_refused_and_left_alone(tmp_path, asked):
    tree = tmp_path / "tree"
    plan(IDEA, "--offline", "--yes", "--dir", str(tree))
    before = snapshot(tree)
    result = plan(*asked, "--offline", "--yes", "--dir", str(tree))
    assert result.exit_code == 1
    assert IDEA in " ".join(result.output.split())
    assert "--dir" in result.output
    assert snapshot(tree) == before
