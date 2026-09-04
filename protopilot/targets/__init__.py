"""What medium the thing is built in.

A target is the answer to "what *kind of artifact* is this" — a web app served
over HTTP, or a terminal app you run in a shell. It sits beside `archetype`,
which answers "what shape of thing is this", and the two are orthogonal on
purpose: a turn-based game is the same shape whether it is drawn with `<form>`
buttons or with Textual widgets.

Each target is one module in this package, shaped exactly like the archetype
modules next door — module-level constants and plain functions, no classes:

    NAME         the stable identifier stored in spec.json
    LABEL        one human phrase, shown when a person is choosing
    SKELETON_DIR the fixed tree copied byte-for-byte into every prototype
    CODE_PASSES  the pass modules, in the order they run
    WRITABLE     the paths a pass may write, for `files.check_path`
    PROTECTED    paths under a writable glob that are skeleton anyway
    ARCHETYPES   the archetype names this target can actually build
    verifier()   a `verify.Verifies` for a generated tree

Those are the four things `docs/TODO/terminal-target.md` names as target-owned
— skeleton directory, pass tuple, allowed write paths, verifier — plus the
matrix declaration, and each of them is defined **here and nowhere else**.
`render.SKELETON_DIR`, `build.CODE_PASSES` and `files.WRITABLE` used to hold
three of them; they were moved rather than copied, because two definitions of a
rule drift within the week and the copy that is wrong is the one being read.

**Discovery is by module presence**, like `protopilot/archetypes/`: a file in
this directory is a registered target and there is deliberately no list to
update beside it. The imports happen inside `_modules()` rather than at the top
of this file, and that is load-bearing rather than stylistic — a target module
imports the pass modules, the pass package imports this one to resolve the
write guard, and importing eagerly here would close that ring at import time.

Two ways this axis deliberately does **not** copy the archetype axis:

- **An unknown target raises; an unknown archetype falls back.**
  `archetypes.for_spec` returns `crud` for a name it does not have, because a
  tree of the wrong shape still builds and beats refusing to generate. That
  reasoning does not survive the move to this axis: the target picks the
  skeleton, the passes and the verifier, so falling back would hand somebody a
  FastAPI app because they asked for a terminal one and this build had never
  heard of it. The plan's own rule for the matrix — *refused by name, not
  generated into something broken* — is the rule here too.
- **`DEFAULT` is not `Spec.target`'s default.** They are the same string today
  and they answer different questions. `Spec.target = "web"` says what a
  `spec.json` written before this axis existed **meant**, and it stays `web`
  forever. `DEFAULT` says what a *new* spec is born with, and
  `docs/TODO/terminal-target.md` Phase 6 flips it. Collapsing them into one
  constant would make that flip silently rewrite the meaning of every old spec.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

#: The root every target's skeleton lives under, defined once.
#:
#: A target's own `SKELETON_DIR` is derived from this, so the answer to "where
#: is the fixed tree" is written down in one place. It used to be
#: `render.SKELETON_DIR`, which could only ever name one of them.
SKELETON_ROOT = Path(__file__).resolve().parents[2] / "skeleton"

#: The target `proto new` chooses when the user does not say.
#:
#: See the module docstring: this is NOT `Spec.target`'s field default, and the
#: two are only equal until Phase 6 of `docs/TODO/terminal-target.md`.
DEFAULT = "web"


class MissingTarget(KeyError):
    """Asked for a target that is not installed.

    Carries what exists, because the failure is almost always a typo or a spec
    written against a newer version, and neither is diagnosable from the name
    that was wrong on its own.
    """

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        known = ", ".join(available) or "none"
        super().__init__(f"unknown target {name!r}; this build has: {known}")

    def __str__(self) -> str:
        # KeyError quotes its own message; that reads as a doubly-quoted string
        # in a CLI error where the message is the whole of what a user sees.
        return self.args[0]


class UnsupportedPair(ValueError):
    """This target cannot build this archetype.

    Raised at intake, before a token is spent, and it names **both** halves.
    A matrix with holes stated is honest; a matrix with holes discovered at
    verify time is the tool lying about its own coverage — and the person
    reading the failure cannot tell which axis to change unless both are in it.
    """

    def __init__(self, target: str, archetype: str, supported: tuple[str, ...]) -> None:
        self.target = target
        self.archetype = archetype
        self.supported = supported
        known = ", ".join(supported) or "none"
        super().__init__(f"the {target!r} target cannot build the {archetype!r} archetype; it builds: {known}")


def _modules() -> dict[str, ModuleType]:
    """Every target module, keyed by its declared NAME.

    Keyed by `NAME` rather than by filename, for the same reason the archetype
    registry is: the identifier stored in every `spec.json` is the one the
    module declares, so a file rename must not orphan every spec naming it.
    """
    found: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        name = getattr(module, "NAME", None)
        if name:
            found[name] = module
    return found


def all() -> dict[str, ModuleType]:  # noqa: A001 -- reads as targets.all()
    return _modules()


def names() -> list[str]:
    return sorted(_modules())


def get(name: str) -> ModuleType:
    modules = _modules()
    if name not in modules:
        raise MissingTarget(name, sorted(modules))
    return modules[name]


def for_spec(spec) -> ModuleType:
    """The target module a spec belongs to.

    Raises rather than falling back — see the module docstring. A spec with no
    `target` key at all does not reach this: `Spec.target` defaults to `web`,
    which is the whole job of that default.
    """
    return get(getattr(spec, "target", "") or DEFAULT)


def archetypes_for(name: str) -> tuple[str, ...]:
    """Which archetypes this target declares it can build."""
    return tuple(getattr(get(name), "ARCHETYPES", ()))


def supports(target: str, archetype: str) -> bool:
    return archetype in archetypes_for(target)


def check_pair(target: str, archetype: str) -> None:
    """Refuse an unsupported target × archetype pair, by name.

    The one enforcement point, called from `build.spec_from_idea` before the
    intake call — so both front ends get it and neither spends tokens on a
    combination that cannot be built. `MissingTarget` comes out of `get()` on
    the way past, which is the other half of the same answer: an unbuildable
    pair and an unknown target are both "say so now".
    """
    if not supports(target, archetype):
        raise UnsupportedPair(target, archetype, archetypes_for(target))
