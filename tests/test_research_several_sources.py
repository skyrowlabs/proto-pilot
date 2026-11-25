"""A finding drawn from several fetched pages cites each of them (#53)."""

from __future__ import annotations

import pytest
from research_script import OTHER, URL, assumed, fetched, old_shape, transcript

from protopilot.llm import research_result
from protopilot.plan.model import Fetch, Plan, Topic
from protopilot.plan.passes import misshapen, research

pytestmark = [pytest.mark.unit]

PAIRED = "Square's free plan costs nothing a month, while ChowNow runs a flat monthly fee."


def plan() -> Plan:
    return Plan(
        slug="p", title="P", idea="i", depth="shallow", topics=[Topic(slug=s, title=s, why="w") for s in "abcd"]
    )


def usable(*urls: str) -> list[Fetch]:
    return [Fetch(url=url, usable=True) for url in urls]


def finding(*urls: str) -> dict:
    return {"text": PAIRED, "kind": "cited", "sources": [{"url": u, "title": f"T {u}"} for u in urls]}


def applied(row: dict, fetches: list[Fetch]) -> tuple[Plan, list]:
    after, record = research.apply(plan(), "a", {"findings": [row, assumed(), assumed("x")]}, fetches)
    return after, next(t for t in after.topics if t.slug == "a").findings


def test_a_finding_citing_two_usable_fetches_gets_both_source_ids():
    after, findings = applied(finding(URL, OTHER), usable(URL, OTHER))
    assert not findings[0].assumption and len(findings[0].source_ids) == 2
    assert {s.url for s in after.sources if s.id in findings[0].source_ids} == {URL, OTHER}


def test_one_unfetched_page_among_them_demotes_the_finding_and_is_listed_unfetched():
    _, findings = applied(finding(URL, OTHER), usable(URL))
    record = research.apply(plan(), "a", {"findings": [finding(URL, OTHER), assumed(), assumed("x")]}, usable(URL))[1]
    assert findings[0].assumption and findings[0].source_ids == [] and record.unfetched == [OTHER]


def test_the_same_page_listed_twice_is_one_source():
    _, findings = applied(finding(URL, URL), usable(URL))
    assert len(findings[0].source_ids) == 1


def test_an_answer_in_the_old_one_url_shape_still_replays_and_cites_its_page():
    old = research_result(old_shape(transcript(fetches=[fetched()])), "r")
    assert "source_url" in old["findings"][0]
    data = research.upgraded(old)
    assert not misshapen(research.schema(plan()), data)
    _, record = research.apply(plan(), "a", data, usable(URL))
    assert record.state == "researched"


def test_the_schema_bounds_the_pages_one_finding_may_name():
    items = research.schema(plan())["properties"]["findings"]["items"]["properties"]["sources"]
    assert items["maxItems"] == research.MAX_SOURCES
