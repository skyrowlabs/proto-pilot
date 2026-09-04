"""The terminal target: Textual, SQLAlchemy, one SQLite file, one process.

The second medium, and the one `docs/TODO/terminal-target.md` exists to build.
Everything the web target needs a container for -- a port, a health wait, a
compose project, a volume to orphan -- has no counterpart here: the whole
application is `python -m app.main` and the database is a file beside it.

## What it can build, and what that claim costs

`ARCHETYPES` is the narrow claim: an archetype is listed here when this target
has **both** a prompt fragment for it (`passes/tui/_brief.py::ARCHETYPE_BRIEFS`)
and an offline baseline that produces a working app of that shape. Those are
two different facts and they are deliberately in two places -- a fragment makes
a shape *sayable* to the model, a baseline makes it *testable without a key*,
and a target that claimed the first while missing the second would be green in
CI and broken on the day somebody ran it offline.

This is the concrete shape of the cost `docs/TODO/terminal-target.md` Phase 2
calls "the one that will hurt": the two axes multiply, and the multiplication
is paid here and in the archetype's terminal generators.

## The archetype brief is a fifth thing a target owns

The plan's Phase 2 table lists four -- skeleton directory, pass tuple, write
allowlist, verifier. Building this one found a fifth. `archetypes.brief_for()`
cannot be reused: both shipped fragments are written in web, down to "in the
same browser" and "draw the pieces as inline SVG", and handing either to a
Textual pass tells the model the app it is building is a web page. So the
fragments are rewritten per medium and they live with the passes that use them.
"""

from __future__ import annotations

from pathlib import Path

from protopilot.passes.tui import repair as repair_pass
from protopilot.passes.tui import schema as schema_pass
from protopilot.passes.tui import screens as screens_pass
from protopilot.passes.tui import seed as seed_pass
from protopilot.passes.tui import smoke as smoke_pass
from protopilot.passes.tui import ui as ui_pass
from protopilot.runner import SubprocessRunner
from protopilot.spec import Spec
from protopilot.targets import SKELETON_ROOT
from protopilot.verify import Verifies
from protopilot.verify_tui import TuiVerifier

NAME = "tui"
LABEL = "A terminal app you run in a shell"

#: The fixed tree, copied byte-for-byte into every generated prototype.
#:
#: Nineteen files against the web tree's twenty-four, and most of the
#: difference is Docker. There is no `compose.yml`, no `Dockerfile`, no
#: `.env.example` and no port anywhere in it.
SKELETON_DIR = SKELETON_ROOT / "tui"

#: The pass order. Five, and that is measured rather than assumed.
#:
#: `docs/TODO/terminal-target.md` Phase 4 asks whether a Textual app splits the
#: same way a FastAPI one does -- "a Textual app is often one file with a
#: `compose()` method, so the split may not be five". The Phase 1 go/no-go ran
#: all five live against three specs and every one of them did work. The
#: expensive two are `smoke` (~6.4x its web twin) and `screens` (~4.3x), with
#: `schema`, `seed` and `ui` at parity; if the split is ever revisited, that is
#: where the money is.
#:
#: The two invariants are the same ones the web target holds and they are the
#: reason this order is not negotiable: smoke is generated BEFORE the screens
#: it tests, from the spec; and each pass is handed the previous pass's real
#: source. `ui` goes last and receives `app/screens.py`, because a stylesheet
#: selecting an id no screen defines is silently dead.
CODE_PASSES = (schema_pass, smoke_pass, seed_pass, screens_pass, ui_pass)

#: The pass the repair loop runs. Not in `CODE_PASSES`: it runs on failure
#: rather than in sequence, and it may rewrite anything in `WRITABLE`.
#:
#: It is the target's rather than `build.py`'s because the prompt differs --
#: the web repair pass is handed container logs and there are none here. What
#: this one gets instead is the boot probe's report, which for a blank screen
#: includes the rendered buffer beside an empty one.
REPAIR = repair_pass

