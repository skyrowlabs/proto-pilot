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


# ── an older version's prototype rows ────────────────────────────────────


def old_row(tmp_path: Path, slug: str) -> Path:
    """A prototype's folder as an older version left it, with the row it wrote."""
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    registry.record(slug=slug, name=slug.title(), path=root, kind=registry.APP)
    return root


def summary(output: str) -> list[str]:
    """What `proto ls` prints under its rows."""
    return [line.strip() for line in output.split("\n\n", 1)[1].splitlines()]


def test_ls_on_an_empty_list_says_how_to_make_a_plan():
    result = CliRunner().invoke(cli.main, ["ls"])
    assert result.exit_code == 0
    assert result.output.strip() == 'no plans yet -- `proto plan "an idea"` makes one'


def test_ls_with_only_plans_counts_them_and_says_nothing_else(tmp_path):
    project(tmp_path, "one")
    project(tmp_path, "two")
    result = CliRunner().invoke(cli.main, ["ls"])
    assert result.exit_code == 0
    assert summary(result.output) == ["2 plan(s)"]


def test_ls_counts_plans_gone_and_old_rows_apart(tmp_path):
    project(tmp_path, "one")
    project(tmp_path, "two")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")
    old_row(tmp_path, "web")
    old_row(tmp_path, "tui")

    result = CliRunner().invoke(cli.main, ["ls"])

    assert result.exit_code == 0
    assert summary(result.output) == [
        "2 plan(s)",
        "1 whose plan is gone -- `proto prune` to forget them",
        f"2 old: {cli.OLD_ROWS}",
    ]


def test_ls_says_the_sentence_about_old_rows_once_however_many_there_are(tmp_path):
    for slug in ("a", "b", "c"):
        old_row(tmp_path, slug)
    output = CliRunner().invoke(cli.main, ["ls"]).output
    assert output.count("no longer runs prototypes") == 1
    assert summary(output) == ["0 plan(s)", f"3 old: {cli.OLD_ROWS}"]


def test_declining_the_prune_confirmation_keeps_old_and_gone_rows(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")
    web = old_row(tmp_path, "web")
    before = registry.load()

    result = CliRunner().invoke(cli.main, ["prune"], input="n\n")

    assert result.exit_code == 1 and "forgot" not in result.output
    assert "Forget 2 entr(y/ies)?" in result.output
    assert registry.load() == before and web.exists()


def test_accepting_the_prune_confirmation_forgets_old_rows_and_keeps_their_folders(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")
    web = old_row(tmp_path, "web")

    result = CliRunner().invoke(cli.main, ["prune"], input="\n")

    assert result.exit_code == 0 and "forgot 2: 1 gone, 1 old" in result.output
    assert [e.slug for e in registry.load()] == ["alive"]
    assert (web / ".protopilot" / "spec.json").exists()


def test_proto_is_exactly_the_planning_verbs():
    assert sorted(cli.main.commands) == ["answer", "doctor", "dream", "ls", "plan", "prune", "rm"]
