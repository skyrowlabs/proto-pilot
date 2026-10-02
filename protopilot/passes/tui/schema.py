"""Spec -> app/models.py, for the terminal target.

Identical in job to `passes/models.py`, and the file it writes is identical in
content: SQLAlchemy models import from `app.db` and know nothing about whether
a screen or a route is going to read them. The whole of the difference is the
brief wrapped around the task -- which is why this module's `offline` reaches
for the same baseline generator the web target does rather than a copy of it.
"""

from __future__ import annotations

from protopilot import baseline
from protopilot.passes.tui import _brief

NAME = "schema"
WRITES = ("app/models.py",)
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    return _brief.system(_brief.SCHEMA_TASK), _brief.spec_block(spec)


def offline(spec, ctx) -> dict:
    """The web target's generator, deliberately.

    A second copy of `baseline.models_py` would be a second answer to "what
    does a model class look like", and the two would drift the first time
    either target grew a field type. The archetype's override is asked for
    under the same name for the same reason: `turn_based_game.models_py` is
    pure SQLAlchemy and is correct in both media.
    """
    from protopilot import archetypes

    override = archetypes.generator(spec, "models_py")
    content = override(spec) if override else baseline.models_py(spec)
    return {
        "files": [{"path": "app/models.py", "content": content}],
        "notes": "baseline: one class per entity, FK plus back_populates for belongs_to.",
    }
