"""`proto console` — the tool's own front end, driven headless.

Every test here runs through Textual's `App.run_test` pilot, which is the same
mechanism `verify_tui` already uses to check a generated terminal tree — so the
console is tested by the machinery it ships rather than by a new dependency.

No key, no Docker daemon, no browser. The generation path is the real one; only
the *latency* is faked, and only where a test needs to look at the panes while
a run is still in flight.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from textual.widgets import Input, RichLog, Static  # noqa: E402

from protopilot.console import ConsoleApp  # noqa: E402
from protopilot.jobs import JobStore  # noqa: E402

pytestmark = pytest.mark.unit

SIZE = (100, 40)


def log_text(app: ConsoleApp) -> str:
    """What the log pane holds, as a person would read it."""
    pane = app.query_one("#log", RichLog)
    return "\n".join(str(line) for line in pane.lines)


def widget_text(helper, app: ConsoleApp, selector: str) -> str:
    """A `Static`'s text, through the skeleton's reader.

    Not `.renderable`: that attribute does not exist on the Textual installed
    here, so a helper reading only it sees an empty screen and reports a working
    pane as broken. `tests/screen.py` already knows the three names that text
    has had, and it is loaded from the skeleton rather than copied -- see the
    `helper` fixture in `conftest.py`.
    """
    return helper.widget_text(app.query_one(selector, Static))


async def until(pilot, predicate, *, ticks: int = 600) -> bool:
    """Pump the app until `predicate` holds, or give up.

    Waiting on `app.busy` is the tempting version and it is wrong: the panes are
    drawn on a timer, so a job that finishes between two ticks leaves the screen
    one frame behind the job. A test that stops at `not busy` then reads a pane
    that is *correct but not yet drawn* and fails intermittently. So every wait
    here is on the thing being asserted.
    """
    for _ in range(ticks):
        if predicate():
            return True
        await pilot.pause(0.05)
    return False


async def type_idea(pilot, idea: str = "a tiny notes app") -> None:
    app = pilot.app
    app.query_one("#idea", Input).value = idea
    await pilot.pause()


def console(tmp_path, runner=None, **kw) -> ConsoleApp:
    """A console with its own store, so tests never share the process-wide one."""
    return ConsoleApp(tmp_path, store=JobStore(), runner=runner, **kw)


# -- the whole thing, offline ---------------------------------------------


@pytest.mark.asyncio
async def test_the_console_generates_end_to_end_with_no_key_and_no_daemon(tmp_path, helper):
    """The acceptance case: an idea in, a tree out, entirely offline.

    The real `generation.run_generation` -- no injected runner -- against the
    default target, which is the terminal one and wants nothing from Docker.
    """
    app = console(tmp_path, backend="offline")
    async with app.run_test(size=SIZE) as pilot:
        await type_idea(pilot)
        await pilot.click("#start")
        assert await until(
            pilot, lambda: "green" in widget_text(helper, app, "#progress")
        ), f"{app.job.error if app.job else 'no job'}\n{log_text(app)}"
        assert app.job is not None and app.job.status == "done"
        tree = Path(app.job.project_dir)
        assert (tree / "app" / "models.py").exists(), "no tree was generated"
        assert "green" in widget_text(helper, app, "#progress"), widget_text(helper, app, "#progress")
        assert "finished" in widget_text(helper, app, "#status")


@pytest.mark.asyncio
async def test_the_panes_fill_while_the_run_is_still_going(tmp_path, helper):
    """Asserted on a **partial** log mid-run, never on the final one.

    A pane that fills only at the end passes any test that waits for the job to
    finish first, and is exactly the failure this front end exists to avoid --
    worse than the CLI it replaces, which at least prints as it goes. So the
    runner is held open on an event and the panes are read while it is blocked.
    """
    released = threading.Event()

    def slow(job, workspace, **kw):
        job.log("intake...")
        job.event("plan", passes=["schema", "smoke"])
        job.event("pass_started", name="schema", index=1, of=2)
        released.wait(timeout=10)
        job.log("  pass smoke...")

    app = console(tmp_path, runner=slow)
    try:
        async with app.run_test(size=SIZE) as pilot:
            await type_idea(pilot)
            await pilot.click("#start")
            assert await until(pilot, lambda: "intake" in log_text(app), ticks=200)
            assert app.busy, "the job finished before the panes could be read"
            assert "intake..." in log_text(app), "the log pane was still empty mid-run"
            assert "smoke" not in log_text(app), "this asserts on a partial log, not a finished one"
            assert "▸ schema" in widget_text(helper, app, "#progress"), widget_text(helper, app, "#progress")

            released.set()
            assert await until(
                pilot, lambda: "pass smoke" in log_text(app), ticks=200
            ), "the rest of the log never arrived"
    finally:
        released.set()


# -- one at a time --------------------------------------------------------


@pytest.mark.asyncio
async def test_a_second_generation_is_refused_by_name_not_interleaved(tmp_path, helper):
    """`JobStore.run` redirects `sys.stdout`, which is process-global, so two
    jobs would clobber each other's capture and braid two transcripts into one
    pane. Until that is per-job the console runs one at a time -- and says so,
    naming what it is busy with, because a button that silently does nothing is
    indistinguishable from one that is broken."""
    released = threading.Event()
    started = []

    def slow(job, workspace, **kw):
        started.append(job.id)
        released.wait(timeout=10)

    app = console(tmp_path, runner=slow)
    try:
        async with app.run_test(size=SIZE) as pilot:
            await type_idea(pilot, "the first idea")
            await pilot.click("#start")
            assert await until(pilot, lambda: bool(started), ticks=200)
            first = app.job

            # The keybinding, not a second `pilot.click`. Repeat clicks at the
            # same position are coalesced by Textual's pilot -- measured here on
            # a minimal app, where three clicks delivered two presses -- so a
            # click-based version of this test would pass whether the refusal
            # worked or not. `ctrl+r` is a real user path and is not coalesced.
            # The button itself is exercised by every other test in this file.
            await type_idea(pilot, "the second idea")
            await pilot.press("ctrl+r")
            await pilot.pause()

            assert len(started) == 1, "a second generation started alongside the first"
            assert app.job is first, "the console swapped which job it was showing"
            assert "the first idea" in widget_text(helper, app, "#status"), widget_text(helper, app, "#status")
            assert "one at a time" in widget_text(helper, app, "#status")
    finally:
        released.set()


# -- the floor ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_run_that_fails_still_renders_rather_than_going_blank(tmp_path, helper):
    """The pipeline's floor must be visible in the pane, not only on disk."""

    def explode(job, workspace, **kw):
        job.log("intake...")
        raise RuntimeError("the model said no")

    app = console(tmp_path, runner=explode)
    async with app.run_test(size=SIZE) as pilot:
        await type_idea(pilot)
        await pilot.click("#start")
        assert await until(pilot, lambda: "the model said no" in widget_text(helper, app, "#status")), widget_text(
            helper, app, "#status"
        )
        assert app.job is not None and app.job.status == "failed", widget_text(helper, app, "#status")
        assert "intake..." in log_text(app), "the log up to the failure was thrown away"


