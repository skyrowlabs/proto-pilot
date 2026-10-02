"""Idea -> spec.

The only pass whose output is not files. It is also the only human checkpoint
in the whole tool, which is why the spec is small: a spec you cannot read in
thirty seconds is one nobody reads, and an unreviewed spec is just the model's
first guess wearing a schema.
"""

from __future__ import annotations

import re

from protopilot.spec import intake_schema

NAME = "intake"
WRITES: tuple[str, ...] = ()
SCHEMA = intake_schema()

SYSTEM = """\
You turn a one-line product idea into a small, concrete application spec.

You are specifying a PROTOTYPE: something to look at and click through in an
afternoon, not a product. Bias hard toward less.

Rules:

- 1 to 4 entities. If the idea suggests more, pick the ones without which the
  app makes no sense and drop the rest. Two is usually right.
- 2 to 6 fields per entity. No `created_at`/`updated_at` unless the idea is
  actually about time. No status enums with six states; a boolean will do.
- Field types are limited to: str, text, int, float, bool, date, datetime.
  `str` is a single line; `text` is a paragraph.
- At most one `belongs_to` relationship per entity, naming a parent entity in
  the same spec. No many-to-many.
- `auth` is "none" unless the idea is explicitly about accounts or privacy.
- `jobs` and `external_apis` are almost always empty. Only fill them if the
  idea is meaningless without them, and name them, do not describe them.
- `slug` is snake_case and is also the database name.
- Leave `port` at 8080 and `protopilot_version` at "0.1.0"; the tool overwrites
  both.
- `direction` echoes back any styling or behavioural steer the user gave, in
  their words. Empty string if they gave none.

Screens: leave `screens` empty unless the idea needs a page that is not a
list, a form or a single record. The standard pages are generated from the
shape of the app, not by you, and anything here that is not `custom` is
discarded.

You may propose at most two `custom` screens -- a calendar, a seating chart,
a dashboard. Name it and give it a path. Most ideas need none: the shape you
are given already provides the page you are most likely reaching for.

Use the entity's snake_case plural. Prefer the user's own vocabulary for
`name` and for field names: if they say "gig", the entity is Gig, not Event.

## What the runtime can and cannot do

Every app is server-rendered HTML: FastAPI, Jinja templates, plain forms and
full page loads. There is NO npm, NO CDN, NO WebGL, and no realtime connection
of any kind. Nothing may exist only in the browser.

Buildable, and often better than it sounds: a page that re-renders after
every submit, any control expressible as a form button, and real artwork
drawn as inline SVG -- vector shapes, hand-drawn by the UI pass, not emoji
standing in for illustrations.

So do NOT write a limit saying the artwork will be emoji. It will be drawn.
Photographs and 3D models are still out; drawing is not.

Buildable with care: small touches of inline vanilla JavaScript, and a
`<canvas>` where a picture genuinely has to be computed pixel by pixel. Both
only ever enhance a page that already works without them.

Not buildable, at all: anything that needs a JavaScript library or a package
from npm, live multiplayer between two devices, sound, video, a camera feed,
or 3D and isometric rendering.

When the idea asks for something in that second list, do NOT quietly specify
something smaller and say nothing about it. Specify the closest honest thing
that works as server-rendered HTML -- and write what you had to drop into
`limits`, one plain sentence each, in the user's own words. "3D board is flat
in this version" is a good limit; "unsupported rendering pipeline" is not.
Leave `limits` empty only when the idea genuinely fits as asked.
"""


def archetype_brief(name: str) -> str:
    """The classified shape's own fragment, for the user message.

    Intake is the one pass with no spec to read the archetype off, so the
    classifier's answer is handed to it through `ctx`. This is where the
    board-game prose that used to live in `SYSTEM` went: it was paid for on
    every generation, game or gear list, and it is `turn-based-game`'s to say.

    Failing soft is deliberate. A name this build does not have must produce a
    slightly less informed spec, never a traceback before the first pass.
    """
    if not name:
        return ""
    from protopilot import archetypes

    try:
        module = archetypes.get(name)
    except archetypes.MissingArchetype:
        return ""
    fragment = getattr(module, "brief", None)
    return fragment() if callable(fragment) else ""


def build(spec_or_idea, ctx) -> tuple[str, str]:
    """`spec_or_idea` is the raw idea string for this pass."""
    idea = spec_or_idea if isinstance(spec_or_idea, str) else spec_or_idea.purpose
    user = f"Idea: {idea}\n"
    if ctx.change:
        user += f"\nExtra direction from the user: {ctx.change}\n"
    brief = archetype_brief(getattr(ctx, "archetype", ""))
    if brief:
        user += (
            "\n## What kind of thing this is\n\n"
            + brief
            + "\n\nSpecify the entities that shape actually needs. It is already decided;\n"
            "do not argue with it and do not specify a different app.\n"
        )
    return SYSTEM, user


def offline(idea: str, ctx) -> dict:
    """The baseline cannot read English. It produces a single-entity app named
    after the idea, which is enough to exercise the pipeline end to end."""
    words = [w for w in re.findall(r"[A-Za-z]+", idea)][:3] or ["Thing"]
    name = " ".join(w.capitalize() for w in words)
    slug = "_".join(w.lower() for w in words)
    entity = words[0].capitalize()
    data = {
        "name": name,
        "slug": slug,
        "purpose": idea.strip() or "A prototype.",
        "entities": [
            {
                "name": entity,
                "plural": "",
                "belongs_to": None,
                "fields": [
                    {"name": "title", "type": "str", "required": True, "label": ""},
                    {"name": "notes", "type": "text", "required": False, "label": ""},
                    {"name": "done", "type": "bool", "required": False, "label": ""},
                ],
            }
        ],
        "screens": [],
        "auth": "none",
        "jobs": [],
        "external_apis": [],
        "port": 8080,
        "protopilot_version": "0.1.0",
        "direction": ctx.change,
    }
    # Screens are the archetype's, and this function does not know which one
    # it is. The caller fills them in through `archetypes.screens_for`.
    return data


AMEND_SYSTEM = SYSTEM + """

## Amending an existing spec

You are given a spec that already exists and a change the user asked for.
Return the COMPLETE updated spec.

- Change only what the request requires. Keep every existing entity name,
  field name, slug and screen path that the change does not touch -- they are
  already in generated code, in seed data and in the user's head, and a
  gratuitous rename is a rewrite of the whole app.
- Keep `slug` and `port` exactly as they are.
- Regenerate the `screens` list from the same rule as before, so it stays
  consistent with the entities after your change.
"""


def build_amend(spec, change: str) -> tuple[str, str]:
    import json

    from protopilot.passes._shared import visible_spec

    # Hidden here too, and for a sharper reason than in the code passes: the
    # amend schema is the intake schema, so `theme` is not a field the model is
    # allowed to return. Showing it could only invite an opinion with nowhere
    # to go.
    user = (
        "## Current spec\n\n```json\n"
        + json.dumps(visible_spec(spec).model_dump(mode="json"), indent=2)
        + "\n```\n\n## The change the user asked for\n\n"
        + change.strip()
        + "\n"
    )
    return AMEND_SYSTEM, user
