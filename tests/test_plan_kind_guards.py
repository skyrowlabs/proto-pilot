"""The guards around a plan tree: what `tree_kind` reads, what `delete` removes, who registers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import NO_REPAIR, edge, script
from research_script import ResearchingLLM

from protopilot import cli, registry
from protopilot.jobs import Job
from protopilot.plan import pipeline
from protopilot.plan.model import plan_path

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


@pytest.fixture
def calls(monkeypatch) -> list:
    """Every `subprocess.call`, recorded instead of run."""
    seen: list = []
    monkeypatch.setattr(subprocess, "call", lambda argv, **kw: seen.append((argv, kw.get("cwd"))) or 0)
    return seen


# ── tree_kind and delete ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "kind"),
    [
        ((), None),
        ((".protopilot/spec.json",), None),
        ((".protopilot/plan.json",), "plan"),
        ((".protopilot/spec.json", ".protopilot/plan.json"), None),
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
        registry.delete(tree)
    assert tree.exists()


def test_deleting_a_plan_whose_protopilot_dir_is_a_link_leaves_the_link_target(tmp_path):
    outside = plant(tmp_path / "outside", "plan.json", "keep.txt")
    tree = tmp_path / "t"
    tree.mkdir()
    (tree / ".protopilot").symlink_to(outside)
    registry.delete(tree)
    assert not tree.exists() and sorted(p.name for p in outside.iterdir()) == ["keep.txt", "plan.json"]


def test_deleting_a_plan_whose_plan_json_is_a_link_leaves_the_file_it_points_at(tmp_path):
    precious = tmp_path / "precious.txt"
    precious.write_text("mine")
    tree = tmp_path / "t"
    (tree / ".protopilot").mkdir(parents=True)
    (tree / ".protopilot" / "plan.json").symlink_to(precious)
    registry.delete(tree)
    assert not tree.exists() and precious.read_text() == "mine"


def test_delete_refuses_the_home_directory_even_when_it_holds_a_plan(tmp_path, monkeypatch):
    home = plant(tmp_path / "home", ".protopilot/plan.json")
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(home)
    assert plan_path(home).exists()


def test_delete_asks_the_tree_not_the_registry_and_runs_nothing(tmp_path, calls):
    tree = plant(tmp_path / "t", ".protopilot/plan.json")
    registry.record(slug="t", name="T", path=tree, kind=registry.APP)
    registry.delete(tree)
    assert (calls, tree.exists(), registry.load()) == ([], False, [])


def test_a_tree_holding_an_older_prototype_is_never_deleted_even_beside_a_plan(tmp_path):
    tree = plant(make_plan(tmp_path / "t"), ".protopilot/spec.json")
    with pytest.raises(registry.NotAProject):
        registry.delete(tree)
    assert plan_path(tree).exists()


# ── what the registry file holds ──────────────────────────────────────


def test_a_plan_entry_round_trips_as_json_null_port_and_kind_plan(tmp_path):
    registry.record(slug="p", name="P", path=tmp_path / "p")
    [raw] = json.loads(registry.registry_path().read_text())
    assert (raw["port"], raw["kind"]) == (None, "plan")
    assert [(e.port, e.kind) for e in registry.load()] == [(None, "plan")]


def test_an_entry_with_an_unknown_kind_is_gone(tmp_path):
    root = plant(tmp_path / "odd", ".protopilot/plan.json")
    registry.record(slug="odd", name="Odd", path=root, kind="banana")
    assert [(e.exists, e.state) for e in registry.load()] == [(False, registry.GONE)]
    result = CliRunner().invoke(cli.main, ["ls"])
    assert result.exit_code == 0 and "gone" in result.output


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
    registry.record(slug="old", name="Old", path=tree, kind=registry.APP)
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
