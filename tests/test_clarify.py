"""The question pass, which is also the classifier.

Its whole value is being cheap and skippable, so the tests are about the
plumbing rather than the wording: the shape must be classifiable and
overrulable, answers must reach the passes that need them in the form that has
a contract, and an unanswered questionnaire must not corrupt the direction that
was already given.

The half these cannot cover is whether the classifier is any *good* — that
needs a live call, and the offline baseline cannot read an idea. Phase 3 of
docs/implementations/spec/archetypes-and-theme.md spent one deliberately.
"""

from __future__ import annotations

import pytest

from protopilot import archetypes
from protopilot.passes import clarify

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


# ── the prompt ───────────────────────────────────────────────────────────


def test_build_includes_the_idea_and_the_direction():
    system, user = clarify.build("3d chess, cats vs dogs", "make it playable")
    assert "3d chess, cats vs dogs" in user
    assert "make it playable" in user
    # The runtime's limits are stated up front, so it classifies the version
    # that can actually be built rather than the one that cannot.
    assert "No JavaScript" in system or "no JavaScript" in system


def test_build_omits_an_empty_direction():
    _, user = clarify.build("3d chess", "   ")
    assert "Direction" not in user


def test_the_prompt_lists_every_installed_archetype():
    """Adding an archetype must teach the classifier by existing. A menu
    hand-written in a prompt goes stale silently — a missing line does not
    fail, it just means that shape is never chosen."""
    system, _ = clarify.build("anything")
    for name in archetypes.names():
        assert name in system


def test_the_prompt_shows_what_each_archetype_already_asks():
    """The classifier is told not to repeat the archetype's fixed questions.
    Until the menu carried them it could not comply — it had never seen them —
    and a live call came back with `rules_depth` beside a fixed
    `rules_enforcement`. It cannot be deferred past classification either: the
    questions are wanted in the same response as the choice."""
    system, _ = clarify.build("anything")
    for name in archetypes.names():
        for question in archetypes.get(name).QUESTIONS:
            assert question["id"] in system, f"{name}.{question['id']} is not shown to the classifier"


def test_the_prompt_names_the_fallback():
    system, _ = clarify.build("anything")
    assert archetypes.DEFAULT in system


# ── the schema ───────────────────────────────────────────────────────────


def test_the_archetype_field_is_an_enum_of_what_exists():
    """An enum removes a failure mode rather than validating it after the
    fact: the model cannot name a shape this build does not have."""
    assert clarify.schema()["properties"]["archetype"]["enum"] == archetypes.names()


def test_the_schema_bounds_the_questionnaire():
    """A long questionnaire is a worse product than no questionnaire, and the
    fixed set is already being asked — so the model's own budget is small."""
    questions = clarify.schema()["properties"]["questions"]
    assert questions["maxItems"] == 2
    assert questions["minItems"] == 0, "zero extra questions must be a legal answer"


def test_the_schema_is_strict():
    schema = clarify.schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


# ── classification and its fallback ──────────────────────────────────────


def test_a_confident_classification_is_taken():
    assert clarify.chosen_archetype({"archetype": "crud", "confidence": "high"}) == "crud"


def test_low_confidence_falls_back_to_the_default():
    """A wrong shape is five passes of the wrong app, so an unsure model lands
    on the one archetype that produces something usable for any idea."""
    result = {"archetype": "crud", "confidence": "low"}
    assert clarify.chosen_archetype(result) == archetypes.DEFAULT


def test_an_archetype_this_build_does_not_have_falls_back():
    """Belt and braces behind the enum: a spec from a newer build, or a backend
    that ignores the enum, must not produce an archetype nobody can load."""
    assert clarify.chosen_archetype({"archetype": "simulator", "confidence": "high"}) == archetypes.DEFAULT


def test_a_missing_archetype_falls_back_rather_than_raising():
    assert clarify.chosen_archetype({}) == archetypes.DEFAULT


# ── answers keep their contract ──────────────────────────────────────────


def test_fixed_answers_land_typed_and_model_answers_become_prose():
    """The split is the point. An answer to a question the archetype declared
    has a stable id and a consumer that reads it by name; an answer to one the
    model invented has neither, so calling it structured would be a lie."""
    known = sorted(clarify.fixed_ids("crud"))[0]
    typed, prose = clarify.split_answers("crud", {known: "gigs", "some_model_question": "weekly"})

    assert typed == {known: "gigs"}
    assert "weekly" in prose
    assert known not in prose


def test_blank_answers_are_dropped_from_both_halves():
    known = sorted(clarify.fixed_ids("crud"))[0]
    typed, prose = clarify.split_answers("crud", {known: "   ", "invented": ""})
    assert typed == {} and prose == ""


def test_an_answer_to_an_unknown_question_is_never_silently_lost():
    """It has no schema, so it cannot be typed — but dropping it would discard
    something the person actually said."""
    _, prose = clarify.split_answers("crud", {"whatever": "matters to me"})
    assert "matters to me" in prose


def test_merge_direction_keeps_what_the_user_typed():
    assert clarify.merge_direction("keep it simple", "x: y") == "keep it simple. x: y"


def test_merge_direction_with_nothing_to_add():
    assert clarify.merge_direction("keep it simple", "") == "keep it simple"
    assert clarify.merge_direction("", "") == ""


def test_answers_to_direction_is_gone():
    """Deleted, not deprecated. Two routes from an answer to a pass means the
    typed one gets quietly bypassed and we are back to prose with extra steps."""
    assert not hasattr(clarify, "answers_to_direction")


# ── the fixed set comes from the registry, not the model ─────────────────


def test_fixed_questions_come_from_the_archetype():
    ids = {q["id"] for q in clarify.fixed_questions("crud")}
    assert ids == {q["id"] for q in archetypes.get("crud").QUESTIONS}


def test_fixed_questions_for_an_unknown_archetype_fall_back():
    """Reached from an HTTP handler with a name in a query string, so it must
    degrade rather than raise."""
    assert clarify.fixed_questions("nonsense") == clarify.fixed_questions(archetypes.DEFAULT)
