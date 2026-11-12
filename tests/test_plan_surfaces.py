"""A plan tree on the verbs it shares a list with: `proto ls` and `proto rm`, and what `rm` refuses."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli, registry

pytestmark = pytest.mark.unit

IDEA = "start a community tool library"


def said(result) -> str:
    """The output as one line: a long path makes click's error wrap anywhere."""
    return " ".join(result.output.split())


@pytest.fixture
def no_docker(monkeypatch):
    """Any Docker call, by any route, fails the test that made it."""

    def refuse(*args: object, **kwargs: object) -> int:
        raise AssertionError(f"a Docker call was made: {args}")

    monkeypatch.setattr(subprocess, "call", refuse)


@pytest.fixture
def plan_tree(tmp_path) -> Path:
    tree = tmp_path / "tool_library"
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 0, result.output
    return tree


def old_prototype(tmp_path: Path, slug: str = "gearlist") -> Path:
    """A folder as an older proto.pilot left one, with its row."""
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    registry.record(slug=slug, name=slug.title(), path=root, kind=registry.APP)
    return root


# ── rm and ls ────────────────────────────────────────────────────────────


def test_rm_removes_a_plan_and_never_calls_docker(plan_tree, no_docker):
    result = CliRunner().invoke(cli.main, ["rm", "--dir", str(plan_tree), "--yes"])
    assert result.exit_code == 0, result.output
    assert (plan_tree.exists(), registry.load()) == (False, [])


def test_rm_names_the_plan_it_is_about_to_delete(plan_tree, no_docker):
    result = CliRunner().invoke(cli.main, ["rm", "--dir", str(plan_tree)], input="n\n")
    assert said(result).startswith("Delete Start a community tool library and everything in")
    assert result.exit_code != 0 and plan_tree.exists()


def test_rm_still_refuses_a_directory_that_is_not_ours(tmp_path, no_docker):
    stranger = tmp_path / "stranger"
    stranger.mkdir()
    result = CliRunner().invoke(cli.main, ["rm", "--dir", str(stranger), "--yes"])
    assert result.exit_code != 0 and stranger.exists()


def test_ls_lists_a_plan_with_its_kind_and_no_port_and_asks_docker_nothing(plan_tree, no_docker):
    result = CliRunner().invoke(cli.main, ["ls"])
    assert result.exit_code == 0, result.output
    [row] = [line for line in result.output.splitlines() if str(plan_tree.resolve()) in line]
    assert row.split()[:2] == ["-", "plan"] and len(row.split()) == 4


def test_rm_refuses_an_older_prototype_and_says_what_to_run_instead(tmp_path, no_docker):
    old = old_prototype(tmp_path)
    result = CliRunner().invoke(cli.main, ["rm", "--dir", str(old), "--yes"])
    assert result.exit_code != 0
    assert "prototype from an older proto.pilot" in said(result) and "docker compose down -v" in said(result)
    assert (old / ".protopilot" / "spec.json").exists() and [e.slug for e in registry.load()] == ["gearlist"]
