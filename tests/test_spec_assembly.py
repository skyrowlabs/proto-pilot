"""Who decides a spec's fields, and the rule that there is only one of them.

`proto new` and `proto serve` are two front ends over one pipeline. That was
true of the passes and false of the twelve lines in front of them: the same
seven fields were assigned in `cli.py` and again in `web/app.py`, agreeing
only because one person wrote both. The web module's own docstring claimed to
be "a second caller of the pipeline, not a second implementation of it" while
being exactly that.

It is the workspace's own rule about seams, one repo in: two writers of the
same artifact agree by construction, and the disagreement shows up later, in
whichever one somebody forgot to edit.

The amend path had already gone wrong that way, silently, which is what
`test_an_amend_keeps_*` is here to stop happening twice.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from protopilot import build as builder
from protopilot.llm import OfflineLLM
from protopilot.spec import MODEL_OWNED_EXCLUSIONS, Spec, Theme, intake_schema

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


class FakeLLM(OfflineLLM):
    """Offline for intake, but answering `structured` -- which the real offline
    backend refuses, because a baseline cannot read a change request."""

    def __init__(self, payload: dict) -> None:
        super().__init__()
        self.payload = payload

    def structured(self, **_) -> dict:
        return dict(self.payload)


def game_spec() -> Spec:
    return Spec(
        name="Kitten Chess",
        slug="kitten_chess",
        purpose="Two people take turns.",
        archetype="turn-based-game",
        theme=Theme(subject="cats and dogs", motif="paw prints"),
        answers={"board_shape": "3x3", "win_condition": "a line of three"},
        extra={"width": 7, "height": 6, "win_length": 4},
        port=8099,
    )


# -- one implementation ---------------------------------------------------


def test_only_one_module_decides_a_spec_field():
    """Recomputed, not listed: every assignment to a spec attribute anywhere in
    the package is found, and they must all live in the module that owns the
    decision. A front end that starts deciding for itself fails here on the
    first line it writes, which is the moment it is cheapest to say no.

    `cli.py:new --port` is the one exception and it is not a spec decision: it
    sets the port on an ALREADY BUILT spec for `proto up`, where the user is
    moving a running app to a different port.
    """
    pattern = re.compile(r"^\s*(?:spec|updated)\.([a-z_]+)\s*=[^=]", re.M)
    offenders: dict[str, set[str]] = {}
    for path in sorted(Path("protopilot").rglob("*.py")):
        if path.name == "build.py":
            continue
        found = {m.group(1) for m in pattern.finditer(path.read_text(encoding="utf-8"))}
        if found:
            offenders[str(path)] = found
    assert offenders == {"protopilot/cli.py": {"port"}}, f"a spec field is being decided outside build.py: {offenders}"


#: The two modules allowed to start a spec, and why there are exactly two.
#:
#: `cli.py` is the scriptable path; `generation.py` is the job path, which BOTH
#: the web front end and the console drive. A third entry here means a front end
#: has started assembling a spec for itself, which is the drift the test above
#: catches on the field level and this one catches on the call level.
SPEC_CALLERS = {"protopilot/cli.py", "protopilot/generation.py"}


def test_only_the_two_entry_points_assemble_a_spec():
    """Recomputed, not listed — the list is the *expectation*, not the search.

    This used to name `protopilot/web/app.py` directly and assert the call was
    in it. That was true until `run_generation` moved out of the web module so a
    second front end could drive it without importing FastAPI, at which point
    the test failed for the right reason and by the wrong mechanism: it was
    checking an address rather than a property. A hardcoded pair also cannot
    notice a *third* caller appearing, which is the direction that matters now
    that there are three front ends and two of them share one runner.
    """
    found = {
        str(path)
        for path in sorted(Path("protopilot").rglob("*.py"))
        if path.name != "build.py" and "spec_from_idea(" in path.read_text(encoding="utf-8")
    }
    assert found == SPEC_CALLERS, f"a spec is being assembled somewhere new: {found ^ SPEC_CALLERS}"

    for path in sorted(SPEC_CALLERS):
        source = Path(path).read_text(encoding="utf-8")
        assert "spec_from_idea(" in source, f"{path} does not go through build.spec_from_idea"


def test_every_front_end_reaches_the_pipeline_rather_than_reimplementing_it():
    """The positive half, for each of the three.

    The CLI calls `build` directly; the web front end and the console both go
    through `generation.run_generation`. What none of them may do is run passes
    of their own — a front end that called `run_pass` would be a second
    implementation of the pipeline wearing a first one's name.
    """
    assert "amend_spec(" in Path("protopilot/cli.py").read_text(encoding="utf-8")

    for path in ("protopilot/web/app.py", "protopilot/console/app.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert "run_generation" in source, f"{path} does not drive the shared runner"
        assert "run_pass(" not in source, f"{path} runs passes itself instead of going through build"


# -- what an amend must not lose ------------------------------------------


def test_the_carried_set_is_derived_from_the_exclusions():
    """The list that must never be written by hand.

    `MODEL_OWNED_EXCLUSIONS` is exactly the set the amend schema omits, so it
    is exactly the set an amend response cannot contain. Deriving one from the
    other means the next model-owned field is carried without anybody
    remembering this rule exists.
    """
    assert set(MODEL_OWNED_EXCLUSIONS) <= set(builder.CARRIED_THROUGH_AMEND)
    for name in MODEL_OWNED_EXCLUSIONS:
        assert name not in intake_schema()["properties"], f"{name} is in the schema; it no longer needs carrying"


def test_an_amend_keeps_the_archetype_theme_answers_and_extra():
    """The defect this file exists for.

    `proto add "add a timer"` on a turn-based game used to return a spec with
    `archetype == "crud"`, no theme, no answers and a default board -- because
    the amend schema cannot carry them and nothing carried them by hand. The
    next generation then built a tracking app over a game's entities, and
    nothing anywhere went red.
    """
    previous = game_spec()
    # A well-formed amend response: exactly the fields the schema allows.
    payload = {k: v for k, v in previous.model_dump(mode="json").items() if k in intake_schema()["properties"]}
    payload["name"] = "Kitten Chess Deluxe"

    updated = builder.amend_spec(previous, "make it fancier", FakeLLM(payload))

    assert updated.name == "Kitten Chess Deluxe", "the change the user asked for must still land"
    assert updated.archetype == "turn-based-game"
    assert updated.target == previous.target, "the medium is not the model's to revise on an amend either"
    assert updated.theme is not None and updated.theme.subject == "cats and dogs"
    assert updated.answers == previous.answers
    assert updated.extra == previous.extra


def test_an_amend_keeps_identity():
    """The slug is the database name and the port is the tab the user has open,
    so neither is the model's to revise."""
    previous = game_spec()
    payload = {k: v for k, v in previous.model_dump(mode="json").items() if k in intake_schema()["properties"]}
    payload["slug"], payload["port"] = "something_else", 9999

    updated = builder.amend_spec(previous, "rename it", FakeLLM(payload))

    assert (updated.slug, updated.port) == (previous.slug, previous.port)


