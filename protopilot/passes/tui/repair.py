"""A failing verify run -> patched files, for the terminal target.

The web repair pass is handed container logs; there are none here. What it gets
instead is the probe's own report -- the stage that failed, the traceback, and
for a blank screen the rendered buffer beside the buffer of an application with
nothing in it. That comparison is the terminal analogue of the browser stage
and it is strictly more legible than a log tail: the model is shown the screen.
"""

from __future__ import annotations

from protopilot.passes.tui import _brief

NAME = "repair"

#: Empty, and it is the one pass for which that does not mean "writes nothing".
#:
#: Repair may rewrite any path the running target allows, and that list belongs
#: to `targets/tui.py`. `run_pass` enforces the real set from `spec.target`;
#: nothing reads this constant. Kept for the shape every pass module has, so
#: `WRITES` is never the attribute a reader has to know is missing here.
WRITES: tuple[str, ...] = ()
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    from protopilot import targets

    sources = _brief.sources(ctx, *targets.get("tui").WRITABLE)
    user = (
        "## What went wrong\n\n```\n"
        + ctx.failure.strip()
        + "\n```\n\n"
        + _brief.spec_block(spec)
        + "\n\n## Current source of every generated file\n\n"
        + sources
    )
    return _brief.system(_brief.REPAIR_TASK), user


def offline(spec, ctx) -> dict:
    # The baseline generator has no diagnostic faculty. Saying so lets the
    # loop stop cleanly and write a runbook rather than spin.
    return {
        "files": [],
        "notes": "offline mode cannot repair; re-run without --offline to fix this.",
    }
