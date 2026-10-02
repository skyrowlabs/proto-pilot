"""The web target: FastAPI, Jinja, SQLAlchemy, Postgres, Docker Compose.

The medium proto.pilot was born speaking, extracted into a module so a second
one can exist beside it. Nothing here is new behaviour — every constant below
was already in the tree, in `render.py`, `build.py` and `files.py`, and this is
a move rather than a copy. If the extraction is faithful, `tests/golden/`'s two
manifests are unchanged; if it is not, that is where it shows.

It is also the control. `docs/implementations/spec/terminal-target.md` keeps this target
reachable, green and generated in CI even after the default moves, because
"is this the target or the change?" is a question only a second working target
can answer.
"""

from __future__ import annotations

from pathlib import Path

from protopilot.passes import models as schema_pass
from protopilot.passes import repair as repair_pass
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

#: The pass the repair loop runs. Not in `CODE_PASSES`: it runs on failure
#: rather than in sequence, and it may rewrite anything in `WRITABLE`.
#:
#: It moved here from a module-level import in `build.py` when the second
#: target arrived, and for the reason the other four moved: the prompt is the
#: medium's. This one names container logs, template context keys and a 307
#: redirect, none of which exist in a terminal.
REPAIR = repair_pass

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


#: Whether `spec.port` means anything for this target.
#:
#: It does here: the port is the tab the user has open, it is frozen into
#: `compose.yml`, and `free_port()` avoids collisions with it. The review
#: checkpoint prints it because a person approving a generation wants to know
#: where the thing will be.
USES_PORT = True

#: The line printed when a generation comes back green.
#:
#: A format string over `name`, `slug`, `port` and `directory`. It is the
#: target's because it is the one sentence that says what the user now HAS,
#: and "http://localhost:8080" is only true of a medium that listens.
HANDOFF = "{name} is up:  http://localhost:{port}"

#: What a person types to start this prototype, once they have the tree.
#:
#: Printed by `proto new --no-verify` and used nowhere else. It belongs to the
#: target because it is a fact about the medium: `make up` is a compose project
#: and there is no such thing in a one-process tree.
RUN_HINT = "cd {directory} && make up"

#: What the RUNBOOK's captured second stream actually is.
LOGS_LABEL = "Container logs"

#: The RUNBOOK's "carrying on by hand" block.
MANUAL = """\
```bash
docker compose up -d --build           # bring it up
docker compose logs -f app             # watch it
docker compose exec -T app pytest -q   # the failing suite
```"""


def preflight(runner) -> tuple[bool, str]:
    """What has to be true before generating for this target.

    Asked before the classifier and before intake, so a machine with no daemon
    is told now rather than after the tokens are spent. It is the target's
    question and not the CLI's: `docker_available` is the right check for a
    tree with a `compose.yml` in it and is meaningless for one process and a
    SQLite file.
    """
    from protopilot.runner import docker_available

    return docker_available(runner)


def verifier(project_dir: Path, spec: Spec, runner=None) -> Verifies:
    """Boot the stack, wait on `/healthz`, run the smoke suite, capture logs.

    Both front ends build their verifier through here rather than reaching for
    `Verifier` directly, so the four constructor arguments are decided once. A
    second target's `verifier()` takes the same two arguments and returns the
    same Protocol; that is the whole of what `drive_to_green` needs.
    """
    return Verifier(project_dir, spec.port, runner or SubprocessRunner(), screens=checkable_paths(spec))


def reset_state(project_dir: Path, runner=None) -> str:
    """Drop this tree's saved data. Returns what it did, for the log.

    Called before an amend, and the reason is the same one `proto add` has
    carried since it existed: a change request can add or retype a column, and
    there are no migrations, so the old data is dropped rather than silently
    kept and left disagreeing with the models it is about to be read through.

    **This is the target's answer and not the amend's.** Both amend paths used
    to run `docker compose down -v` unconditionally, which is correct here and
    meaningless for a tree with no compose file — it is the seventh thing that
    was hardcoded somewhere and turned out to be true only of Docker. The
    volume is what holds the data here; somewhere else it is a file.
    """
    from protopilot.runner import SubprocessRunner

    (runner or SubprocessRunner()).run(["docker", "compose", "down", "-v"], cwd=project_dir, timeout=120.0)
    return "dropped the database volume"
