"""Resizing the panes, and scrolling the preview.

Both exist because a fixed layout is wrong for somebody: a 24-row terminal
wants the log big and the summary small, a wide one wants the opposite, and a
prototype rendered larger than the pane showing it has to be reachable rather
than cropped.

Textual 8.2.8 ships no splitter, so `protopilot/console/splitter.py` is one.
These tests drive it the two ways a person can — the keyboard chords and a
real mouse drag — because a terminal with mouse reporting off, or a
multiplexer that eats drags, has only the first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from textual.containers import ScrollableContainer
from textual.widgets import Static, TabbedContent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot.console import ConsoleApp  # noqa: E402
from protopilot.console.splitter import Splitter  # noqa: E402
from protopilot.jobs import JobStore  # noqa: E402

pytestmark = pytest.mark.unit

SIZE = (120, 40)


def console(tmp_path) -> ConsoleApp:
    return ConsoleApp(tmp_path, store=JobStore(), runner=lambda *a, **k: None)


# -- the keyboard road ----------------------------------------------------


@pytest.mark.asyncio
async def test_the_input_pane_widens_and_narrows(tmp_path):
    app = console(tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        pane = app.query_one("#input-pane")
        start = pane.size.width

        await pilot.press("ctrl+right")
        await pilot.pause()
        wider = pane.size.width
        assert wider > start, f"{start} -> {wider}"

        await pilot.press("ctrl+left")
        await pilot.press("ctrl+left")
        await pilot.pause()
        assert pane.size.width < wider


@pytest.mark.asyncio
async def test_the_progress_region_grows_and_shrinks(tmp_path):
    app = console(tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        region = app.query_one("#progress-scroll")
        start = region.size.height

        await pilot.press("ctrl+down")
        await pilot.pause()
        taller = region.size.height
        assert taller > start, f"{start} -> {taller}"

        await pilot.press("ctrl+up")
        await pilot.pause()
        assert region.size.height < taller


@pytest.mark.asyncio
async def test_a_pane_cannot_be_driven_to_nothing(tmp_path):
    """A pane dragged or held to zero is a pane nobody can find again, and a
    chord held down is exactly how that happens. Clamped in the splitter rather
    than by each caller, so the mouse path gets it too."""
    app = console(tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        for _ in range(30):
            await pilot.press("ctrl+left")
        await pilot.pause()
        splitter = app.query_one("#split-panes", Splitter)
        # `outer_size`, because that is the box the splitter clamps — `size` is
        # the content box and is smaller by the padding, so comparing it to the
        # limit fails by four cells for a reason that is not a bug.
        assert app.query_one("#input-pane").outer_size.width >= splitter.minimum

        for _ in range(60):
            await pilot.press("ctrl+right")
        await pilot.pause()
        assert app.query_one("#input-pane").outer_size.width <= splitter.maximum


# -- the mouse road -------------------------------------------------------


@pytest.mark.asyncio
async def test_dragging_the_divider_resizes_the_pane_it_names(tmp_path):
    """The divider resizes the pane it was **told** about, not the one that
    happens to sit before it — working that out from the layout would silently
    retarget when somebody reorders `compose()`, and a divider that resizes the
    wrong pane reads as a rendering bug rather than as a moved line.
    """
    from textual import events

    app = console(tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        splitter = app.query_one("#split-panes", Splitter)
        pane = app.query_one("#input-pane")
        start = pane.size.width

        origin = splitter.region.x
        splitter.post_message(
            events.MouseDown(
                x=0,
                y=0,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=origin,
                screen_y=5,
                widget=splitter,
            )
        )
        await pilot.pause()
        splitter.post_message(
            events.MouseMove(
                x=0,
                y=0,
                delta_x=12,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=origin + 12,
                screen_y=5,
                widget=splitter,
            )
        )
        await pilot.pause()

        assert pane.size.width == start + 12, f"{start} -> {pane.size.width}"

        splitter.post_message(
            events.MouseUp(
                x=0,
                y=0,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=origin + 12,
                screen_y=5,
                widget=splitter,
            )
        )
        await pilot.pause()
        assert not splitter.has_class("-dragging"), "the drag never ended; the mouse is still captured"


@pytest.mark.asyncio
async def test_a_move_with_no_drag_in_progress_changes_nothing(tmp_path):
    """The pointer crosses the divider constantly. Only a press starts a drag."""
    from textual import events

    app = console(tmp_path)
    async with app.run_test(size=SIZE) as pilot:
        splitter = app.query_one("#split-panes", Splitter)
        pane = app.query_one("#input-pane")
        start = pane.size.width

        splitter.post_message(
            events.MouseMove(
                x=0,
                y=0,
                delta_x=30,
                delta_y=0,
                button=0,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=splitter.region.x + 30,
                screen_y=5,
                widget=splitter,
            )
        )
        await pilot.pause()
        assert pane.size.width == start


# -- the preview scrolls --------------------------------------------------


@pytest.mark.asyncio
async def test_a_frame_larger_than_the_pane_can_be_scrolled_to(tmp_path):
    """The still screenshot is rendered by the verifier at a fixed 100x30 and
    is not ours to re-render, so on a narrow pane it must be reachable rather
    than cropped."""
    app = console(tmp_path)
    async with app.run_test(size=(70, 24)) as pilot:
        # The tab has to be forward, and that is not test bookkeeping: Textual
        # does not lay out an inactive `TabPane`, so an unshown preview
        # measures zero by zero and every question about its scrolling gets the
        # answer "no" for a reason that has nothing to do with scrolling.
        app.query_one("#views", TabbedContent).active = "tab-preview"
        wide = "\n".join("x" * 100 for _ in range(30))
        app.query_one("#preview", Static).update(wide)
        await pilot.pause()
        await pilot.pause()

        box = app.query_one("#preview-scroll", ScrollableContainer)
        assert box.max_scroll_x > 0, "a 100-column frame in a narrower pane cannot be scrolled sideways"
        assert box.max_scroll_y > 0, "a 30-row frame in a shorter pane cannot be scrolled down"


@pytest.mark.asyncio
async def test_a_frame_that_fits_gets_no_scrollbars(tmp_path):
    app = console(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#views", TabbedContent).active = "tab-preview"
        app.query_one("#preview", Static).update("small")
        await pilot.pause()
        await pilot.pause()
        box = app.query_one("#preview-scroll", ScrollableContainer)
        assert box.max_scroll_x == 0 and box.max_scroll_y == 0
