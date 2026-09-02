"""The two axes, and the registry that reads them.

Phase 1 added `archetype`, `theme` and `answers` to the spec; Phase 2 put the
first archetype behind them. What is pinned here is that the axes survive a
round trip, that a spec written before they existed still loads, that the human
review checkpoint shows them, that intake is not asked to invent the fields it
does not own, and that the registry's contract is **recomputed** over whatever
is installed rather than listed — so archetype number two cannot ship
half-implemented or reach for the stack.

See docs/TODO/archetypes-and-theme.md.
"""

from __future__ import annotations

import json

import pytest

from protopilot import archetypes
from protopilot.spec import MODEL_OWNED_EXCLUSIONS, Spec, Theme, intake_schema

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


# ── the axes carry ───────────────────────────────────────────────────────


def test_a_new_spec_defaults_to_crud():
    assert Spec(name="X", slug="x", purpose="p").archetype == archetypes.DEFAULT == "crud"


def test_both_axes_survive_a_save_and_reload(tmp_path, spec):
    spec.archetype = "turn-based-game"
    spec.theme = Theme(palette="warm", motif="paw prints", tone="playful", subject="cats")
    spec.answers = {"turn_order": "alternating", "players": "two"}
    spec.save(tmp_path)

    reloaded = Spec.load(tmp_path)

    assert reloaded.archetype == "turn-based-game"
    assert reloaded.theme is not None and reloaded.theme.subject == "cats"
    assert reloaded.answers == {"turn_order": "alternating", "players": "two"}


def test_a_spec_written_before_archetypes_existed_still_loads(tmp_path):
    """The compatibility case, written the way it actually occurs: a spec.json
    on disk with none of the three new keys in it."""
    legacy = {
        "name": "Gear List",
        "slug": "gearlist",
        "purpose": "Track camping gear.",
        "entities": [],
        "screens": [],
        "auth": "none",
        "jobs": [],
        "external_apis": [],
        "port": 8080,
        "protopilot_version": "0.1.0",
        "direction": "",
        "limits": [],
    }
    (tmp_path / ".protopilot").mkdir()
    (tmp_path / ".protopilot" / "spec.json").write_text(json.dumps(legacy))

    loaded = Spec.load(tmp_path)

    assert loaded.archetype == "crud"
    assert loaded.theme is None
    assert loaded.answers == {}


def test_the_shipped_kitten_chess_spec_still_loads():
    """A real artifact from before this change, not a fixture of one."""
    from pathlib import Path

    tree = Path(__file__).resolve().parents[1] / "prototypes" / "kitten_chess"
    if not (tree / ".protopilot" / "spec.json").exists():
        pytest.skip("kitten_chess prototype is not present in this checkout")
    assert Spec.load(tree).archetype == "crud"


# ── the review checkpoint ────────────────────────────────────────────────


def test_the_checkpoint_shows_both_axes(spec):
    """The only human gate in the tool. An axis it does not print is an axis
    nobody reviews, which is the same as one nobody chose."""
    spec.archetype = "turn-based-game"
    spec.theme = Theme(subject="cats", tone="playful")
    spec.answers = {"turn_order": "alternating"}

    summary = spec.summary()

    assert "archetype: turn-based-game" in summary
    assert "cats" in summary and "playful" in summary
    assert "turn_order: alternating" in summary


def test_an_empty_theme_is_not_printed_as_noise(spec):
    spec.theme = Theme()
    assert "theme:" not in spec.summary()


# ── what the model is asked for ──────────────────────────────────────────


def test_intake_is_not_asked_to_invent_the_fields_it_does_not_own():
    """`_strictify` makes every property required, so a field left in the
    schema is one the model MUST produce a value for. These three have an owner
    that is not intake, and a confident second opinion would overwrite it."""
    properties = intake_schema()["properties"]
    for excluded in MODEL_OWNED_EXCLUSIONS:
        assert excluded not in properties


