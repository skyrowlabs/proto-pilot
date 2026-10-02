"""What shape of thing is being built.

An archetype is the answer to "what *kind* of app is this" — and it is a type
rather than a paragraph of prose. Before it existed, `intake.py`'s system prompt
carried a five-paragraph essay explaining how to build a board game out of form
buttons and inline SVG: untyped, untestable, and paid for on every generation
whether the idea was a game or a gear list.

Each archetype is one module in this package, shaped like the pass modules it
sits beside — module-level constants and plain functions, no classes:

    NAME      the stable identifier stored in spec.json
    LABEL     one human phrase, shown when a person is choosing
    MATCHES   one line of examples, handed to the classifier
    QUESTIONS the fixed question set, each with a stable id
    EXTRA     a pydantic model validating this archetype's slice of spec.extra
    screens() the screen-generation rule for this shape
    brief()   the fragment every code pass is given, in the user message
    ASSETS    fixed files this archetype adds to the skeleton

and, optionally, any of the five baseline generators it wants to replace:

    models_py(spec) seed_py(spec) routes_py(spec) smoke_py(spec)
    templates_for(spec)

An archetype that defines none of them gets `baseline.py`'s, which is what
`crud` does -- the baseline *is* its implementation. Defining one is how a
shape whose pages are a board rather than a list gets built offline.

**Discovery is by module presence.** A file in this directory is a registered
archetype. There is deliberately no list to update alongside it, because a
registry you must remember to edit is a registry that goes stale the first busy
afternoon — the same reasoning as the marker-based test suites this repo uses.

Two rules an archetype may not break:

- **It may not choose a stack.** Questions, typed fields, a screen rule and
  prompt text — never `requirements.txt`, the Dockerfile or the compose file.
  The moment an archetype can pick a stack we are back to N unrunnable variants
  and debugging all of them, which is the thing the fixed skeleton exists to
  prevent.
- **It ships with its offline baseline in the same change.** The baseline is
  what CI runs, so an archetype without one is an archetype the test suite
  cannot see. This is what bounds how many archetypes are worth having.

`ASSETS` is declared and empty. An archetype whose screens genuinely cannot work
as a full page reload — a simulator that ticks — would need a fixed static file
copied byte-for-byte into the skeleton, never generated. That is a change to a
load-bearing invariant and it has not been made; the field exists so making it
later is a value in a tuple rather than a refactor.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

#: The archetype every spec gets when nothing better is known.
#:
#: It is the fallback for a low-confidence classification precisely because it
#: is the one shape that produces something usable for any idea at all. "I am
#: not sure" should not produce a board with no game on it.
DEFAULT = "crud"


class MissingArchetype(KeyError):
    """Asked for an archetype that is not installed.

    Carries what exists, because the failure is almost always a typo or a spec
    written against a newer version, and neither is diagnosable from the name
    that was wrong on its own.
    """

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        known = ", ".join(available) or "none"
        super().__init__(f"unknown archetype {name!r}; this build has: {known}")

    def __str__(self) -> str:
        # KeyError quotes its own message; that reads as a doubly-quoted string
        # in a CLI error where the message is the whole of what a user sees.
        return self.args[0]


def _modules() -> dict[str, ModuleType]:
    """Every archetype module, keyed by its declared NAME.

    Keyed by `NAME` rather than by filename: the identifier stored in every
    `spec.json` is the one the module declares, so a file rename must not
    silently orphan every spec that referenced it.
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


def all() -> dict[str, ModuleType]:  # noqa: A001 -- reads as archetypes.all()
    return _modules()


def names() -> list[str]:
    return sorted(_modules())


def get(name: str) -> ModuleType:
    modules = _modules()
    if name not in modules:
        raise MissingArchetype(name, sorted(modules))
    return modules[name]


def matches() -> str:
    """The classifier's menu, generated from what is installed.

    Adding an archetype teaches the classifier by existing. A hand-written list
    in a prompt is the same stale-registry problem one layer up, and the layer
    where being out of date is hardest to notice — a missing line does not
    fail, it just means that archetype is never chosen.
    """
    lines = []
    for name in names():
        module = _modules()[name]
        label = getattr(module, "LABEL", "")
        examples = getattr(module, "MATCHES", "")
        line = f"- {name}: {label}" + (f" — {examples}" if examples else "")
        # What this shape already asks. The classifier is told not to repeat the
        # archetype's fixed questions, and until this was here it could not
        # comply: it was never shown them. A live call duly came back with
        # `rules_depth` next to a fixed `rules_enforcement`. It cannot be
        # deferred until after classification either -- the questions are wanted
        # in the same response as the choice.
        asks = ", ".join(q["id"] for q in getattr(module, "QUESTIONS", ()))
        if asks:
            line += f"\n  (already asks: {asks})"
        lines.append(line)
    return "\n".join(lines)


def for_spec(spec) -> ModuleType:
    """The archetype module a spec belongs to, never raising.

    A spec can name an archetype this build does not have -- one written by a
    newer version, or hand-edited. Falling back beats refusing to generate: the
    default produces something usable for any spec, and a tree that will not
    build is worse than a tree of the wrong shape.
    """
    try:
        return get(getattr(spec, "archetype", "") or DEFAULT)
    except MissingArchetype:
        return get(DEFAULT)


def generator(spec, kind: str):
    """An archetype's override for one baseline generator, or None.

    `kind` is the `baseline` function name -- `models_py`, `seed_py`,
    `routes_py`, `smoke_py`, `templates_for`. An archetype that does not define
    one gets the baseline's, which is why `crud` defines none of them: the
    baseline *is* its implementation.
    """
    return getattr(for_spec(spec), kind, None)


def brief_for(spec) -> str:
    """The archetype's prompt fragment, or nothing."""
    fragment = getattr(for_spec(spec), "brief", None)
    return fragment() if callable(fragment) else ""


def screens_for(spec, proposed=None) -> list[dict]:
    """This spec's screens: the archetype's set, plus any extra custom pages.

    The archetype owns the rule -- that is the whole point of the axis, and
    hardcoding `crud.screens()` at the call sites is how a generated board game
    ended up being checked for `/kittens`, `/kittens/new` and `/kittens/1`. The
    browser stage found it; nothing else could, because every unit test built
    the spec by calling the right archetype directly.

    Model-proposed `custom` screens survive on top, because intake is allowed to
    add a page the archetype did not think of. Its list/detail/form screens do
    not: those are the archetype's to decide, and a model second-guessing them
    is how the tests and the routes come to disagree.
    """
    base = for_spec(spec).screens(spec)
    known = {s["path"] for s in base}
    extra = [
        dict(s)
        for s in (proposed or [])
        if (s.get("kind") if isinstance(s, dict) else getattr(s, "kind", None)) == "custom"
        and (s.get("path") if isinstance(s, dict) else getattr(s, "path", None)) not in known
    ]
    return base + extra
