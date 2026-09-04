"""Spec + models + screens -> app/app.tcss and app/widgets.py.

Last, and given the real screen source, because a Textual selector for an id no
screen defines is silently dead -- the terminal analogue of the template
referencing a context key no route passes.

The one place this target's ui pass has more authority than the web target's:
it writes the stylesheet. On the web side `app/static/app.css` is skeleton and
the pass may not touch it, so a theme's palette arrives as `fill` and `stroke`
attributes on drawn SVG. There is no SVG here, so colour is the stylesheet or
it is nothing.
"""

from __future__ import annotations

from protopilot import baseline_tui
from protopilot.passes.tui import _brief

NAME = "ui"
WRITES = ("app/app.tcss", "app/widgets.py")
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    user = (
        _brief.spec_block(spec)
        + "\n\n## Already generated\n\n"
        + _brief.sources(ctx, "app/models.py", "app/screens.py")
    )
    if spec.direction:
        user += f"\n\nThe user's direction for how this should look and feel: {spec.direction}"
    return _brief.system(_brief.UI_TASK), user + _brief.theme_block(spec)


def offline(spec, ctx) -> dict:
    from protopilot import archetypes

    override = archetypes.generator(spec, "tui_tcss")
    content = override(spec) if override else baseline_tui.tcss(spec)
    return {
        "files": [{"path": "app/app.tcss", "content": content}],
        "notes": "baseline: a layout that fills the terminal, and a styled empty state.",
    }
