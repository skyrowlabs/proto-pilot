"""The registry against what it did not write: odd kinds, older rows, shared slugs, unsafe roots, racing writers."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from click.testing import CliRunner

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


# ── B3: one idea, an older prototype's row and a plan ────────────────


def test_an_old_row_and_a_plan_from_one_idea_get_different_slugs(tmp_path):
    registry.record(slug=SLUG, name="App", path=app_at(tmp_path / "app"), kind=registry.APP)
    make_plan(tmp_path / "plan")
    slugs = [e.slug for e in registry.load()]
    assert len(set(slugs)) == 2 and SLUG in slugs


def test_rerecording_one_path_keeps_its_slug(tmp_path):
    registry.record(slug="gear", name="A", path=tmp_path / "a")
    registry.record(slug="gear", name="B", path=tmp_path / "b")
    registry.record(slug="gear", name="B", path=tmp_path / "b")
    assert sorted(e.slug for e in registry.load()) == ["gear", "gear_2"]


# ── a registry file an older version wrote ───────────────────────────


def test_a_registry_written_by_0_3_0_loses_no_row_until_a_person_prunes(tmp_path):
    plan, odd = make_plan(tmp_path / "plan"), make_plan(tmp_path / "odd")
    web, bare = app_at(tmp_path / "web"), app_at(tmp_path / "bare")
    write_raw(
        [
            {
                "slug": "web",
                "name": "Web",
                "path": str(web),
                "port": 8080,
                "created_at": "x",
                "idea": "",
                "kind": "app",
            },
            {"slug": "bare", "name": "Bare", "path": str(bare), "port": 8081, "created_at": "x"},
            {"slug": "plan", "name": "Plan", "path": str(plan), "port": None, "created_at": "x", "kind": "plan"},
            {"slug": "odd", "name": "Odd", "path": str(odd), "created_at": "x", "kind": "plan", "later": 1},
        ]
    )

    listed = CliRunner().invoke(cli.main, ["ls"])
    assert listed.exit_code == 0 and listed.output.count("  old ") == 2, listed.output
    assert "no longer runs prototypes" in listed.output and "proto prune" in listed.output
    registry.record(slug="new", name="New", path=make_plan(tmp_path / "new"))
    rows = {e.slug: e for e in registry.load()}
    assert {"web", "bare", "plan", "odd"} <= set(rows)
    assert rows["web"].port == 8080 and rows["bare"].kind == registry.APP and rows["plan"].port is None

    pruned = CliRunner().invoke(cli.main, ["prune", "--yes"])
    assert pruned.exit_code == 0 and "0 gone, 2 old" in pruned.output
    assert {e.slug for e in registry.load()} == {"plan", "odd", "new"}
    assert web.exists() and bare.exists(), "prune forgets rows and never touches a folder"


# ── B4: a root that holds home, or the registry itself ───────────────


def test_delete_refuses_a_parent_of_home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    (tmp_path / ".protopilot").mkdir()
    (tmp_path / ".protopilot" / "plan.json").write_text("{}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(tmp_path)
    assert (tmp_path / "home").exists()


def test_delete_refuses_a_tree_that_holds_the_registry(tmp_path, monkeypatch):
    tree = make_plan(tmp_path / "t")
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tree / "inside" / "projects.json"))
    registry.record(slug="x", name="X", path=tree)
    with pytest.raises(registry.NotAProject, match="not a safe path"):
        registry.delete(tree)
    assert registry.registry_path().exists()


# ── writers that race ────────────────────────────────────────────────


def test_concurrent_records_lose_no_entry(tmp_path):
    def write(n: int) -> None:
        for i in range(25):
            registry.record(slug=f"s{n}_{i}", name="S", path=tmp_path / f"t{n}_{i}")

    threads = [threading.Thread(target=write, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(registry.load()) == 150


def test_save_leaves_no_partial_file_behind(tmp_path):
    registry.record(slug="a", name="A", path=tmp_path / "a")
    folder = registry.registry_path().parent
    assert sorted(p.name for p in folder.iterdir() if not p.name.endswith(".lock")) == ["projects.json"]
