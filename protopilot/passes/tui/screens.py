"""Spec + models + smoke tests -> app/screens.py.

The terminal counterpart of `passes/routes.py`, and the second of the two
passes Phase 1 measured as expensive -- roughly 4.3x its web twin. Like that
pass it is handed the generated smoke suite as its target: it is not asked to
guess a navigation scheme, it is asked to satisfy assertions that already
exist.

`HomeScreen` is the one name that is not negotiable. `app/main.py` returns it
from `get_default_screen()`, so a `screens.py` that does not define a class
with exactly that name is an app that will not start.
"""

from __future__ import annotations

from protopilot import baseline_tui
from protopilot.passes.tui import _brief

NAME = "screens"
WRITES = ("app/screens.py",)
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    user = (
        _brief.spec_block(spec)
        + "\n\n## Already generated\n\n"
        + _brief.sources(ctx, "app/models.py", "tests/test_smoke.py")
    )
    return _brief.system(_brief.SCREENS_TASK), user


def offline(spec, ctx) -> dict:
    from protopilot import archetypes

    override = archetypes.generator(spec, "tui_screens_py")
    content = override(spec) if override else baseline_tui.screens_py(spec)
    return {
        "files": [{"path": "app/screens.py", "content": content}],
        "notes": "baseline: a home screen, plus a list, a form and a record screen per entity.",
    }