def test_the_intake_schema_still_carries_everything_else():
    properties = intake_schema()["properties"]
    for owned in ("name", "slug", "purpose", "entities", "screens", "limits", "direction"):
        assert owned in properties


# ── the registry ─────────────────────────────────────────────────────────


def test_an_unknown_archetype_names_what_does_exist():
    """A bad name is nearly always a typo or a spec from a newer build, and
    neither is diagnosable from the wrong name alone."""
    with pytest.raises(archetypes.MissingArchetype) as raised:
        archetypes.get("simulator")

    message = str(raised.value)
    assert "simulator" in message
    assert "this build has" in message


def test_crud_is_registered_by_existing():
    """Discovery is by module presence — no list to keep in sync."""
    assert "crud" in archetypes.names()
    assert archetypes.get("crud").NAME == "crud"


def test_the_default_archetype_is_one_that_actually_exists():
    """`DEFAULT` is the fallback for a low-confidence classification, so a
    default naming a module nobody wrote would fail at the worst moment."""
    assert archetypes.DEFAULT in archetypes.names()


def test_the_classifier_menu_is_generated_from_what_is_installed():
    """Adding an archetype must teach the classifier by existing. A hand-written
    list in a prompt goes stale silently: a missing line does not fail, it just
    means that archetype is never chosen."""
    menu = archetypes.matches()
    for name in archetypes.names():
        assert name in menu
    assert archetypes.get("crud").MATCHES in menu


def test_every_archetype_declares_the_interface_the_passes_rely_on():
    """Recomputed over the package rather than listed, so archetype number two
    cannot ship half-implemented."""
    for name, module in archetypes.all().items():
        for attribute in ("NAME", "LABEL", "MATCHES", "QUESTIONS", "ASSETS", "screens", "brief"):
            assert hasattr(module, attribute), f"{name} is missing {attribute}"


def test_generator_overrides_are_optional_and_resolve():
    """An archetype replaces a baseline generator by defining it, and gets the
    baseline's by not defining it. `crud` defines none — the baseline IS its
    implementation — so every kind must resolve to None for it."""
    from protopilot import baseline
    from protopilot.spec import Spec

    kinds = ("models_py", "seed_py", "routes_py", "smoke_py", "templates_for")
    crud_spec = Spec(name="X", slug="x", purpose="p", archetype="crud")
    for kind in kinds:
        assert archetypes.generator(crud_spec, kind) is None, f"crud should not override {kind}"
        # And the name it would fall through to actually exists.
        assert hasattr(baseline, kind), f"baseline has no {kind} to fall through to"


def test_a_spec_naming_an_archetype_this_build_lacks_still_generates():
    """Falling back beats refusing: a tree that will not build is worse than a
    tree of the wrong shape, and a spec can name a shape a newer version had."""
    from protopilot.spec import Spec

    stale = Spec(name="X", slug="x", purpose="p", archetype="from-the-future")
    assert archetypes.for_spec(stale).NAME == archetypes.DEFAULT


def test_fixed_questions_carry_stable_unique_ids():
    """The ids key `spec.answers` and the passes read them by name. A duplicate
    or a missing id silently drops an answer."""
    for name, module in archetypes.all().items():
        ids = [q["id"] for q in module.QUESTIONS]
        assert all(ids), f"{name} has a question with no id"
        assert len(ids) == len(set(ids)), f"{name} has duplicate question ids: {ids}"


def test_no_archetype_reaches_for_the_stack():
    """The constraint that keeps this from becoming a stack-picking generator.
    An archetype contributes questions, a screen rule and prompt text — never
    requirements.txt, the Dockerfile or the compose file."""
    import inspect

    forbidden = ("requirements.txt", "Dockerfile", "compose.yml")
    for name, module in archetypes.all().items():
        source = inspect.getsource(module)
        for token in forbidden:
            assert token not in source, f"{name} references {token}"
