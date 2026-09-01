"""Spec + models + routes -> the Jinja templates.

Last, and given the real route source, because the single most common failure
in a generated app is a template referencing a context key no route passes.
"""

from __future__ import annotations

from protopilot import baseline
from protopilot.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "ui"
WRITES = ("app/templates/*.html",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write the Jinja templates. You may write any file under `app/templates/`
EXCEPT `base.html`, which is fixed.

Generate exactly the templates `app/routes.py` renders -- read its
`TemplateResponse` calls and produce one file per distinct name. Also write
`_nav.html`, which `base.html` includes: a `<nav>` with one link per entity
list screen.

Every template starts `{% extends "base.html" %}` and fills the `title` and
`content` blocks. `app_name` and `app_purpose` are already globals; do not
expect a route to pass them.

Use ONLY context keys the corresponding route actually passes. This is the
single most common way a generated app 500s at render time -- read the route,
then write the template.

Shape:

- list: a heading, a "New <Entity>" button, a `<table>` with one column per
  spec field, and a link to the detail screen per row. When the list is empty,
  a `<p class="empty">` with a link to the create form -- not a blank page.
- detail: `row.display` as the heading, a `<dl>` of the fields, a link back to
  the parent if there is one, a list of children if there are any, and Edit /
  Delete controls. Delete is a `<form method="post">` with a button, never a
  link -- a crawler or a prefetch must not be able to delete a row.
- form: one `<label>` per field wrapping its input, with the input type
  matching the field type (`text`, `textarea`, `number`, `checkbox`, `date`,
  `datetime-local`). Prefill from `obj` when it is set and leave blank when it
  is `None`. Render `date`/`datetime` values through `.isoformat()`;
  `<input type="datetime-local">` rejects Python's default rendering. An
  entity with a parent gets a `<select>` of candidate parents.
- index: the app name, its purpose, and a `.card` per entity linking to its
  list with a count.

Use the stylesheet's existing classes for chrome and layout. Do not write
CSS and do not add `<style>`.

## Drawing

That rule is about not inventing a second design system. It is not a rule
against pictures. When the thing on the screen genuinely IS a picture -- a
game board and its pieces, a chart, a floor plan, a seating chart, a badge,
a diagram -- draw it with inline `<svg>`.

Inline SVG is markup, not JavaScript: it needs no library, no CDN and no
build step, and it is the difference between a prototype that looks like the
idea and a table of emoji standing in for one. Reach for it whenever the
alternative is a glyph pretending to be an illustration.

- Give every `<svg>` a `viewBox` so it scales, and a `<title>` so it is not
  invisible to a screen reader.
- Colour with presentation attributes (`fill`, `stroke`), not CSS. Use
  `currentColor` where the shape should follow the surrounding text, so it
  works in light and dark without you writing a palette.
- Build shapes from a handful of paths, circles and polygons. Aim for clean
  and iconic, the way a good pictogram reads at a glance -- not photorealism,
  and not a thousand-point path.
- Draw it once as a Jinja macro or an `{% include %}` and reuse it, rather
  than pasting the same shape into eight cells.
- Everything stays inline. No external images, no sprite sheets, no fonts.

For a raster image that has to be computed rather than drawn -- a filtered
photo, a generated texture -- the routes pass renders it with Pillow and
serves it from a route; the template just points an `<img>` at that route.

Emoji are still fine as small accents and labels. They are not fine as the
artwork when the screen is asking to be looked at.

## JavaScript, and when a canvas is worth it

Inline `<script>` is allowed. There is still no npm, no CDN and no build step,
and the container has no outbound network, so it is vanilla JavaScript written
into the template and nothing else.

The rule that matters: **the page must work with JavaScript switched off.**
Every action is still a form submit or a link, and the server still renders
the truth. Script may sharpen a working page -- highlight the squares a picked
piece can reach, preview a colour before submitting, sort a table in place --
but nothing may exist only in the browser. State lives in Postgres, reached
by forms, exactly as before.

`<canvas>` is the exception where a drawing genuinely has to be computed per
frame or per pixel rather than described as shapes -- a plotted curve over
thousands of points, a generated texture. Prefer SVG whenever the picture can
be expressed as shapes, because SVG needs no script, scales, and survives with
JavaScript off. If you do use a canvas, draw on it during page load, never
leave it blank waiting for an interaction, and render the same information as
text or SVG underneath it so the page still says something without script.

Anything you write is loaded in a real browser during verification, and an
uncaught error or a canvas that was never drawn on fails the run. Script that
cannot be seen to work is worse than no script.
"""


def build(spec, ctx) -> tuple[str, str]:
    user = spec_block(spec) + "\n\n## Already generated\n\n" + ctx.sources("app/models.py", "app/routes.py")
    if spec.direction:
        user += f"\n\nThe user's direction for how this should look and feel: {spec.direction}"
    return STACK_BRIEF + TASK, user


def offline(spec, ctx) -> dict:
    files = [{"path": path, "content": body} for path, body in sorted(baseline.templates_for(spec).items())]
    return {
        "files": files,
        "notes": "baseline: nav, index, and list/detail/form per entity.",
    }
