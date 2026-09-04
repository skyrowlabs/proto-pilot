"""Spec + models -> app/seed.py, for the terminal target.

Same job, same file, same baseline as the web target -- `seed()` takes a
`Session` and knows nothing about the medium. The one thing the task block says
that its web twin does not is *keep the strings short*: a terminal column is a
few dozen cells wide, and a forty-character name is a truncated one.
"""

from __future__ import annotations

from protopilot import baseline
from protopilot.passes.tui import _brief

NAME = "seed"
WRITES = ("app/seed.py",)
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    user = _brief.spec_block(spec) + "\n\n## Already generated\n\n" + _brief.sources(ctx, "app/models.py")
    if spec.direction:
        user += f"\n\nThe user's direction, which the sample data should reflect: {spec.direction}"
    return _brief.system(_brief.SEED_TASK), user


def offline(spec, ctx) -> dict:
    from protopilot import archetypes

    override = archetypes.generator(spec, "seed_py")
    content = override(spec) if override else baseline.seed_py(spec)
    return {
        "files": [{"path": "app/seed.py", "content": content}],
        "notes": "baseline: five rows per parent, two per child, guarded and deterministic.",
    }
