"""Spec + models -> app/seed.py.

Seed data is not a nicety. A prototype opened on an empty table looks broken,
and the person you are showing it to cannot tell the difference between "no
data yet" and "the query is wrong".
"""

from __future__ import annotations

from protopilot import baseline
from protopilot.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "seed"
WRITES = ("app/seed.py",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write `app/seed.py` -- and only that file. It exports
`def seed(db: Session) -> None`.

- Roughly 5 rows per top-level entity and 2-3 children per parent. Enough to
  fill a table; few enough to read.
- Make the data PLAUSIBLE for this specific app. Real-sounding names, dates
  spread across the next few weeks, a mix of true and false booleans, numbers
  in a believable range. "Item 1 / Item 2 / Item 3" tells a viewer nothing
  about what the app is for.
- Idempotent, and the guard comes first: return immediately if the first
  entity already has any row. `seed()` runs on every startup, and hot reload
  means that is often -- an unguarded seed is a duplicate-row factory.
- Insert parents, `db.flush()` to get their ids, then children referencing
  `parent.id`. One `db.commit()` at the end, so a failure part-way rolls the
  whole seed back rather than leaving half a fixture.
- No randomness. A regenerated seed should be a no-op diff.
"""


def build(spec, ctx) -> tuple[str, str]:
    user = spec_block(spec) + "\n\n## Already generated\n\n" + ctx.sources("app/models.py")
    if spec.direction:
        user += f"\n\nThe user's direction, which the sample data should reflect: {spec.direction}"
    return STACK_BRIEF + TASK, user


def _generate(spec) -> str:
    """This archetype's generator, or the baseline's.

    An archetype whose pages are not CRUD has to be able to replace this; one
    whose pages are CRUD must not have to. See `archetypes.generator`.
    """
    from protopilot import archetypes

    override = archetypes.generator(spec, "seed_py")
    return override(spec) if override else baseline.seed_py(spec)


def offline(spec, ctx) -> dict:
    return {
        "files": [{"path": "app/seed.py", "content": _generate(spec)}],
        "notes": "baseline: five rows per parent, two per child, guarded and deterministic.",
    }
