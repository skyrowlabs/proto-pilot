"""`plan.model`: what plan.json refuses, and the broken plans it must still hold."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from protopilot.plan.model import Dream, Edge, Finding, Plan, Source, Step, Topic, plan_path

pytestmark = [pytest.mark.unit]

UNSAFE_SLUGS = [
    "../evil",
    "..",
    ".",
    "a/b",
    "a\\b",
    "/etc/passwd",
    "topics/../../evil",
    "evil\n",
    "evil\x00",
    "evil.md",
    "",
    "Upper",
    "1st",
    "_lead",
    "has-dash",
    "has space",
    "café",
]


def topic(slug: str = "members") -> dict:
    return {"slug": slug, "title": "Members", "why": "Who joins."}


def document() -> dict:
    """One of every record, as plan.json would spell it."""
    return {
        "slug": "tool_library",
        "title": "Tool library",
        "idea": "a tool library",
        "topics": [{**topic(), "findings": [{"text": "Idle drills.", "assumption": True}]}],
        "edges": [{"from_topic": "members", "to_topic": "members", "kind": "informs"}],
        "steps": [{"topic": "members", "action": "Ask.", "why": "First."}],
        "dreams": [
            {"id": "d1", "title": "T", "what_if": "w", "lens": "l", "anchor": "members", "takes": "t"},
        ],
        "sources": [{"id": "s1", "title": "T", "url": "https://example.test"}],
    }


def write(tree, doc: dict) -> None:
    path = plan_path(tree)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def errors(doc: dict) -> list[ErrorDetails]:
    with pytest.raises(ValidationError) as caught:
        Plan.model_validate(doc)
    return caught.value.errors()


# -- slugs ----------------------------------------------------------------


@pytest.mark.parametrize("slug", UNSAFE_SLUGS)
def test_a_topic_slug_that_is_not_a_safe_filename_is_refused(slug):
    with pytest.raises(ValidationError, match="slug must be snake_case"):
        Topic(**topic(slug))


@pytest.mark.parametrize("slug", UNSAFE_SLUGS)
def test_a_plan_slug_that_is_not_a_safe_filename_is_refused(slug):
    with pytest.raises(ValidationError, match="slug must be snake_case"):
        Plan(slug=slug, title="T", idea="i")


def test_a_traversal_slug_in_a_file_on_disk_is_refused_on_load(tmp_path):
    doc = document()
    doc["topics"][0]["slug"] = "../../evil"
    write(tmp_path, doc)
    with pytest.raises(ValidationError, match="slug must be snake_case"):
        Plan.load(tmp_path)


@pytest.mark.parametrize("slug", ["a", "a1", "first_test", "a_"])
def test_a_snake_case_slug_is_accepted(slug):
    assert Topic(**topic(slug)).slug == slug


# -- duplicates -----------------------------------------------------------


def test_duplicate_topic_slugs_are_refused_and_named():
    doc = {**document(), "topics": [topic("zed"), topic("zed"), topic("alpha"), topic("alpha"), topic("once")]}
    with pytest.raises(ValidationError, match="topic slugs must be unique: alpha, zed") as caught:
        Plan.model_validate(doc)
    assert "once" not in str(caught.value)


def test_duplicate_topic_slugs_in_a_file_on_disk_are_refused_on_load(tmp_path):
    write(tmp_path, {**document(), "topics": [topic(), topic()]})
    with pytest.raises(ValidationError, match="topic slugs must be unique: members"):
        Plan.load(tmp_path)


# -- unknown fields -------------------------------------------------------


@pytest.mark.parametrize(
    "record, loc",
    [
        (lambda d: d, ()),
        (lambda d: d["topics"][0], ("topics", 0)),
        (lambda d: d["topics"][0]["findings"][0], ("topics", 0, "findings", 0)),
        (lambda d: d["edges"][0], ("edges", 0)),
        (lambda d: d["steps"][0], ("steps", 0)),
        (lambda d: d["dreams"][0], ("dreams", 0)),
        (lambda d: d["sources"][0], ("sources", 0)),
    ],
    ids=["plan", "topic", "finding", "edge", "step", "dream", "source"],
)
def test_an_unknown_field_is_refused_on_every_record(record: Callable[[dict], dict], loc: tuple):
    doc = document()
    Plan.model_validate(doc)
    record(doc)["surplus"] = 1
    assert [(e["type"], e["loc"]) for e in errors(doc)] == [("extra_forbidden", (*loc, "surplus"))]


def test_a_misspelt_researched_is_refused_rather_than_read_as_false():
    assert [e["type"] for e in errors({**document(), "researchd": True})] == ["extra_forbidden"]


def test_a_finding_must_say_whether_it_is_an_assumption():
    doc = document()
    del doc["topics"][0]["findings"][0]["assumption"]
    assert [(e["type"], e["loc"][-1]) for e in errors(doc)] == [("missing", "assumption")]


def test_an_edge_kind_outside_the_three_is_refused():
    doc = document()
    doc["edges"][0]["kind"] = "blocks"
    assert [e["loc"] for e in errors(doc)] == [("edges", 0, "kind")]


def test_a_verdict_outside_the_two_is_refused():
    doc = document()
    doc["dreams"][0]["verdict"] = "maybe"
    assert [e["loc"] for e in errors(doc)] == [("dreams", 0, "verdict")]


# -- what must stay loadable ----------------------------------------------


def broken_plan(*edges: Edge, **over) -> Plan:
    topics = [Topic(**topic("a")), Topic(**topic("b")), Topic(**topic("c"))]
    return Plan(slug="broken", title="Broken", idea="i", topics=topics, edges=list(edges), **over)


@pytest.mark.parametrize(
    "plan",
    [
        broken_plan(Edge(from_topic="a", kind="depends-on", to_topic="ghost")),
        broken_plan(Edge(from_topic="ghost", kind="informs", to_topic="other_ghost")),
        broken_plan(
            Edge(from_topic="a", kind="depends-on", to_topic="b"),
            Edge(from_topic="b", kind="depends-on", to_topic="c"),
            Edge(from_topic="c", kind="depends-on", to_topic="a"),
        ),
        broken_plan(Edge(from_topic="a", kind="depends-on", to_topic="a")),
        broken_plan(steps=[Step(topic="ghost", action="Act.", why="Why.")]),
        broken_plan(
            dreams=[Dream(id="d1", title="T", what_if="w", lens="l", anchor="ghost", takes="t")],
        ),
    ],
    ids=["dangling-to", "dangling-both", "cycle", "self-edge", "step", "dream-anchor"],
)
def test_an_incoherent_plan_survives_a_round_trip_for_the_verifier(tmp_path, plan):
    plan.save(tmp_path)
    assert Plan.load(tmp_path) == plan


def test_a_citation_of_a_missing_source_survives_a_round_trip(tmp_path):
    finding = Finding(text="Claimed.", assumption=False, source_ids=["ghost"])
    plan = Plan(
        slug="broken",
        title="T",
        idea="i",
        topics=[Topic(**topic(), findings=[finding])],
        sources=[Source(id="s1", title="T", url="https://example.test")],
    )
    plan.save(tmp_path)
    assert Plan.load(tmp_path).topics[0].findings == [finding]


# -- persistence ----------------------------------------------------------


def test_a_plan_defaults_to_not_researched():
    assert Plan(slug="p", title="T", idea="i").researched is False


def test_save_creates_the_directory_and_keeps_non_ascii_readable(tmp_path):
    path = Plan(slug="p", title="工具 café", idea="i").save(tmp_path / "new")
    assert path == tmp_path / "new" / ".protopilot" / "plan.json"
    text = path.read_text(encoding="utf-8")
    assert '"title": "工具 café"' in text
    assert text.endswith("}\n")
