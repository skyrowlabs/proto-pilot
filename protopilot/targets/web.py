"""The web target: FastAPI, Jinja, SQLAlchemy, Postgres, Docker Compose.

The medium proto.pilot was born speaking, extracted into a module so a second
one can exist beside it. Nothing here is new behaviour — every constant below
was already in the tree, in `render.py`, `build.py` and `files.py`, and this is
a move rather than a copy. If the extraction is faithful, `tests/golden/`'s two
manifests are unchanged; if it is not, that is where it shows.

It is also the control. `docs/TODO/terminal-target.md` keeps this target
reachable, green and generated in CI even after the default moves, because
"is this the target or the change?" is a question only a second working target
can answer.
"""

from __future__ import annotations

from pathlib import Path

from protopilot.passes import models as schema_pass
from protopilot.passes import routes, seed, smoke, ui
from protopilot.runner import SubprocessRunner
from protopilot.spec import Spec, checkable_paths
from protopilot.targets import SKELETON_ROOT
from protopilot.verify import Verifier, Verifies

NAME = "web"
LABEL = "A web app you open in a browser"

#: The fixed tree, copied byte-for-byte into every generated prototype.
#:
#: `skeleton/web/` since 2026-09-04, when `skeleton/` grew a directory per
#: target. The move was mechanical and is held byte-identical by
#: `tests/test_skeleton_move_characterisation.py`, whose manifest was captured
#: from the tree before a file was touched.
SKELETON_DIR = SKELETON_ROOT / "web"

#: The pass order, which is the design rather than an accident:
#: tests come second, before any of the code they test, so they describe what
#: was asked for rather than what got built; UI comes last because it is the
#: pass most dependent on real source. Reordering this breaks the invariant.
CODE_PASSES = (schema_pass, smoke, seed, routes, ui)

#: Only these paths are generated. Everything else in a project is skeleton,
#: and `files.check_path` refuses it before it reaches disk.
WRITABLE = (
    "app/models.py",
    "app/routes.py",
    "app/seed.py",
    "app/templates/*.html",
    "tests/test_smoke.py",
)

#: ...except these, which live under a writable glob but are skeleton.
PROTECTED = ("app/templates/base.html",)

#: Every archetype this target can build. Both of them, today — the web medium
#: is the one all the shipped archetype briefs were written against.
#:
#: Declared rather than inferred, because the honest failure for an archetype
#: nobody wired up here is `UnsupportedPair` naming both halves. A test asserts
#: every name here is an installed archetype, so a stale entry cannot sit here
#: unnoticed; the reverse direction is deliberately not enforced for every
#: target, since a target that cannot build a shape is the point of the axis.
ARCHETYPES = ("crud", "turn-based-game")


def verifier(project_dir: Path, spec: Spec, runner=None) -> Verifies:
    """Boot the stack, wait on `/healthz`, run the smoke suite, capture logs.

    Both front ends build their verifier through here rather than reaching for
    `Verifier` directly, so the four constructor arguments are decided once. A
    second target's `verifier()` takes the same two arguments and returns the
    same Protocol; that is the whole of what `drive_to_green` needs.
    """
    return Verifier(project_dir, spec.port, runner or SubprocessRunner(), screens=checkable_paths(spec))
