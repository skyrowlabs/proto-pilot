"""The guards between a plan and the app verbs: what `tree_kind` reads, what `delete` removes, who registers."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import require_or_skip
from fakes import FakeLLM
from plan_script import NO_REPAIR, edge, script
from research_script import ResearchingLLM

from protopilot import cli, registry
from protopilot.jobs import STORE, Job
from protopilot.plan import pipeline
from protopilot.plan.model import Plan, plan_path

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"
SLUG = "community_tool_library"


def make_plan(tree: Path) -> Path:
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 0, result.output
    return tree


def plant(root: Path, *names: str) -> Path:
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("{}")
    return root


def app_tree(tmp_path: Path, slug: str = "gearlist") -> Path:
    root = plant(tmp_path / slug, ".protopilot/spec.json")
    registry.record(slug=slug, name=slug.title(), path=root, port=8080)
    return root


@pytest.fixture
def calls(monkeypatch) -> list:
    """Every `subprocess.call`, recorded instead of run."""
    seen: list = []
    monkeypatch.setattr(subprocess, "call", lambda argv, **kw: seen.append((argv, kw.get("cwd"))) or 0)
    return seen


def recorder() -> tuple[list, object]:
    seen: list = []
    return seen, lambda argv, cwd: seen.append(argv)


# ── tree_kind and delete ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "kind"),
    [
        ((), None),
        ((".protopilot/spec.json",), "app"),
        ((".protopilot/plan.json",), "plan"),
        ((".protopilot/spec.json", ".protopilot/plan.json"), "app"),
        ((".protopilot/research/draft.json",), None),
        (("plan.json",), None),
    ],
)
def test_tree_kind_reads_only_our_own_files(tmp_path: Path, files: tuple[str, ...], kind: str | None):
    assert registry.tree_kind(plant(tmp_path / "t", *files)) == kind


def test_a_dangling_plan_json_link_is_not_ours_and_is_never_deleted(tmp_path):
    tree = tmp_path / "t"
    (tree / ".protopilot").mkdir(parents=True)
    (tree / ".protopilot" / "plan.json").symlink_to(tmp_path / "nowhere")
    with pytest.raises(registry.NotAProject):
        registry.delete(tree, runner=recorder()[1])
    assert tree.exists()


def test_deleting_a_plan_whose_protopilot_dir_is_a_link_leaves_the_link_target(tmp_path):
    outside = plant(tmp_path / "outside", "plan.json", "keep.txt")
    tree = tmp_path / "t"
    tree.mkdir()
    (tree / ".protopilot").symlink_to(outside)
    registry.delete(tree, runner=recorder()[1])
    assert not tree.exists() and sorted(p.name for p in outside.iterdir()) == ["keep.txt", "plan.json"]


def test_deleting_a_plan_whose_plan_json_is_a_link_leaves_the_file_it_points_at(tmp_path):
    precious = tmp_path / "precious.txt"
    precious.write_text("mine")
    tree = tmp_path / "t"
    (tree / ".protopilot").mkdir(parents=True)
    (tree / ".protopilot" / "plan.json").symlink_to(precious)
    registry.delete(tree, runner=recorder()[1])
    assert not tree.exists() and precious.read_text() == "mine"


def test_delete_refuses_the_home_directory_even_when_it_holds_a_plan(tmp_path, monkeypatch):
    home = plant(tmp_path / "home", ".protopilot/plan.json")
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(home, runner=recorder()[1])
    assert plan_path(home).exists()


def test_delete_asks_the_tree_not_the_registry_and_stops_a_stack_that_appeared(tmp_path):
    tree = make_plan(tmp_path / "t")
    plant(tree, ".protopilot/spec.json")
    seen, runner = recorder()
    registry.delete(tree, runner=runner)
    assert seen == [["docker", "compose", "down", "-v"]] and not tree.exists()


def test_delete_calls_no_docker_for_a_plan_recorded_as_an_app(tmp_path):
    tree = plant(tmp_path / "t", ".protopilot/plan.json")
    registry.record(slug="t", name="T", path=tree, port=8080)
    seen, runner = recorder()
    registry.delete(tree, runner=runner)
    assert (seen, tree.exists(), registry.load()) == ([], False, [])


# ── what the registry file holds ──────────────────────────────────────


def test_a_plan_entry_round_trips_as_json_null_port_and_kind_plan(tmp_path):
    registry.record(slug="p", name="P", path=tmp_path / "p", port=None, kind=registry.PLAN)
    [raw] = json.loads(registry.registry_path().read_text())
    assert (raw["port"], raw["kind"]) == (None, "plan")
    assert [(e.port, e.kind) for e in registry.load()] == [(None, "plan")]


def test_an_entry_with_an_unknown_kind_is_gone_and_reaches_no_docker(tmp_path, calls):
    root = plant(tmp_path / "odd", ".protopilot/spec.json")
    registry.record(slug="odd", name="Odd", path=root, port=8080, kind="banana")
    assert [e.exists for e in registry.load()] == [False]
    result = CliRunner().invoke(cli.main, ["down", "--all"])
    assert (result.exit_code, "nothing to stop" in result.output, calls) == (0, True, [])


# ── _register ────────────────────────────────────────────────────────


def test_a_red_plan_is_registered_too(tmp_path):
    tree = tmp_path / "tree"
    loop = [edge("lending", "space"), edge("space", "lending")]
    verdict = pipeline.run_plan(Job(id="t", idea=IDEA), tree, FakeLLM([*script(connect={"edges": loop}), NO_REPAIR]))
    assert not verdict.ok
    assert [(e.kind, e.path) for e in registry.load()] == [("plan", str(tree.resolve()))]


def test_a_rerender_keeps_the_entrys_original_date(tmp_path):
    tree = make_plan(tmp_path / "t")
    [entry] = registry.load()
    entry.created_at = "2020-01-01T00:00:00+00:00"
    registry.save([entry])
    make_plan(tree)
    assert [e.created_at for e in registry.load()] == ["2020-01-01T00:00:00+00:00"]


def test_a_rerender_replaces_a_stale_app_entry_at_the_same_path(tmp_path):
    tree = make_plan(tmp_path / "t")
    registry.save([])
    registry.record(slug="old", name="Old", path=tree, port=8080)
    make_plan(tree)
    assert [(e.kind, e.port, e.slug) for e in registry.load()] == [("plan", None, SLUG)]


def test_a_dream_round_adds_no_entry_and_keeps_the_plans(tmp_path):
    tree = make_plan(tmp_path / "t")
    before = registry.load()
    result = CliRunner().invoke(cli.main, ["dream", str(tree), "--offline"])
    assert result.exit_code == 0, result.output
    assert registry.load() == before


def test_a_plan_that_stopped_after_research_registers_once_it_resumes(tmp_path):
    tree = tmp_path / "tree"
    with pytest.raises(Exception, match="cannot be used"):
        pipeline.run_plan(Job(id="t", idea=IDEA), tree, ResearchingLLM(script(connect={"edges": "nonsense"}), {}))
    assert registry.load() == []
    assert pipeline.run_plan(Job(id="t", idea=IDEA), tree, ResearchingLLM(script()[2:], {})).ok
    assert [(e.kind, e.path) for e in registry.load()] == [("plan", str(tree.resolve()))]


# ── the CLI ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("argv", [["up"], ["down"], ["logs"], ["spec"]])
def test_an_app_verb_run_inside_a_plan_tree_refuses_it(tmp_path, monkeypatch, calls, argv: list[str]):
    tree = make_plan(tmp_path / "t")
    monkeypatch.chdir(tree)
    result = CliRunner().invoke(cli.main, argv)
    assert result.exit_code == 1 and "is a plan, not an app" in result.output
    assert calls == []


def test_down_all_with_only_plans_has_nothing_to_stop(tmp_path, calls):
    make_plan(tmp_path / "t")
    result = CliRunner().invoke(cli.main, ["down", "--all"])
    assert (result.exit_code, result.output.strip(), calls) == (0, "nothing to stop", [])


def test_rm_names_an_unreadable_plan_by_its_folder_and_still_deletes_it(tmp_path, calls):
    tree = plant(tmp_path / "half_written", ".protopilot/plan.json")
    plan_path(tree).write_text("not json")
    asked = CliRunner().invoke(cli.main, ["rm", "--dir", str(tree)], input="n\n")
    assert asked.output.startswith(f"Delete half_written and everything in {tree.resolve()}?")
    done = CliRunner().invoke(cli.main, ["rm", "--dir", str(tree), "--yes"])
    assert (done.exit_code, tree.exists(), calls) == (0, False, [])


def test_rm_refuses_a_home_directory_holding_a_plan(tmp_path, monkeypatch, calls):
    home = plant(tmp_path / "home", ".protopilot/plan.json")
    monkeypatch.setenv("HOME", str(home))
    result = CliRunner().invoke(cli.main, ["rm", "--dir", str(home), "--yes"])
    assert result.exit_code == 1 and plan_path(home).exists()


# ── the web front end ────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    require_or_skip(importlib.util.find_spec("fastapi") is not None, "fastapi is not installed", requires="dev extras")
    from fastapi.testclient import TestClient

    from protopilot.web import app as web

    monkeypatch.setattr(web, "docker_available", lambda runner: (False, "not asked in a test"))
    return TestClient(web.create_app(tmp_path / "workspace", backend="offline"))


HOSTILE = "<script>alert(1)</script>"


def test_a_model_written_title_is_escaped_on_the_list_and_the_plan_page(client, tmp_path):
    tree = make_plan(tmp_path / "t")
    plan = Plan.load(tree)
    plan.title = HOSTILE
    plan.save(tree)
    [entry] = registry.load()
    entry.name, entry.idea = HOSTILE, HOSTILE
    registry.save([entry])
    pages = [client.get("/"), client.get(f"/projects/{SLUG}")]
    assert [p.status_code for p in pages] == [200, 200]
    assert all(HOSTILE not in p.text and "&lt;script&gt;" in p.text for p in pages)


def test_the_plan_page_survives_an_unreadable_plan_json(client, tmp_path):
    tree = make_plan(tmp_path / "t")
    plan_path(tree).write_text("{ not json")
    page = client.get(f"/projects/{SLUG}")
    assert page.status_code == 200 and "plan.json cannot be read" in page.text


def test_the_plan_page_names_the_plan_its_folder_and_its_files_and_has_no_form(client, tmp_path):
    tree = make_plan(tmp_path / "t")
    page = client.get(f"/projects/{SLUG}").text
    assert "<h1>Start a community tool library</h1>" in page and str(tree.resolve()) in page
    assert '<div class="small">PLAN.md</div>' in page and "<form" not in page


def test_a_web_action_on_an_unknown_slug_goes_home_and_runs_nothing(client, calls):
    reply = client.post("/projects/nobody/up", follow_redirects=False)
    assert (reply.status_code, reply.headers["location"], calls) == (303, "/", [])


def test_a_web_action_on_a_plan_goes_back_to_its_page(client, tmp_path, calls):
    make_plan(tmp_path / "t")
    reply = client.post(f"/projects/{SLUG}/up", follow_redirects=False)
    assert (reply.status_code, reply.headers["location"], calls) == (303, f"/projects/{SLUG}", [])


def test_amending_a_plan_on_the_web_starts_no_job(client, tmp_path):
    make_plan(tmp_path / "t")
    before = len(STORE.all())
    client.post(f"/projects/{SLUG}/amend", data={"change": "add a cafe"}, follow_redirects=False)
    assert len(STORE.all()) == before


def test_a_web_action_on_an_app_still_reaches_its_stack(client, tmp_path, calls):
    root = app_tree(tmp_path)
    reply = client.post("/projects/gearlist/down", follow_redirects=False)
    assert reply.status_code == 303 and calls == [(["docker", "compose", "down"], str(root.resolve()))]
