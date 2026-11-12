"""Plan lifecycle on the list: `ls` reads, and only `prune` forgets."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli, registry

pytestmark = pytest.mark.unit


def project(tmp_path: Path, slug: str) -> Path:
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "plan.json").write_text("{}")
    registry.record(slug=slug, name=slug.title(), path=root)
    return root


# ── ls is a read ─────────────────────────────────────────────────────────


def test_ls_does_not_delete_entries_whose_directory_is_gone(tmp_path):
    """The regression. `ls` used to call prune(), so reading the list emptied it."""
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")

    result = CliRunner().invoke(cli.main, ["ls"])

    assert result.exit_code == 0
    assert {e.slug for e in registry.load()} == {"alive", "ghost"}


def test_ls_reports_a_missing_tree_rather_than_hiding_it(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")

    output = CliRunner().invoke(cli.main, ["ls"]).output

    assert "gone" in output and "ghost" in output
    assert "proto prune" in output


# ── prune is the write ───────────────────────────────────────────────────


def test_prune_forgets_only_the_entries_whose_tree_is_gone(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")

    result = CliRunner().invoke(cli.main, ["prune", "--yes"])

    assert result.exit_code == 0
    assert [e.slug for e in registry.load()] == ["alive"]


def test_prune_says_so_when_there_is_nothing_to_do(tmp_path):
    project(tmp_path, "alive")
    output = CliRunner().invoke(cli.main, ["prune", "--yes"]).output
    assert "nothing to prune" in output
    assert [e.slug for e in registry.load()] == ["alive"]


def test_declining_the_prune_confirmation_changes_nothing(tmp_path):
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")
    CliRunner().invoke(cli.main, ["prune"], input="n\n")
    assert [e.slug for e in registry.load()] == ["ghost"]
