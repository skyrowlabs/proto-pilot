"""Prototype lifecycle: listing, pruning, collecting, and moving a port.

The headline case is a regression test for something that actually happened:
`proto ls` called `prune()`, so *looking at* the list of prototypes deleted
every entry whose directory had gone -- and a wiped scratch directory took the
whole registry with it. A read must not be a write.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli, containers, registry
from protopilot.render import render_skeleton
from protopilot.spec import Spec

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))
    # No daemon in CI, and no spawn either: every lifecycle command asks Docker
    # something, and a test that shells out is a test that behaves differently
    # on a laptop than on a runner.
    monkeypatch.setattr(containers, "running_paths", lambda runner: set())


def project(tmp_path: Path, slug: str, port: int = 8080) -> Path:
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    registry.record(slug=slug, name=slug.title(), path=root, port=port)
    return root


# ── ls is a read ─────────────────────────────────────────────────────────


def test_ls_does_not_delete_entries_whose_directory_is_gone(tmp_path):
    """The regression. `ls` used to call prune(), so reading the list emptied it."""
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8081)

    result = CliRunner().invoke(cli.main, ["ls"])

    assert result.exit_code == 0
    assert {e.slug for e in registry.load()} == {"alive", "ghost"}


def test_ls_reports_a_missing_tree_rather_than_hiding_it(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8081)

    output = CliRunner().invoke(cli.main, ["ls"]).output

    assert "gone" in output and "ghost" in output
    assert "proto prune" in output


def test_ls_marks_a_running_prototype(tmp_path, monkeypatch):
    root = project(tmp_path, "alive")
    monkeypatch.setattr(containers, "running_paths", lambda runner: {str(root.resolve())})

    output = CliRunner().invoke(cli.main, ["ls"]).output

    assert "up" in output.split("alive")[0].split("\n")[-1]


# ── prune is the write ───────────────────────────────────────────────────


def test_prune_forgets_only_the_entries_whose_tree_is_gone(tmp_path):
    project(tmp_path, "alive")
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8081)

    result = CliRunner().invoke(cli.main, ["prune", "--yes"])

    assert result.exit_code == 0
    assert [e.slug for e in registry.load()] == ["alive"]


def test_prune_says_so_when_there_is_nothing_to_do(tmp_path):
    project(tmp_path, "alive")
    output = CliRunner().invoke(cli.main, ["prune", "--yes"]).output
    assert "nothing to prune" in output
    assert [e.slug for e in registry.load()] == ["alive"]


def test_declining_the_prune_confirmation_changes_nothing(tmp_path):
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8081)
    CliRunner().invoke(cli.main, ["prune"], input="n\n")
    assert [e.slug for e in registry.load()] == ["ghost"]


# ── gc ───────────────────────────────────────────────────────────────────


def test_gc_dry_run_removes_nothing(tmp_path, monkeypatch):
    orphan = containers.Orphan(path=str(tmp_path / "gone"), counts={"volume": 1})
    monkeypatch.setattr(cli, "docker_available", lambda runner: (True, "ok"))
    monkeypatch.setattr(containers, "find_orphans", lambda runner: [orphan])
    removed = []
    monkeypatch.setattr(containers, "remove", lambda runner, path: removed.append(path) or {})

    output = CliRunner().invoke(cli.main, ["gc", "--dry-run"]).output

    assert "nothing removed" in output
    assert removed == []


def test_gc_collects_and_then_forgets_the_registry_entry(tmp_path, monkeypatch):
    """Order matters: the registry entry holds the path that finds the
    resources, so forgetting it first would strand them."""
    gone = tmp_path / "gone"
    registry.record(slug="gone", name="Gone", path=gone, port=8081)
    orphan = containers.Orphan(path=str(gone.resolve()), counts={"volume": 1})
    seen: list[str] = []

    monkeypatch.setattr(cli, "docker_available", lambda runner: (True, "ok"))
    monkeypatch.setattr(containers, "find_orphans", lambda runner: [orphan])

    def fake_remove(runner, path):
        # The entry must still be there when removal runs.
        seen.append(path)
        assert [e.slug for e in registry.load()] == ["gone"]
        return {"volume": 1}

    monkeypatch.setattr(containers, "remove", fake_remove)

    result = CliRunner().invoke(cli.main, ["gc", "--yes"])

    assert result.exit_code == 0
    assert seen == [str(gone.resolve())]
    assert registry.load() == []


def test_gc_without_a_daemon_says_so_instead_of_reporting_clean(monkeypatch):
    """ "Nothing to collect" and "cannot look" must not print the same thing."""
    monkeypatch.setattr(cli, "docker_available", lambda runner: (False, "no daemon"))
    result = CliRunner().invoke(cli.main, ["gc", "--yes"])
    assert result.exit_code != 0
    assert "no daemon" in result.output


# ── moving a port ────────────────────────────────────────────────────────


def test_set_port_updates_compose_and_the_spec_together(tmp_path, spec):
    """Either both or neither. Updating one leaves a prototype that runs
    somewhere other than where every command says it does."""
    target = tmp_path / spec.slug
    render_skeleton(spec, target)
    spec.save(target)
    assert f'"{spec.port}:8000"' in (target / "compose.yml").read_text()

    cli.set_port(target, spec, 8123)

    assert '"8123:8000"' in (target / "compose.yml").read_text()
    assert Spec.load(target).port == 8123


def test_up_refuses_a_port_something_else_holds(tmp_path, spec, monkeypatch):
    target = tmp_path / spec.slug
    render_skeleton(spec, target)
    spec.save(target)
    monkeypatch.setattr(cli, "_port_is_ours", lambda project_dir, port: False)
    composed = []
    monkeypatch.setattr(cli, "_compose", lambda d, *a: composed.append(a) or 0)

    result = CliRunner().invoke(cli.main, ["up", "--dir", str(target)])

    assert result.exit_code != 0
    assert "already in use" in result.output
    assert "--port" in result.output
    # And it stopped before touching docker, rather than failing halfway up.
    assert composed == []


def test_up_is_still_idempotent_when_we_are_the_ones_holding_the_port(tmp_path, spec, monkeypatch):
    target = tmp_path / spec.slug
    render_skeleton(spec, target)
    spec.save(target)
    monkeypatch.setattr(cli, "_port_is_ours", lambda project_dir, port: True)
    monkeypatch.setattr(cli, "_compose", lambda d, *a: 0)

    result = CliRunner().invoke(cli.main, ["up", "--dir", str(target)])

    assert result.exit_code == 0


# ── down --all ───────────────────────────────────────────────────────────


def test_down_all_stops_every_tree_that_still_exists(tmp_path, monkeypatch):
    project(tmp_path, "one")
    project(tmp_path, "two", port=8081)
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8082)
    calls: list[tuple[Path, tuple]] = []
    monkeypatch.setattr(cli, "_compose", lambda d, *a: calls.append((d, a)) or 0)

    output = CliRunner().invoke(cli.main, ["down", "--all"]).output

    # The ghost is skipped: half-cleaning it would stop nothing and leave the
    # volume, which is the state hardest to notice. That is `gc`'s job.
    assert {d.name for d, _ in calls} == {"one", "two"}
    assert all(args == ("down",) for _, args in calls)
    assert "2/2 stopped" in output


def test_down_all_purge_drops_the_volumes(tmp_path, monkeypatch):
    project(tmp_path, "one")
    calls: list[tuple] = []
    monkeypatch.setattr(cli, "_compose", lambda d, *a: calls.append(a) or 0)

    CliRunner().invoke(cli.main, ["down", "--all", "--purge"])

    assert calls == [("down", "-v")]
