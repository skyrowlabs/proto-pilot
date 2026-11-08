"""A plan tree in the registry: listed by `proto plan`, read back by kind, deleted with no Docker call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli, registry
from protopilot.jobs import Job
from protopilot.plan import pipeline, render

pytestmark = pytest.mark.unit

IDEA = "start a community tool library"


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


def test_proto_plan_registers_its_tree_as_a_plan_with_no_port(plan_tree):
    [entry] = registry.load()
    assert (entry.kind, entry.port, entry.path, entry.exists) == ("plan", None, str(plan_tree.resolve()), True)


def test_rerendering_a_plan_keeps_one_entry_and_its_date(plan_tree):
    [before] = registry.load()
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(plan_tree)])
    assert result.exit_code == 0, result.output
    assert registry.load() == [before]


def test_a_plan_made_before_plans_were_listed_joins_the_list_on_rerender(plan_tree):
    registry.forget(plan_tree)
    CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(plan_tree)])
    assert [e.kind for e in registry.load()] == ["plan"]


def test_an_entry_written_before_kinds_existed_reads_as_an_app(tmp_path):
    root = app_tree(tmp_path)
    old = {"slug": "gearlist", "name": "Gearlist", "path": str(root), "port": 8080, "created_at": "2026-09-01"}
    registry.registry_path().write_text(json.dumps([old]))
    [entry] = registry.load()
    assert (entry.kind, entry.exists) == ("app", True)


def test_a_plan_entry_is_gone_once_its_plan_json_is(plan_tree):
    (plan_tree / ".protopilot" / "plan.json").unlink()
    assert [e.exists for e in registry.load()] == [False]


def test_delete_removes_a_plan_without_calling_docker(plan_tree):
    calls: list = []
    registry.delete(plan_tree, runner=lambda argv, cwd: calls.append(argv))
    assert (calls, plan_tree.exists(), registry.load()) == ([], False, [])


def test_delete_still_calls_an_apps_stack_down(tmp_path):
    root = app_tree(tmp_path)
    calls: list = []
    registry.delete(root, runner=lambda argv, cwd: calls.append(argv))
    assert calls == [["docker", "compose", "down", "-v"]]


def test_delete_refuses_a_tree_with_research_in_progress_but_no_plan(tmp_path):
    stopped = tmp_path / "stopped"
    (stopped / ".protopilot" / "research").mkdir(parents=True)
    with pytest.raises(registry.NotAProject):
        registry.delete(stopped, runner=lambda argv, cwd: None)
    assert stopped.exists()


def test_a_plan_whose_render_is_blocked_after_saving_is_still_registered(tmp_path, monkeypatch):
    def blocked(plan, tree, runbook=""):
        raise render.PageBlocked("a page is blocked")

    monkeypatch.setattr(render, "write", blocked)
    tree = tmp_path / "tree"
    with pytest.raises(pipeline.PlanRefused):
        pipeline.run_plan(Job(id="t", idea=IDEA), tree)
    assert [(e.kind, e.path) for e in registry.load()] == [("plan", str(tree.resolve()))]
