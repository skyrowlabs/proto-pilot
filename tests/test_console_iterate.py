"""Changing the prototype you have, instead of generating another one.

The failure this exists to prevent: refining an idea by pressing Generate again
with a longer sentence, which throws away everything the last run got right and
costs a full generation to find out whether the new sentence was better. Three
abandoned trees beside the one you meant.

So a change applies to the loaded prototype, in place, on the same job — one
prototype, its history in one transcript.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from textual.widgets import Input, Static

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot.console import ConsoleApp  # noqa: E402
from protopilot.jobs import JobStore  # noqa: E402

pytestmark = pytest.mark.unit

SIZE = (110, 40)


async def until(pilot, predicate, *, ticks: int = 400) -> bool:
    for _ in range(ticks):
        if predicate():
            return True
        await pilot.pause(0.05)
    return False


def console(tmp_path, runner=None, **kw) -> ConsoleApp:
    return ConsoleApp(tmp_path, store=JobStore(), runner=runner, **kw)


def generated(tmp_path):
    """A runner that stands in for a finished generation."""

    def run(job, workspace, **kw):
        tree = Path(workspace) / "pong_simulator"
        tree.mkdir(parents=True, exist_ok=True)
        job.project_dir = str(tree)
        job.event("spec", name="Pong Simulator", slug="pong_simulator", target="tui", archetype="crud")
        job.event("finished", ok=True, attempts=1, project_dir=str(tree), run_hint="")

    return run


async def generate_once(pilot, app, tmp_path):
    app.query_one("#idea", Input).value = "a simple pong simulator"
    await pilot.pause()
    await pilot.click("#start")
    assert await until(pilot, lambda: not app.busy)


@pytest.mark.asyncio
async def test_a_change_amends_the_loaded_tree_and_makes_no_new_one(tmp_path, helper):
    """The assertion that matters is the count of directories.

    A console that "iterated" by generating again would satisfy every other
    check here — same status line, same log, same events — and leave two trees
    on disk. So the workspace is counted before and after.
    """
    amended = []

    def amend(job, project_dir, change, backend=None, demo=True, attempts=3, verifier_factory=None):
        # The real signature, not `**kw`. A stand-in that accepts anything
        # cannot notice the caller passing something the real one does not
        # take — which is the only thing an injected fake is here to check
        # besides being called at all.
        amended.append((str(project_dir), change))
        job.event("amending", name="Pong Simulator", slug="pong_simulator", change=change)
        job.event("finished", ok=True, attempts=1, project_dir=str(project_dir), run_hint="")

    app = console(tmp_path, runner=generated(tmp_path))
    app._amend = amend
    async with app.run_test(size=SIZE) as pilot:
        await generate_once(pilot, app, tmp_path)
        before = sorted(p.name for p in tmp_path.iterdir())
        first_job = app.job

        app.query_one("#change", Input).value = "add a score counter"
        await pilot.pause()
        await pilot.click("#apply")
        assert await until(pilot, lambda: bool(amended))
        assert await until(pilot, lambda: not app.busy)

        assert amended == [(str(tmp_path / "pong_simulator"), "add a score counter")]
        assert sorted(p.name for p in tmp_path.iterdir()) == before, "a change created a second tree"
        assert app.job is first_job, "the change started a new job; the transcript is split"


@pytest.mark.asyncio
async def test_the_pane_names_the_prototype_a_change_would_apply_to(tmp_path, helper):
    """ "Apply this change" is meaningless without "to what"."""
    app = console(tmp_path, runner=generated(tmp_path))
    async with app.run_test(size=SIZE) as pilot:
        assert "nothing loaded" in helper.widget_text(app.query_one("#loaded", Static))

        await generate_once(pilot, app, tmp_path)
        assert await until(pilot, lambda: "pong_simulator" in helper.widget_text(app.query_one("#loaded", Static)))
        assert "Pong Simulator" in helper.widget_text(app.query_one("#loaded", Static))


@pytest.mark.asyncio
async def test_a_change_with_nothing_loaded_is_refused(tmp_path, helper):
    tried = []
    app = console(tmp_path, runner=lambda *a, **k: None)

    def refuse(job, project_dir, change, backend=None, demo=True, attempts=3, verifier_factory=None):
        tried.append(1)

    app._amend = refuse
    async with app.run_test(size=SIZE) as pilot:
        app.query_one("#change", Input).value = "add a score counter"
        await pilot.pause()
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert not tried
        assert "nothing loaded" in helper.widget_text(app.query_one("#status", Static))


@pytest.mark.asyncio
async def test_an_empty_change_is_refused(tmp_path, helper):
    tried = []
    app = console(tmp_path, runner=generated(tmp_path))

    def refuse(job, project_dir, change, backend=None, demo=True, attempts=3, verifier_factory=None):
        tried.append(1)

    app._amend = refuse
    async with app.run_test(size=SIZE) as pilot:
        await generate_once(pilot, app, tmp_path)
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert not tried
        assert "what to change" in helper.widget_text(app.query_one("#status", Static))


@pytest.mark.asyncio
async def test_the_change_box_is_cleared_so_it_is_not_applied_twice(tmp_path, helper):
    """A sentence left in the box after it has been applied is one keystroke
    away from being applied again, to a tree that already has it."""
    app = console(tmp_path, runner=generated(tmp_path))

    def amend(job, project_dir, change, backend=None, demo=True, attempts=3, verifier_factory=None):
        job.event("finished", ok=True, attempts=1, project_dir=str(project_dir), run_hint="")

    app._amend = amend
    async with app.run_test(size=SIZE) as pilot:
        await generate_once(pilot, app, tmp_path)
        app.query_one("#change", Input).value = "add a score counter"
        await pilot.pause()
        await pilot.press("ctrl+e")
        assert await until(pilot, lambda: not app.busy)
        assert app.query_one("#change", Input).value == ""
