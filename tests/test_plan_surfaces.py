"""A plan tree on the surfaces written for apps: the lifecycle verbs, `proto ls`, and the web list."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli, containers, registry

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
    monkeypatch.setattr(containers, "running_paths", refuse)


@pytest.fixture
def plan_tree(tmp_path) -> Path:
    tree = tmp_path / "tool_library"
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 0, result.output
    return tree


def app_tree(tmp_path: Path, slug: str = "gearlist") -> Path:
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    registry.record(slug=slug, name=slug.title(), path=root, port=8080)
    return root


# ── the lifecycle verbs ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "argv",
    [["up"], ["down"], ["test"], ["reset", "--yes"], ["logs"], ["add", "a change", "--offline"], ["spec"], ["export"]],
)
def test_every_app_verb_refuses_a_plan_and_says_what_to_do(plan_tree, no_docker, argv: list[str]):
    result = CliRunner().invoke(cli.main, [*argv, "--dir", str(plan_tree)])
    assert result.exit_code != 0
    assert f"is a plan, not an app, so there is nothing to `proto {argv[0]}`" in said(result)
    assert "Read PLAN.md" in said(result)


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
    assert row.split()[:2] == ["-", "plan"] and ":" not in row.split()[3]


def test_ls_shows_both_kinds_side_by_side(tmp_path, plan_tree, monkeypatch):
    app_tree(tmp_path)
    monkeypatch.setattr(containers, "running_paths", lambda runner: set())
    rows = [line.split() for line in CliRunner().invoke(cli.main, ["ls"]).output.splitlines() if "/" in line]
    assert sorted((row[1], row[3]) for row in rows) == [("app", ":8080"), ("plan", "-")]


def test_down_all_never_reaches_a_plan(tmp_path, plan_tree, monkeypatch):
    app = app_tree(tmp_path)
    stopped: list[Path] = []
    monkeypatch.setattr(cli, "_compose", lambda target, *args: stopped.append(target) or 0)
    result = CliRunner().invoke(cli.main, ["down", "--all"])
    assert result.exit_code == 0, result.output
    assert stopped == [app.resolve()]


# ── the web front end ────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from protopilot.web import app as web

    monkeypatch.setattr(web, "docker_available", lambda runner: (False, "not asked in a test"))
    return TestClient(web.create_app(tmp_path / "workspace", backend="offline"))


def test_the_web_list_shows_a_plan_read_only(client, plan_tree):
    page = client.get("/")
    assert page.status_code == 200
    assert "read-only" in page.text and "/projects/community_tool_library/delete" not in page.text


def test_the_web_page_for_a_plan_offers_no_app_action(client, plan_tree):
    page = client.get("/projects/community_tool_library")
    assert page.status_code == 200
    assert "A plan, not an app" in page.text and "PLAN.md" in page.text
    assert "/up" not in page.text and "/amend" not in page.text


@pytest.mark.parametrize("action", ["up", "down", "purge", "delete", "forget", "amend"])
def test_a_web_action_on_a_plan_changes_nothing(client, plan_tree, no_docker, action: str):
    data = {"change": "x"} if action == "amend" else {}
    reply = client.post(f"/projects/community_tool_library/{action}", data=data, follow_redirects=False)
    assert reply.status_code == 303
    assert plan_tree.exists() and [e.kind for e in registry.load()] == ["plan"]
