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
from protopilot.spec import Spec
from protopilot.targets import SKELETON_ROOT
from protopilot.verify import Verifies

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
#: that claim requires. `crud` only, for now: `turn-based-game` has a terminal
#: prompt fragment and no terminal offline baseline, so the honest failure for
#: that pair is `UnsupportedPair` naming both halves rather than a generated
#: tracking app where somebody asked for a board.
ARCHETYPES = ("crud",)


def verifier(project_dir: Path, spec: Spec, runner=None) -> Verifies:
    """Not yet. Phase 5 of `docs/TODO/terminal-target.md` builds this.

    Deliberately explicit rather than absent. The alternative was to leave this
    module out until the verifier existed, and that is what Phase 3 did -- but
    it means `--target tui` is refused as an unknown target, which reads as
    "this build does not have it" rather than "this build cannot check it yet".

    `tests/test_tui_target.py` asserts this raises, so the half-built state is
    a stated one for the single commit it exists in rather than something a
    reader has to notice.
    """
    raise NotImplementedError(
        "the terminal verifier arrives with Phase 5 of docs/TODO/terminal-target.md; "
        "`proto new --target tui --no-verify` generates a tree without checking it"
    )
