"""Boot the generated app under `App.run_test` and report what it painted.

Run as a subprocess against a generated tree, never imported into the harness:
model-authored code gets a `compose()` that raises, a module-level
`sys.exit()`, an infinite `on_mount`. Any of those inside the harness ends the
measurement instead of failing one run, and the timeout that bounds this one is
the runner's.

Output is a single JSON object on stdout. Everything the app itself prints --
Textual's own logging, a stray `print` in generated code -- goes to stderr,
which is why the payload is written last and to a stream nothing else uses.

    python boot_probe.py            # cwd is the generated tree

The blank-screen check is the whole reason this exists, and it is the terminal
analogue of the browser stage: render the screen buffer, render the buffer of
an application with nothing in it at the same size, and compare. No browser, no
headless Chrome, no optional extra reported as skipped -- two strings.
"""

from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any, Dict

SIZE = (100, 30)


def buffer(app: Any) -> str:
    """The rendered screen, as text.

    `screen._compositor.render_strips()` is the composited result -- what a
    terminal would actually receive. `Screen.render_lines` is not: it renders
    the screen widget itself and returns blank rows for an app whose content is
    all in its children, which is every app here. Getting this wrong reports a
    working app as blank, so it is checked in the spike's own test.
    """
    compositor = app.screen._compositor
    return "\n".join(strip.text for strip in compositor.render_strips())


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
        # Drive it, rather than only looking at it. A screen that paints once
        # and raises on the first keystroke is not a working app, and Tab is
        # the one key every Textual app has whatever its bindings are.
        await pilot.press("tab")
        await pilot.pause()
        after = buffer(app)

    return {
        "ok": True,
        "painted": painted != empty,
        "screen": screen,
        "widgets": widgets,
        "changed_on_key": after != painted,
        "buffer": painted,
        "empty_buffer": empty,
    }


def main() -> int:
    try:
        result = asyncio.run(probe())
    except BaseException:  # noqa: BLE001 -- reporting the failure is the job
        result = {"ok": False, "painted": False, "traceback": traceback.format_exc()}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
