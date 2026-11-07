"""The registry once plans are a second writer: odd kinds, shared slugs, unsafe roots, and racing writers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import threading
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import require_or_skip

from protopilot import cli, registry

pytestmark = pytest.mark.unit

IDEA = "start a community tool library"
SLUG = "community_tool_library"


def make_plan(tree: Path) -> Path:
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 0, result.output
    return tree


def app_at(root: Path) -> Path:
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    return root


def write_raw(entries: list[dict]) -> None:
    registry.registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path().write_text(json.dumps(entries))


@pytest.fixture
def calls(monkeypatch) -> list:
    seen: list = []
    monkeypatch.setattr(subprocess, "call", lambda argv, **kw: seen.append(argv) or 0)
    return seen


@pytest.fixture
def client(tmp_path, monkeypatch):
    require_or_skip(importlib.util.find_spec("fastapi") is not None, "fastapi is not installed", requires="dev extras")
    from fastapi.testclient import TestClient

    from protopilot.web import app as web

    monkeypatch.setattr(web, "docker_available", lambda runner: (False, "not asked in a test"))
    return TestClient(web.create_app(tmp_path / "workspace", backend="offline"))


# ── B1: a kind that is not one of ours ───────────────────────────────


@pytest.mark.parametrize("kind", [None, 3, ["plan"], "banana"])
def test_an_entry_whose_kind_is_not_ours_is_gone_and_ls_survives_it(tmp_path, kind: object):
    stranger = tmp_path / "s"
    stranger.mkdir()
    write_raw([{"slug": "s", "name": "S", "path": str(stranger), "port": None, "created_at": "x", "kind": kind}])
    assert [e.exists for e in registry.load()] == [False]
    result = CliRunner().invoke(cli.main, ["ls"])
    assert result.exit_code == 0 and "gone" in result.output


def test_prune_forgets_an_entry_whose_kind_is_not_ours(tmp_path):
    stranger = tmp_path / "s"
    stranger.mkdir()
    write_raw([{"slug": "s", "name": "S", "path": str(stranger), "port": None, "created_at": "x", "kind": None}])
    assert registry.prune() == []


# ── B3: one idea, an app and a plan ──────────────────────────────────


def test_an_app_and_a_plan_from_one_idea_get_different_slugs(tmp_path):
    registry.record(slug=SLUG, name="App", path=app_at(tmp_path / "app"), port=8080)
    make_plan(tmp_path / "plan")
    slugs = [e.slug for e in registry.load()]
    assert len(set(slugs)) == 2 and SLUG in slugs


def test_rerecording_one_path_keeps_its_slug(tmp_path):
    registry.record(slug="gear", name="A", path=app_at(tmp_path / "a"), port=8080)
    registry.record(slug="gear", name="B", path=app_at(tmp_path / "b"), port=8081)
    registry.record(slug="gear", name="B", path=tmp_path / "b", port=8082)
    assert sorted(e.slug for e in registry.load()) == ["gear", "gear_2"]


def test_the_web_deletes_the_app_that_shares_an_idea_with_a_plan(client, tmp_path, calls):
    app = app_at(tmp_path / "app")
    registry.record(slug=SLUG, name="App", path=app, port=8080)
    plan = make_plan(tmp_path / "plan")
    client.post(f"/projects/{SLUG}/delete", follow_redirects=False)
    assert not app.exists() and plan.exists()


# ── B4: a root that holds home, or the registry itself ───────────────


def test_delete_refuses_a_parent_of_home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    (tmp_path / ".protopilot").mkdir()
    (tmp_path / ".protopilot" / "plan.json").write_text("{}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(tmp_path, runner=lambda argv, cwd: None)
    assert (tmp_path / "home").exists()


def test_delete_refuses_a_tree_that_holds_the_registry(tmp_path, monkeypatch):
    tree = make_plan(tmp_path / "t")
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tree / "inside" / "projects.json"))
    registry.record(slug="x", name="X", path=tree, port=None, kind=registry.PLAN)
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(tree, runner=lambda argv, cwd: None)
    assert registry.registry_path().exists()


# ── writers that race ────────────────────────────────────────────────


def test_concurrent_records_lose_no_entry(tmp_path):
    def write(n: int) -> None:
        for i in range(25):
            registry.record(slug=f"s{n}_{i}", name="S", path=tmp_path / f"t{n}_{i}", port=None, kind=registry.PLAN)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(registry.load()) == 150


def test_save_leaves_no_partial_file_behind(tmp_path):
    registry.record(slug="a", name="A", path=tmp_path / "a", port=None, kind=registry.PLAN)
    folder = registry.registry_path().parent
    assert sorted(p.name for p in folder.iterdir() if not p.name.endswith(".lock")) == ["projects.json"]
