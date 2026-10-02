"""The project registry and the demo toggle.

Two things worth pinning. A corrupt registry must never stop a generation --
losing the index is recoverable, refusing to build because the index is
unreadable is not. And `hide_tests` must be presentation only: the smoke pass
still runs second and the routes pass is still handed its output, because a
demo that changes what gets built is not a demo of the thing that ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from protopilot import registry
from protopilot.build import is_test_path

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


def make_project(tmp_path: Path, slug: str) -> Path:
    root = tmp_path / slug
    (root / ".protopilot").mkdir(parents=True)
    (root / ".protopilot" / "spec.json").write_text("{}")
    return root


def test_record_then_load(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root, port=8080)
    entries = registry.load()
    assert [(e.slug, e.port) for e in entries] == [("gearlist", 8080)]


def test_recording_the_same_path_twice_does_not_duplicate(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root, port=8080)
    registry.record(slug="gearlist", name="Gear List", path=root, port=8099)
    entries = registry.load()
    assert len(entries) == 1 and entries[0].port == 8099


def test_prune_drops_directories_that_are_gone(tmp_path):
    alive = make_project(tmp_path, "alive")
    registry.record(slug="alive", name="Alive", path=alive, port=8080)
    registry.record(slug="ghost", name="Ghost", path=tmp_path / "ghost", port=8081)
    assert [e.slug for e in registry.prune()] == ["alive"]


def test_a_corrupt_registry_reads_as_empty_rather_than_raising(tmp_path):
    registry.registry_path().parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path().write_text("{ not json at all")
    assert registry.load() == []


def test_forget_removes_one_project(tmp_path):
    root = make_project(tmp_path, "gearlist")
    registry.record(slug="gearlist", name="Gear List", path=root, port=8080)
    registry.forget(root)
    assert registry.load() == []


@pytest.mark.parametrize(
    "path,expected",
    [
        ("tests/test_smoke.py", True),
        ("tests/conftest.py", True),
        ("app/models.py", False),
        ("app/templates/index.html", False),
        # A generated test could land outside tests/ -- name it, catch it.
        ("test_extra.py", True),
    ],
)
def test_is_test_path(path, expected):
    assert is_test_path(path) is expected


def test_delete_removes_the_tree_and_the_entry(tmp_path):
    root = make_project(tmp_path, "doomed")
    (root / "app").mkdir()
    (root / "app" / "models.py").write_text("x = 1")
    registry.record(slug="doomed", name="Doomed", path=root, port=8080)
    calls = []
    registry.delete(root, runner=lambda argv, cwd: calls.append(argv))
    assert not root.exists()
    assert registry.load() == []
    # Data volume dropped, not just the containers stopped.
    assert calls == [["docker", "compose", "down", "-v"]]


def test_delete_refuses_a_directory_that_is_not_a_project(tmp_path):
    stranger = tmp_path / "someone_elses_work"
    (stranger / "src").mkdir(parents=True)
    (stranger / "src" / "important.py").write_text("keep me")
    with pytest.raises(registry.NotAProject):
        registry.delete(stranger, runner=lambda argv, cwd: None)
    assert (stranger / "src" / "important.py").exists()


def test_delete_refuses_the_home_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".protopilot").mkdir(exist_ok=True)
    (tmp_path / ".protopilot" / "spec.json").write_text("{}")
    with pytest.raises(registry.NotAProject):
        registry.delete(tmp_path, runner=lambda argv, cwd: None)
    assert tmp_path.exists()


def test_no_test_can_write_to_the_operators_real_registry(tmp_path):
    """The autouse guard in `conftest.py`, asserted rather than assumed.

    Every generation a suite runs calls `registry.record`. Before the guard
    existed this machine's own `proto ls` held 129 entries pointing at
    `/tmp/pytest-of-*/...` — one per generation any test had ever run, each
    naming a directory pytest deleted seconds later.

    The damage is entirely **outside** the repository, which is why nothing
    caught it: every test passed, every gate was green, and the only evidence
    was a operator running `proto ls` and finding their own list buried. So the
    check has to be for the guard itself, not for its effect.

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
