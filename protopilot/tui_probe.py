"""Boot a generated terminal app, drive it, and report what it painted.

Run as a **subprocess** against a generated tree, never imported into the
process doing the verifying:

    APP_DB=... PYTHONPATH=<tree> python protopilot/tui_probe.py

Model-authored code gets a `compose()` that raises, a module-level
`sys.exit()`, an infinite `on_mount`. Any of those inside the harness ends the
run instead of failing one verification, and the timeout that bounds this one
belongs to the `Runner` that started it.

Output is a single JSON object on the last line of stdout. Everything the app
itself prints -- Textual's own logging, a stray `print` in generated code --
goes to stderr, which is why the payload is written last and to a stream
nothing else uses.

## The blank-screen check

This is the terminal analogue of the browser stage, and the reason
`docs/implementations/spec/terminal-target.md` Phase 5 is the optimistic half of that plan:
render the app's screen buffer, render the buffer of an application with
nothing in it at the same size, and compare two strings. No browser, no
headless Chrome, no optional extra that gets reported as skipped -- and unlike
the browser stage it is available on every machine, so it never has to hand
back a green it did not earn.

The comparison is against a live empty app rather than against `""`. A Textual
application with nothing in it still paints: a background, and whatever the
theme puts behind it. Comparing to an empty string would call every app
painted, which is the one answer that makes the check worthless.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

#: The terminal size the app is rendered at. Wide enough that a table with a
#: few columns is not truncated into nothing, which would read as a blank
#: screen for a reason that is the harness's fault.
SIZE = (100, 30)

# This file's own directory is `protopilot/`, and CPython puts a script's
# directory at the front of `sys.path`. Left there, `protopilot/spec.py`,
# `build.py` and friends become importable as top-level modules inside a
# generated tree that has nothing to do with them. Nothing needs them here.
_HERE = str(Path(__file__).resolve().parent)
sys.path[:] = [entry for entry in sys.path if entry not in ("", _HERE)]


def buffer(app: Any) -> str:
    """The composited screen, as a terminal would receive it.

    `screen._compositor.render_strips()` and **not** `Screen.render_lines`: the
    second renders the screen widget itself and returns blank rows for an app
    whose content is all in its children, which is every app here. Getting this
    wrong reports a working app as blank, and the failure is silent -- the run
    reads as a competence failure of whatever generated the screens.
    """
    return "\n".join(strip.text for strip in app.screen._compositor.render_strips())


def readable(app: Any) -> str:
    """What a person could read on the top screen, or "" if we cannot tell.

    Uses the tree's own `tests/screen.py`, which is skeleton and is the one
    place that knows where Textual is currently keeping a `Static`'s text --
    an attribute that has moved three times. Diagnostic only: the verdict below
    is the buffer comparison, because a screen that legitimately draws a chart
    and no words is a working screen.
    """
    try:
        from tests.screen import screen_text  # noqa: PLC0415 -- the tree's, not ours

        return screen_text(app.screen)
    except Exception:  # noqa: BLE001 -- a tree without the helper still verifies
        return ""


async def probe() -> Dict[str, Any]:
    from app.main import TerminalApp
    from textual.app import App

    class Blank(App):
        """An application with nothing in it. The empty buffer to compare to."""

    blank = Blank()
    async with blank.run_test(size=SIZE) as pilot:
        await pilot.pause()
        empty = buffer(blank)

    app = TerminalApp()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.pause()
        painted = buffer(app)
        screen = type(app.screen).__name__
        widgets = len(list(app.screen.query("*")))
        text = readable(app)
        depth = len(app.screen_stack)
        # Driven, not only looked at. A screen that paints once and raises on
        # the first keystroke is not a working app, and Tab is the one key
        # every Textual app has whatever its own bindings are.
        await pilot.press("tab")
        await pilot.pause()
        after = buffer(app)

    return {
        "ok": True,
        "painted": painted != empty,
        "screen": screen,
        "widgets": widgets,
        "depth": depth,
        "text": text[:2000],
        "changed_on_key": after != painted,
        "buffer": painted,
        "empty_buffer": empty,
    }


def main() -> int:
    try:
        result = asyncio.run(probe())
    except BaseException:  # noqa: BLE001 -- reporting the failure IS the job
        result = {"ok": False, "painted": False, "traceback": traceback.format_exc()}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
