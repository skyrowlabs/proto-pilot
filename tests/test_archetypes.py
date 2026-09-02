"""Phase 1 of the archetypes plan: the two axes exist and carry.

Nothing reads them yet — that is the point of the phase. What is pinned here is
that they survive a round trip, that a spec written before they existed still
loads, that the human review checkpoint shows them, and that the intake model is
not asked to invent the ones it does not own.

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


def test_the_registry_is_empty_until_phase_2_adds_crud():
    """Honest about where the plan is. Phase 2 extracts `crud`; until then the
    package is the mechanism with nothing in it, and a test asserting otherwise
    would be asserting a future."""
    assert archetypes.names() == []
    assert archetypes.matches() == ""
