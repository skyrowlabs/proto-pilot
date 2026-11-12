"""The registry of plans.

A corrupt registry must never stop a plan: losing the index is recoverable,
and refusing to plan because the index is unreadable is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from protopilot import registry

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


def make_project(tmp_path: Path, slug: str) -> Path:
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "plan.json").write_text("{}")
    return root


def test_record_then_load(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root)
    entries = registry.load()
    assert [(e.slug, e.kind, e.port) for e in entries] == [("gearlist", registry.PLAN, None)]


def test_recording_the_same_path_twice_does_not_duplicate(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root)
    registry.record(slug="gearlist", name="Gear List Again", path=root)
    entries = registry.load()
    assert len(entries) == 1 and entries[0].name == "Gear List Again"


def test_prune_drops_directories_that_are_gone(tmp_path):
    alive = make_project(tmp_path, "alive")
    registry.record(slug="alive", name="Alive", path=alive)
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost")
    assert [e.slug for e in registry.prune()] == ["alive"]


def test_a_corrupt_registry_reads_as_empty_rather_than_raising(tmp_path):
    registry.registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path().write_text("{ not json at all")
    assert registry.load() == []


def test_forget_removes_one_project(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root)
    registry.forget(root)
    assert registry.load() == []


def test_delete_removes_the_tree_and_the_entry(tmp_path):
    root = make_project(tmp_path, "doomed")
    (root / "topics").mkdir()
    (root / "topics" / "one.md").write_text("# One")
    registry.record(slug="doomed", name="Doomed", path=root)
    registry.delete(root)
    assert not root.exists()
    assert registry.load() == []


def test_delete_refuses_a_directory_that_is_not_a_project(tmp_path):
    stranger = tmp_path / "someone_elses_work"
    (stranger / "src").mkdir(parents=True)
    (stranger / "src" / "important.py").write_text("keep me")
    with pytest.raises(registry.NotAProject):
        registry.delete(stranger)
    assert (stranger / "src" / "important.py").exists()


def test_delete_refuses_the_home_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".protopilot").mkdir(exist_ok=True)
    (tmp_path / ".protopilot" / "plan.json").write_text("{}")
    with pytest.raises(registry.NotAProject):
        registry.delete(tmp_path)
    assert tmp_path.exists()


def test_no_test_can_write_to_the_operators_real_registry(tmp_path):
    """The autouse guard in `conftest.py`, asserted rather than assumed.

    Every plan a suite makes calls `registry.record`, and the damage of a
    missing guard is entirely outside the repository, where no gate looks. So
    the check is for the guard itself, not for its effect.

    Derived from the real resolver, not from the environment variable: reading
    the variable back would test that `monkeypatch.setenv` works. `registry_path()`
    is what `record` actually calls.
    """
    from protopilot.registry import _state_home, registry_path

    resolved = registry_path()
    real = _state_home() / "proto-pilot" / "projects.json"
    assert resolved != real, "a test is pointed at the operator's real registry"
    assert str(tmp_path.parent.parent) in str(resolved) or "pytest" in str(
        resolved
    ), f"the registry is neither the real one nor a test one: {resolved}"
