"""Shared fixtures and the environment-gate helper.

The one rule worth reading before writing a test: **a skip in CI is a failure**.
CI guarantees the environment, so "the service was not reachable" there means
the harness broke — and a harness that silently skips its whole suite reports
green, which is the single most expensive failure mode a test suite has.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Bootstrap only, and it runs before any test module is collected: put the
# package on sys.path so tests can import `scripts.paths`, which owns every
# path in the tree. A bare `pytest tests/` otherwise gets only `tests/`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Set by CI and by `pp test --ci`. Under it, an env-gate skip becomes a failure.
CI_FLAG = "PP_CI"


def in_ci() -> bool:
    return os.environ.get(CI_FLAG) == "1"


def require_or_skip(condition: bool, reason: str, *, requires: str | None = None) -> None:
    """Skip locally, **fail** in CI.

    Use for anything CI guarantees — services running, seed data present, a
    toolchain installed. Raw ``pytest.skip`` stays legitimate for genuine
    cross-environment conditions CI does not guarantee (a GPU, a paid API key).

        require_or_skip(services_up, "the app is not reachable", requires="services")
    """
    if condition:
        return
    detail = f"{reason} (requires: {requires})" if requires else reason
    if in_ci():
        pytest.fail(f"environment gate failed in CI: {detail}. CI guarantees this — the harness is broken.")
    pytest.skip(detail)


@pytest.fixture(scope="session")
def repo_root():
    """The project root, from the module that owns it — never re-derived here.

    A fixture that works this out for itself is a second answer to a question
    with one owner, and it is the answer a test would trust. See
    `scripts/paths.py`.
    """
    from scripts.paths import PROJECT_ROOT

    return PROJECT_ROOT


@pytest.fixture(autouse=True)
def _never_the_users_state(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the state root at a fresh directory for every test.

    Unset, it falls back to the user's real state under the home directory, so a
    test that forgot it would write there. A test that sets its own still wins,
    because autouse fixtures run first. stash.flow's incident: `stash-flow@c5544b3`.
    """
    from scripts.paths import STATE_ROOT_ENV

    monkeypatch.setenv(STATE_ROOT_ENV, str(tmp_path_factory.mktemp("state-root")))


@pytest.fixture(autouse=True)
def _never_the_users_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail a test that would open the user's real browser.

    A test that means to open one replaces it with a recorder, which wins
    because it is patched later. stash.flow's incident: `stash-flow@a2fe3b7`.
    """
    import webbrowser

    def refuse(name: str):
        def refused(*args, **kwargs):
            raise AssertionError(f"a test reached the real webbrowser.{name}{args!r}; replace it with a recorder")

        return refused

    for name in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, name, refuse(name))


@pytest.fixture(autouse=True)
def _never_the_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a unit test on loopback and away from every secret-shaped variable. See `tests/guards.py`.

    Other suites may reach real services by design. A test that patches the socket
    itself still wins, because it is patched later.
    """
    if request.node.get_closest_marker("unit") is None:
        return
    from tests.guards import hide_secrets, refuse_remote

    hide_secrets(monkeypatch)
    refuse_remote(monkeypatch)


# ── Your fixtures go below this line ──────────────────────────────────────────
#
# skeletor adds its fixtures above this block and renders nothing below it, so a
# release's new fixture and yours are never adjacent and merge cleanly. The block
# itself is frozen. Asked for by proto.pilot, whose fixtures at the end of this
# file conflicted with the template's at v0.49.0 and again at v0.51.0.


# ── proto.pilot's own fixtures ──────────────────────────────────────────


@pytest.fixture()
def spec():
    """Two entities, a parent/child relationship, and every field type.

    Every type is present on purpose: the column mapping, the form input, the
    coercion helper and the seed literal are four separate tables in
    baseline.py, and a type missing from any one of them produces a tree that
    fails at a different stage each time.
    """
    from protopilot.spec import Entity, Field_, Spec

    return Spec(
        name="Gear List",
        slug="gearlist",
        purpose="Track camping gear across trips.",
        port=8099,
        entities=[
            Entity(
                name="Trip",
                fields=[
                    Field_(name="title", type="str"),
                    Field_(name="starts_on", type="date"),
                    Field_(name="notes", type="text", required=False),
                    Field_(name="nights", type="int", required=False),
                ],
            ),
            Entity(
                name="Item",
                belongs_to="Trip",
                fields=[
                    Field_(name="name", type="str"),
                    Field_(name="packed", type="bool", required=False),
                    Field_(name="weight_kg", type="float", required=False),
                    Field_(name="checked_at", type="datetime", required=False),
                ],
            ),
        ],
    )


# ── reading what a Textual app is actually showing ───────────────────────


@pytest.fixture(scope="module")
def helper():
    """`tests/screen.py`, loaded from the skeleton rather than copied here.

    Lives here because two suites need it: the skeleton's own tests, and the
    console's. `Static.renderable` does not exist on the Textual installed
    here — a harness reading only that sees an empty screen and reports a
    working app as broken — so this is the repository's one answer to how a
    widget's text is read, and a second copy is how one of them goes stale.

    Loaded, not copied: a copy would be tested against itself and would stay
    green while the shipped one rotted, which is the shape of defect
    `tests/test_tui_skeleton.py` exists to prevent one level up.

    `sys.dont_write_bytecode` rather than `PYTHONDONTWRITEBYTECODE`, and the
    distinction is the whole of why this works: the environment variable is
    read once, at interpreter start, into that attribute — so setting it from
    inside a running test does nothing at all. Without it, `exec_module` writes
    a `__pycache__` into `skeleton/tui/tests/`, which is source data copied
    byte-for-byte into every generated prototype. It is gitignored, so the cost
    today is cosmetic; `test_tui_skeleton.py` already excludes `__pycache__`
    by name when it walks the skeleton, because a `.pyc` read as text is a
    `UnicodeDecodeError` in a test whose failure message is then about nothing.
    """
    import importlib.util

    from protopilot import targets

    path = targets.SKELETON_ROOT / "tui" / "tests" / "screen.py"
    spec_ = importlib.util.spec_from_file_location("skeleton_tui_screen", path)
    assert spec_ and spec_.loader
    module = importlib.util.module_from_spec(spec_)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec_.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ── nothing here touches the operator's real state ───────────────────────


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point `PROTOPILOT_REGISTRY` at a throwaway file for **every** test.

    Any test that runs a real generation calls `registry.record`, which writes
    to the operator's own registry unless told otherwise. `proto ls` on this
    machine had 129 entries pointing at `/tmp/pytest-of-*/...` before this
    existed — one per generation any suite had ever run, each one a directory
    pytest deleted seconds later.

    **Autouse and here, rather than per-file.** `test_verifier_wiring.py` had
    exactly this fixture already and it worked, which is precisely the problem:
    a protection that each new test file has to remember is one that the next
    file forgets, and the failure is invisible from inside the suite — every
    test passes, and the damage is to a file outside the repository that
    nothing checks.

    The same shape as the scan guards in `tests/scanning.py`: put it where it
    cannot be omitted rather than where it has to be repeated.
    """
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "registry" / "projects.json"))
