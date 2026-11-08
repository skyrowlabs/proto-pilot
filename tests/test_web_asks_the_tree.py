"""The web front end asks a tree what it is, never its registry entry, and keeps a name out of script."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import require_or_skip

from protopilot import cli, registry

pytestmark = pytest.mark.unit

IDEA = "start a community tool library"


def make_plan(tree: Path) -> Path:
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 0, result.output
    return tree


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


# ── B2: the web asks the tree, not the entry ─────────────────────────


@pytest.mark.parametrize("action", ["up", "down", "purge", "delete"])
def test_a_plan_recorded_as_an_app_gets_no_docker_and_no_delete_from_the_web(client, tmp_path, calls, action: str):
    tree = make_plan(tmp_path / "t")
    registry.save([])
    registry.record(slug="stale", name="Stale", path=tree, port=8080)
    client.post(f"/projects/stale/{action}", follow_redirects=False)
    assert calls == [] and tree.exists()


def test_the_page_for_a_plan_recorded_as_an_app_is_the_plan_page(client, tmp_path):
    tree = make_plan(tmp_path / "t")
    registry.save([])
    registry.record(slug="stale", name="Stale", path=tree, port=8080)
    page = client.get("/projects/stale")
    assert page.status_code == 200 and "A plan, not an app" in page.text


def test_the_page_for_an_entry_whose_tree_is_gone_goes_home(client, tmp_path):
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8080)
    reply = client.get("/projects/ghost", follow_redirects=False)
    assert (reply.status_code, reply.headers["location"]) == (303, "/")


# ── the confirm prompt is data, never script ─────────────────────────


def test_a_name_with_a_quote_cannot_reach_the_confirm_handler_as_script(client, tmp_path, spec):
    name = "x');alert(1);('"
    root = tmp_path / "q"
    spec.save(root)
    registry.record(slug="q", name=name, path=root, port=8080)
    pages = [client.get("/").text, client.get("/projects/q").text]
    handlers = [line for page in pages for line in page.splitlines() if "onsubmit=" in line]
    assert handlers and all("{{" not in h and "alert" not in h for h in handlers)
