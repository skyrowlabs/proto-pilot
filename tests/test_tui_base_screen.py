"""`skeleton/tui/app/base.py`, exercised as the shipped file.

`tests/test_tui_skeleton.py` proves the terminal tree renders, boots and can be
read by its own harness. What it does not touch is the base screen every
generated screen inherits: `AppScreen.action_back`, whose whole job is to do
nothing safely, and `AppScreen.db()`, which is how every generated handler
reaches the database.

Both are run **inside a rendered tree**, in a subprocess, against the file that
ships — not a copy of it. Three reasons, in increasing importance:

* `app.base` imports `app.db`, which resolves `APP_DB` at import time. The
  tree's own `conftest.py` redirects it before anything imports it, and that
  ordering is the only fragile thing in the file; importing it into this suite
  would break it or prove nothing about it.
* An in-process import would leave `app`, `app.db` and `app.base` in
  `sys.modules` pointing at a temporary directory that is about to be deleted,
  which is a leak the next test pays for.
* A copied fixture stays green while the shipped file rots. That is the exact
  failure `tests/screen.py` exists to prevent one level down, and it would be
  odd to fall into it while testing the file next to it.

The assertions live in `tests/tui_probe_base_screen.py`, which is a real,
linted, non-collected Python file rather than a string — see its docstring.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from protopilot import targets
from protopilot.render import render_skeleton

# Host-side: no key, no Docker daemon, no browser, no network. A terminal tree
# has nothing to boot, so its base screen is testable here in full.
pytestmark = [pytest.mark.unit]

pytest.importorskip("textual")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pytest_asyncio")

TUI_SKELETON = targets.SKELETON_ROOT / "tui"
PROBE = Path(__file__).resolve().parent / "tui_probe_base_screen.py"


@pytest.fixture()
def tree_with_probe(spec, tmp_path) -> Path:
    """A rendered terminal tree with the probe dropped into its `tests/`.

    `skeleton=` is explicit because there is no `tui` target module to resolve
    it from until Phase 4 of `docs/implementations/spec/terminal-target.md`.
    """
    render_skeleton(spec, tmp_path, skeleton=TUI_SKELETON)
    shutil.copyfile(PROBE, tmp_path / "tests" / "test_base_screen.py")
    return tmp_path


def run_tree_suite(tree: Path, *paths: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *paths],
        cwd=str(tree),
        # No bytecode: a `__pycache__` written into a tree this fixture is
        # about to delete is harmless, but the same run against the SOURCE
        # skeleton would not be, and the habit is cheaper than the distinction.
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_the_base_screen_behaves_as_the_skeleton_promises(tree_with_probe):
    """Escape is safe on the last screen, pops exactly one otherwise, `q`
    quits, and `db()` returns its connection on both the normal and the raising
    path. Every assertion is in `tui_probe_base_screen.py`."""
    result = run_tree_suite(tree_with_probe, "tests/test_base_screen.py")
    assert result.returncode == 0, f"the shipped base screen is red:\n{result.stdout}\n{result.stderr}"


def test_the_probe_is_running_against_the_shipped_file(tree_with_probe):
    """A gate nobody has seen fail is a gate nobody knows works.

    Break `action_back`'s guard in the rendered copy and the probe must go red.
    If it does not, it is testing something other than `skeleton/tui/app/base.py`
    and every assertion above is decoration.
    """
    base = tree_with_probe / "app" / "base.py"
    source = base.read_text()
    assert "if len(self.app.screen_stack) > 1:" in source, "base.py's guard has changed shape; update this test"
    base.write_text(source.replace("if len(self.app.screen_stack) > 1:", "if True:"))

    result = run_tree_suite(tree_with_probe, "tests/test_base_screen.py")
    assert result.returncode != 0, "the probe passed against a base screen that pops the last screen"


PUSHED_HOME_SCREEN = """
    def on_mount(self) -> None:
        Base.metadata.create_all(bind=engine)
        with session() as db:
            seed(db)
        self.push_screen(HomeScreen())
"""


def test_the_probe_catches_a_home_screen_pushed_onto_the_default(tree_with_probe):
    """The regression that actually happened, reintroduced on purpose.

    `app/main.py` pushed `HomeScreen()` from `on_mount` until 2026-09-04.
    Textual keeps a `Screen` of its own at the bottom of the stack, so the home
    screen sat at depth two, `action_back`'s guard never fired, and Escape on
    the first screen popped to a blank default — the exact thing the guard's
    docstring says it prevents.

    The suite was green throughout, because every test built its own app with
    `get_default_screen`. So this is the assertion that the probe is looking at
    the shipped `main.py` and not only at the shipped `base.py`: put the old
    shape back and it must go red.
    """
    main = tree_with_probe / "app" / "main.py"
    source = main.read_text()
    start = source.index("    def get_default_screen(self)")
    end = source.index("def main() -> None:")
    main.write_text(source[:start] + PUSHED_HOME_SCREEN.lstrip("\n") + "\n" + source[end:])

    result = run_tree_suite(tree_with_probe, "tests/test_base_screen.py")
    assert result.returncode != 0, "the probe passed against an app whose home screen is pushed onto a blank one"


def test_the_probe_is_not_collected_by_this_suite():
    """It imports `app.base`, which exists only inside a rendered tree, so
    collecting it here would be an ImportError at collection time — which exits
    2 and takes the whole suite with it. The filename is the whole defence."""
    assert PROBE.exists()
    assert not PROBE.name.startswith("test_")
    assert not PROBE.name.endswith("_test.py")
