"""Spec + models -> tests/test_smoke.py, driven through `App.run_test`.

Generated BEFORE the screens, exactly as on the web side and for the same
reason: tests written after the code describe whatever the code happened to do.
These describe what the spec promised, so a screen the model forgot is a red
test rather than a silent omission, and the screens pass is handed them as its
target.

This is the more expensive of the two passes Phase 1 measured -- roughly 6.4x
the web smoke pass in wall clock. It is also where all three terminal runs
failed, every time for the same reason: each wrote its own text reader and each
got it wrong. The reader is skeleton now (`tests/screen.py`) and the task block
names it.
"""

from __future__ import annotations

from protopilot import baseline_tui
from protopilot.passes.tui import _brief

NAME = "smoke"
WRITES = ("tests/test_smoke.py",)
SCHEMA = _brief.FILES_SCHEMA


def build(spec, ctx) -> tuple[str, str]:
    user = _brief.spec_block(spec) + "\n\n## Already generated\n\n" + _brief.sources(ctx, "app/models.py")
    return _brief.system(_brief.SMOKE_TASK), user


def offline(spec, ctx) -> dict:
    from protopilot import archetypes

    override = archetypes.generator(spec, "tui_smoke_py")
    content = override(spec) if override else baseline_tui.smoke_py(spec)
    return {
        "files": [{"path": "tests/test_smoke.py", "content": content}],
        "notes": "baseline: boot, seed, list, record and a create round trip per entity, driven by the pilot.",
    }