@pytest.mark.asyncio
async def test_a_red_run_names_the_stage_and_the_runbook(tmp_path, helper):
    """A generation that ends red is `done`, not `failed` -- the tree is handed
    back deliberately. The pane has to say which, or a red run reads as a green
    one that produced nothing."""

    def red(job, workspace, **kw):
        job.event("plan", passes=["schema"])
        job.event("pass_started", name="schema", index=1, of=1)
        job.event("pass_done", name="schema", index=1, of=1, files=["app/models.py"])
        job.event("verify_started", attempt=1, of=3)
        job.event("verify_failed", attempt=1, stage="smoke", summary="2 of 7 failed")
        job.event("exhausted", attempts=1, stage="smoke")
        job.project_dir = str(workspace / "tree")
        job.event("finished", ok=False, attempts=1, project_dir=job.project_dir, run_hint="cd {directory} && make run")

    app = console(tmp_path, runner=red)
    async with app.run_test(size=SIZE) as pilot:
        await type_idea(pilot)
        await pilot.click("#start")
        assert await until(pilot, lambda: "red at" in widget_text(helper, app, "#progress"))
        text = widget_text(helper, app, "#progress")
        assert "red at smoke" in text, text
        assert "RUNBOOK.md" in text, "the floor the pipeline already has is invisible in the pane"


# -- guards before anything is spent --------------------------------------