def test_an_amend_re_resolves_screens_from_the_archetype():
    """Screens are the archetype's rule, and the archetype was just carried
    forward rather than re-decided -- so a model's guess at the screen set is
    not the thing to keep. A board game amended into a CRUD spread is the same
    bug as the CLI hardcoding `crud.screens()`, one pass later."""
    previous = game_spec()
    payload = {k: v for k, v in previous.model_dump(mode="json").items() if k in intake_schema()["properties"]}
    payload["screens"] = [{"name": "Kittens", "path": "/kittens", "entity": "Kitten", "kind": "list"}]

    updated = builder.amend_spec(previous, "add a page", FakeLLM(payload))

    paths = {s.path for s in updated.screens}
    assert "/board" in paths, "the archetype's own pages must come back"
    assert "/kittens" not in paths, "a model-proposed list screen is not the archetype's to accept"


# -- the new path ---------------------------------------------------------


def test_spec_from_idea_sets_the_axes_the_model_never_sees():
    spec = builder.spec_from_idea(
        "a kitten chess app",
        OfflineLLM(),
        archetype="turn-based-game",
        target="web",
        port=8123,
        direction="keep it small",
        theme=Theme(subject="cats"),
        answers={"board_shape": "3x3"},
    )
    assert spec.archetype == "turn-based-game"
    assert spec.target == "web"
    assert spec.theme is not None and spec.theme.subject == "cats"
    assert spec.answers == {"board_shape": "3x3"}
    assert spec.port == 8123
    assert "/board" in {s.path for s in spec.screens}


def test_an_empty_theme_is_stored_as_no_theme():
    """`Theme()` with every field blank and `None` mean the same thing, and the
    UI pass checks for one of them. Two ways to say "no theme" is one more than
    the consumer knows about."""
    spec = builder.spec_from_idea(
        "a gear tracker", OfflineLLM(), archetype="crud", target="web", port=8124, theme=Theme()
    )
    assert spec.theme is None
