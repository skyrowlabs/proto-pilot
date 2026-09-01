"""The question pass.

Its whole value is being cheap and skippable, so the tests are about the
plumbing around it rather than the wording of the questions: answers must
reach the passes that need them, and an unanswered questionnaire must not
corrupt the direction that was already given.
"""

from __future__ import annotations

import pytest

from protopilot.passes import clarify

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


def test_build_includes_the_idea_and_the_direction():
    system, user = clarify.build("3d chess, cats vs dogs", "make it playable")
    assert "3d chess, cats vs dogs" in user
    assert "make it playable" in user
    # The runtime's limits are stated up front, so it asks about the version
    # that can actually be built rather than the one that cannot.
    assert "No JavaScript" in system or "no JavaScript" in system


def test_build_omits_an_empty_direction():
    _, user = clarify.build("3d chess", "   ")
    assert "Direction" not in user


def test_answers_fold_into_the_direction():
    out = clarify.answers_to_direction("keep it simple", {"Who plays?": "two people"})
    assert "keep it simple" in out and "two people" in out


def test_blank_answers_are_dropped():
    out = clarify.answers_to_direction("keep it simple", {"Who plays?": "  ", "X": ""})
    assert out == "keep it simple"


def test_answers_with_no_prior_direction():
    out = clarify.answers_to_direction("", {"Who plays?": "two people"})
    assert out == "Who plays?: two people"


def test_no_answers_and_no_direction_is_empty():
    assert clarify.answers_to_direction("", {}) == ""


def test_schema_bounds_the_questionnaire():
    # A long questionnaire is a worse product than no questionnaire.
    assert clarify.SCHEMA["properties"]["questions"]["maxItems"] == 4
    assert clarify.SCHEMA["properties"]["questions"]["minItems"] == 1