@pytest.mark.asyncio
async def test_an_empty_idea_is_refused_before_a_job_exists(tmp_path, helper):
    ran = []
    app = console(tmp_path, runner=lambda *a, **k: ran.append(1))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.click("#start")
        await pilot.pause()
        assert not ran and app.job is None
        assert "an idea first" in widget_text(helper, app, "#status")


@pytest.mark.asyncio
async def test_an_unsupported_pair_is_refused_before_anything_is_spent(tmp_path, helper, monkeypatch):
    """The same check the CLI makes, at the same point: before the job exists.

    A console that started a generation and only discovered the pair was
    impossible three passes in would have spent the tokens to learn what the
    registry knew from the first frame.

    `check_pair` is **made** to refuse rather than hunting for a pair that
    already does. Every target currently supports every archetype, so the
    honest version of that search skips — and a test that skips forever is a
    test that has never run. Which pairs exist is `protopilot/targets`' business
    and is covered there; what this file owns is that the console *asks*, and
    stops when the answer is no.
    """
    from protopilot import targets
    from protopilot.console import app as console_app

    def refuse(target, archetype):
        # The real exception, built the real way -- it composes its own message
        # from all three fields, and a stand-in raising a bare ValueError would
        # not prove the console surfaces what the registry actually says.
        raise targets.UnsupportedPair(target, archetype, ("crud",))

    monkeypatch.setattr(console_app.targets, "check_pair", refuse)

    ran = []
    app = console(tmp_path, runner=lambda *a, **k: ran.append(1))
    async with app.run_test(size=SIZE) as pilot:
        await type_idea(pilot)
        await pilot.click("#start")
        await pilot.pause()

        assert not ran, "a generation started on a pair the registry rejects"
        assert app.job is None, "a job was created before the pair was checked"
        shown = widget_text(helper, app, "#status")
        assert "cannot build" in shown and "it builds: crud" in shown, shown


@pytest.mark.asyncio
async def test_the_recent_list_shows_past_runs_and_marks_the_current_one(tmp_path, helper):
    """Seeing the last few runs is most of what the list is for: it is what
    makes two ideas comparable, which a single-shot CLI cannot do at all.

    Read from the store, not from a list the app keeps for itself — the web
    front end shares `STORE`, so a job started there belongs here too.
    """
    app = console(tmp_path, runner=lambda job, workspace, **kw: None)
    async with app.run_test(size=SIZE) as pilot:
        for idea in ("a notes app", "a chess clock"):
            await type_idea(pilot, idea)
            await pilot.press("ctrl+r")
            assert await until(pilot, lambda: not app.busy, ticks=200)
            await pilot.pause(0.3)

        shown = widget_text(helper, app, "#jobs")
        assert "a notes app" in shown and "a chess clock" in shown, shown
        # Both finished, so both are ticked; the arrow marks the one on screen.
        assert shown.count("✓") >= 2, shown
        assert "a chess clock ←" in shown, f"the current run is not marked: {shown}"
        assert "a notes app ←" not in shown, "an older run is marked as current"


@pytest.mark.asyncio
async def test_a_long_idea_is_truncated_rather_than_breaking_the_column(tmp_path, helper):
    """The input pane is a fixed 34 cells. An idea is free-form text a person
    typed, so it is the one value here with no bound at all."""
    app = console(tmp_path, runner=lambda job, workspace, **kw: None)
    async with app.run_test(size=SIZE) as pilot:
        await type_idea(pilot, "a" * 200)
        await pilot.press("ctrl+r")
        assert await until(pilot, lambda: not app.busy, ticks=200)
        await pilot.pause(0.3)

        row = next(line for line in widget_text(helper, app, "#jobs").splitlines() if "aaa" in line)
        assert len(row) < 40, f"the row is {len(row)} cells wide in a 34-cell pane: {row!r}"
        assert row.rstrip("←").rstrip().endswith("…"), row


# -- the name, which is the one thing that must not drift -----------------


def test_nothing_in_the_console_package_is_called_tui():
    """`tui` is the terminal **target** -- what `proto` emits -- and it already
    means that in five modules. A front end module called `tui` anything would
    be read as one of them by the next person, and they would be right to.
    """
    import protopilot.console as pkg

    root = Path(pkg.__file__).parent
    offenders = [p.name for p in root.rglob("*") if "tui" in p.name.lower()]
    assert not offenders, f"the console package must not use the target's name: {offenders}"
