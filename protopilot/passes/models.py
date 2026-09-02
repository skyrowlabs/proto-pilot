"""Spec -> app/models.py. The first code pass; everything downstream reads it."""

from __future__ import annotations

from protopilot import baseline
from protopilot.passes._shared import FILES_SCHEMA, STACK_BRIEF, spec_block

NAME = "schema"
WRITES = ("app/models.py",)
SCHEMA = FILES_SCHEMA

TASK = """\
## Your task

Write `app/models.py` -- and only that file.

- One `Base` subclass per entity, SQLAlchemy 2.0 declarative style with
  `Mapped[...]` annotations and `mapped_column(...)`.
- `id: Mapped[int] = mapped_column(primary_key=True)` on every model.
- A `belongs_to` becomes a nullable `ForeignKey` column named
  `<parent_snake>_id` plus a `relationship()` on both sides with
  `back_populates`. The parent side carries
  `cascade="all, delete-orphan"` -- deleting a parent must not leave orphans
  that every later query has to filter out.
- A field with `required: false` is `Mapped[Optional[T]]` and
  `nullable=True`; a required one is `Mapped[T]` and `nullable=False`.
- Every model gets a `display` property returning a short human label,
  falling back to `f"<Entity> {self.id}"`, and `__str__` returning it.
- `from __future__ import annotations` at the top, and `Optional` imported
  from `typing` -- SQLAlchemy resolves these annotations at class creation.
"""


def build(spec, ctx) -> tuple[str, str]:
    return STACK_BRIEF + TASK, spec_block(spec)


def _generate(spec) -> str:
    """This archetype's generator, or the baseline's.

    An archetype whose pages are not CRUD has to be able to replace this; one
    whose pages are CRUD must not have to. See `archetypes.generator`.
    """
    from protopilot import archetypes

    override = archetypes.generator(spec, "models_py")
    return override(spec) if override else baseline.models_py(spec)


def offline(spec, ctx) -> dict:
    return {
        "files": [{"path": "app/models.py", "content": _generate(spec)}],
        "notes": "baseline: one class per entity, FK plus back_populates for belongs_to.",
    }