#: Only these paths are generated. Everything else is skeleton, and
#: `files.check_path` refuses it before it reaches disk.
#:
#: Six rather than the web target's five, and the extra one is the stylesheet:
#: on the web side `app/static/app.css` is skeleton and the ui pass may not
#: touch it, because a theme's colour arrives as `fill` on drawn SVG. There is
#: no SVG in a terminal, so colour is `app/app.tcss` or it is nothing.
WRITABLE = (
    "app/models.py",
    "app/screens.py",
    "app/seed.py",
    "app/widgets.py",
    "app/app.tcss",
    "tests/test_smoke.py",
)

#: Under a writable glob but skeleton. Empty, and named rather than omitted, so
#: the shape matches the web target's and a later addition is a value in a
#: tuple. `WRITABLE` here is six literal paths with no glob in it, which is why
#: there is nothing for this to exclude.
PROTECTED: tuple[str, ...] = ()

#: Every archetype this target can build -- see the module docstring for what
#: that claim requires.
#:
#: Both of them since Phase 6, and completing the matrix was not optional once
#: this became `targets.DEFAULT`: a hole in the DEFAULT target is `proto new`
#: refusing its own classifier's answer, which is a worse failure than any
#: stated hole elsewhere. `tests/test_targets.py` holds exactly that line.
#:
#: What it cost is the concrete form of "the one that will hurt":
#: `archetypes/turn_based_game.py` grew `tui_screens_py`, `tui_smoke_py` and
#: `tui_tcss` beside its web three. Its `models_py` and `seed_py` are reused
#: unchanged, because both are pure SQLAlchemy -- so the multiplication is
#: three files per pair rather than five.
ARCHETYPES = ("crud", "turn-based-game")


#: Whether `spec.port` means anything for this target. It does not.
#:
#: A terminal app listens on nothing. The field is still on `Spec` -- it is
#: identity for the web target and it is carried through an amend -- but the
#: review checkpoint must not print it, because a person approving a
#: generation and reading "port 8082" has been told something false about the
#: thing they are approving.
USES_PORT = False

#: The line printed when a generation comes back green.
#:
#: Not a URL. The most common way a tool lies is by reusing the sentence that
#: was true of the only medium it used to have.
HANDOFF = "{name} is ready:  cd {directory} && make run"

#: What a person types to start this prototype. One process, no port.
RUN_HINT = "cd {directory} && make run"

#: What the RUNBOOK's captured second stream actually is. Not "container logs":
#: there is no container, and the stream is whatever the app itself printed to
#: stderr while the probe was driving it.
LOGS_LABEL = "What the app printed"

#: The RUNBOOK's "carrying on by hand" block.
MANUAL = """\
```bash
pip install -r requirements.txt   # into a virtualenv you have activated
python -m app.main                # the app, in this terminal
python -m pytest -q               # the failing suite
```"""


def preflight(runner) -> tuple[bool, str]:
    """Nothing has to be true. That is the point of this target.

    No daemon, no port, no image to pull. It exists as a function rather than
    a `NEEDS_DOCKER = False` flag so the CLI asks one question of the target
    instead of branching on a property of it -- a third target that needs
    something else entirely answers here and changes nothing upstream.
    """
    return True, "a terminal app needs nothing but Python"


def verifier(project_dir: Path, spec: Spec, runner=None) -> Verifies:
    """Import, boot under `App.run_test`, run the smoke suite, check it painted.

    The same two arguments and the same Protocol the web target's factory
    returns, so `drive_to_green` never learns which one it got -- and the same
    place the constructor arguments are decided once, for both front ends.

    `spec` is unused, deliberately. The web verifier needs `spec.port` and
    `checkable_paths(spec)`; a terminal app has neither a port nor a URL, and
    the argument stays in the signature because the signature is the contract
    `targets.for_spec(spec).verifier(...)` calls through.

    `SubprocessRunner` is resolved from this module's namespace rather than
    frozen into a default, so a test can substitute it -- see the note in
    `verify_tui.py` about the seam the web factory does not have.
    """
    return TuiVerifier(project_dir, runner=runner or SubprocessRunner())
