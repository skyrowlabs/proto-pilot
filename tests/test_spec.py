from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from protopilot.spec import Entity, Field_, Screen, Spec, intake_schema

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


def test_plural_is_derived_when_absent():
    assert Entity(name="Trip").plural == "trips"
    assert Entity(name="Category").plural == "categories"
    assert Entity(name="Box").plural == "boxes"
    assert Entity(name="Day").plural == "days"


def test_pascal_and_snake_names_are_enforced():
    with pytest.raises(ValidationError):
        Entity(name="trip")
    with pytest.raises(ValidationError):
        Field_(name="Title")
    with pytest.raises(ValidationError):
        Spec(name="X", slug="Not-Snake", purpose="p")


def test_reserved_field_names_are_rejected():
    # `id` is added by the generator; a spec field of the same name would
    # produce a model with two primary keys and a confusing traceback.
    with pytest.raises(ValidationError):
        Field_(name="id")


def test_screen_path_must_be_absolute():
    with pytest.raises(ValidationError):
        Screen(name="Trips", path="trips")


def test_round_trip_through_disk(spec, tmp_path):
    spec.save(tmp_path)
    assert Spec.load(tmp_path) == spec


def test_intake_schema_is_self_contained_and_strict():
    schema = intake_schema()
    text = json.dumps(schema)
    # Nothing may reference $defs: the API takes one schema object.
    assert "$ref" not in text and "$defs" not in schema

    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(schema)


def test_summary_names_what_it_cannot_do(spec):
    """The review checkpoint is the only place a downscope can be caught.

    Building something smaller than what was asked for, and saying nothing,
    is the failure mode that looks identical to success.
    """
    spec.limits = ["the board is flat, not 3D", "two people share one browser"]
    out = spec.summary()
    assert "not in this version:" in out
    assert "- the board is flat, not 3D" in out


def test_summary_stays_quiet_when_the_idea_fits(spec):
    assert "not in this version" not in spec.summary()
