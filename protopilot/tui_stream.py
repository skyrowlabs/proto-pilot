"""Boot a generated terminal app and keep it running, streaming its screen.

The live counterpart to `tui_probe.py`. The probe boots an app, takes one
reading and exits — which is what a verifier wants and is a photograph. This
holds the app open and answers requests: send a key, get the frame it produced;
ask for a frame, get the current one. An app with a timer therefore animates.

Run as a **subprocess** against a generated tree, exactly as the probe is:

    APP_DB=... PYTHONPATH=<tree> python protopilot/tui_stream.py

## Why a subprocess and not an import

Two Textual `App`s cannot share one process — `App.run()` owns the terminal —
which is the constraint that ruled out embedding a *running* prototype in a
pane. This is the way around it that does not need a PTY or a terminal-emulator
widget: the generated app runs in its own process under `App.run_test`, which
composites to a buffer instead of to a terminal, and the buffer is what crosses
the pipe. The console then draws that text like any other text.

It is not a terminal emulator and does not pretend to be. What it gives is the
app's own screen, refreshed on demand and on every keystroke, from the real app
with its real state — the same thing the verifier looks at, held open.

And it keeps the isolation the probe was written for: model-authored code with
a `compose()` that raises, a module-level `sys.exit()` or an infinite `on_mount`
ends *this* process and is reported, rather than taking the console down with it.

## The protocol

Newline-delimited JSON both ways, because a frame is multi-line text and a
line-oriented pipe is the one thing both ends already agree on.

Requests (stdin):   {"key": "left"}   {"frame": true}   {"quit": true}
Replies  (stdout):  {"frame": "...", "n": 3}   {"error": "...", "fatal": true}

**Frames go to the real stdout, captured before the app can touch it**, and
`sys.stdout` is pointed at stderr for the app's own lifetime. Generated code
prints; Textual's logging prints. Either would land in the middle of a JSON
line and desynchronise the stream, and the failure would look like a corrupt
frame rather than like a stray `print`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

#: The same size the probe renders at, so a frame here and a frame there are
#: comparable. Wide enough that a table with a few columns is not truncated
#: into nothing, which would read as a blank screen for a reason that is the
#: harness's fault.
SIZE = (100, 30)

#: Captured before anything else can rebind it. See the module docstring.
_OUT = sys.stdout

# This file's own directory is `protopilot/`, and CPython puts a script's
# directory at the front of `sys.path`. Left there, `protopilot/spec.py` and
# friends become importable as top-level modules inside a generated tree that
# has nothing to do with them.
_HERE = str(Path(__file__).resolve().parent)
sys.path[:] = [entry for entry in sys.path if entry not in ("", _HERE)]


def send(payload: dict) -> None:
    _OUT.write(json.dumps(payload) + "\n")
    _OUT.flush()


def buffer(app: Any) -> str:
    """The composited screen, as a terminal would receive it.

    `screen._compositor.render_strips()` and **not** `Screen.render_lines`:
    the second renders the screen widget itself and returns blank rows for an
    app whose content is all in its children, which is every app here. The same
    reasoning, and the same one-line implementation, as `tui_probe.buffer` —
    kept as a copy rather than imported because this file runs with the
    generated tree on `sys.path` and proto.pilot's own package deliberately not.
    """
    return "\n".join(strip.text for strip in app.screen._compositor.render_strips())


async def serve() -> None:
    from app.main import TerminalApp

    app = TerminalApp()
    frames = 0
    async with app.run_test(size=SIZE) as pilot:
        # Two pauses before the first frame, as the probe does: one to mount,
        # one to let anything scheduled by `on_mount` actually run.
        await pilot.pause()
        await pilot.pause()
        frames += 1
        send({"frame": buffer(app), "n": frames, "ready": True})

        loop = asyncio.get_running_loop()
        requests: asyncio.Queue = asyncio.Queue()

        def read_stdin() -> None:
            """A thread, because `sys.stdin` blocks and the app's event loop
            must keep running — an app with a timer has to go on animating
            between requests, and a loop parked on `readline` does not."""
            for line in sys.stdin:
                loop.call_soon_threadsafe(requests.put_nowait, line)
            loop.call_soon_threadsafe(requests.put_nowait, None)

        threading.Thread(target=read_stdin, daemon=True).start()

        while True:
            line = await requests.get()
            if line is None:
                break
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                # A malformed request is the caller's bug and not fatal to the
                # app; saying so beats dying and beats silence.
                send({"error": "unparseable request"})
                continue
            if request.get("quit"):
                break

            key = request.get("key")
            try:
                if key:
                    await pilot.press(key)
                await pilot.pause()
                frames += 1
                send({"frame": buffer(app), "n": frames})
            except Exception as exc:  # noqa: BLE001 -- reporting it IS the job
                # A key that raises is a real finding about the generated app,
                # not a reason to stop: the next key may well work, and a
                # preview that dies on one bad binding tells the reader less
                # than one that shows the error and keeps the screen.
                send({"error": f"{type(exc).__name__}: {exc}", "key": key})


def main() -> int:
    # For the app's lifetime. Anything it prints is diagnostics, and stderr is
    # the stream nothing else here uses.
    sys.stdout = sys.stderr
    try:
        asyncio.run(serve())
    except BaseException:  # noqa: BLE001 -- reporting the failure IS the job
        send({"error": "the app could not be started", "traceback": traceback.format_exc(), "fatal": True})
        return 0
    send({"closed": True})
    return 0


if __name__ == "__main__":
    os.environ.setdefault("TERM", "xterm-256color")
    raise SystemExit(main())
