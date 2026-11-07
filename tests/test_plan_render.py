"""`plan.render`: what each page says, and what can and cannot change it."""

from __future__ import annotations

import pytest

from protopilot.plan import render
from protopilot.plan.model import Dream, Edge, Finding, Plan, Source, Step, Topic

pytestmark = [pytest.mark.unit]

STAMP = render.NOT_RESEARCHED


def proposal() -> Dream:
    return Dream(
        id="d2",
        title="Lend to schools",
        what_if="schools borrowed by the term",
        lens="who else",
        anchor="members",
        takes="one teacher",
        verdict="proposed",
        reason="Doubles the audience.",
        if_adopted="Membership gains an institution tier.",
    )


def set_aside() -> Dream:
    return Dream(
        id="d3",
        title="Ten towns at once",
        what_if="every town opened on one day",
        lens="ten times bigger",
        anchor="stock",
        takes="a national sponsor",
        verdict="set-aside",
        reason="Fights the one town constraint.",
    )


def unevaluated() -> Dream:
    return Dream(
        id="d1",
        title="Lend nothing",
        what_if="the library only taught repair",
        lens="the opposite",
        anchor="stock",
        takes="a workshop",
    )


def later_proposal() -> Dream:
    return proposal().model_copy(update={"id": "d9", "title": "Lend to clubs"})


def sample(**over) -> Plan:
    fields: dict = {
        "slug": "tool_library",
        "title": "Tool library",
        "idea": "a tool library",
        "topics": [
            Topic(
                slug="members",
                title="Members",
                why="Who joins.",
                findings=[Finding(text="Most drills sit idle.", assumption=False, source_ids=["s1"])],
            ),
            Topic(slug="stock", title="Stock", why="What it lends."),
            Topic(slug="space", title="Space", why="Where it lives."),
        ],
        "edges": [
            Edge(from_topic="stock", kind="depends-on", to_topic="members"),
            Edge(from_topic="members", kind="informs", to_topic="space"),
            Edge(from_topic="space", kind="conflicts-with", to_topic="stock"),
        ],
        "steps": [Step(topic="members", action="Ask ten neighbours.", why="It needs nothing else.")],
        "dreams": [proposal(), set_aside(), unevaluated()],
        "sources": [
            Source(id="s2", title="Second", url="https://example.test/2"),
            Source(id="s1", title="First", url="https://example.test/1"),
            Source(id="s3", title="Third", url="https://example.test/3"),
        ],
    }
    return Plan(**{**fields, **over})


def section(page: str, heading: str) -> str:
    """The body under one `## heading`, up to the next one."""
    assert f"## {heading}\n" in page, f"no section {heading!r}"
    return page.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def finding_line(finding: Finding) -> str:
    topic = Topic(slug="members", title="Members", why="Who joins.", findings=[finding])
    return section(render.render(sample(topics=[topic]))["topics/members.md"], "Findings").strip()


# -- dreams ---------------------------------------------------------------


def test_each_dream_sits_only_under_the_section_of_its_verdict():
    page = render.render(sample())["dreams.md"]
    placed = {
        "Proposals": "Lend to schools",
        "Set aside": "Ten towns at once",
        "Not yet evaluated": "Lend nothing",
    }
    for heading, title in placed.items():
        body = section(page, heading)
        assert [t for t in placed.values() if t in body] == [title]


def test_sections_run_proposals_then_set_aside_then_not_yet_evaluated():
    page = render.render(sample())["dreams.md"]
    assert page.index("## Proposals") < page.index("## Set aside") < page.index("## Not yet evaluated")


def test_a_proposal_says_what_it_extends_costs_and_changes():
    page = render.render(sample())["dreams.md"]
    assert section(page, "Proposals").strip() == (
        "### Lend to schools (d2)\n\n"
        "What if schools borrowed by the term\n\n"
        "- Extends: Members\n"
        "- Lens: who else\n"
        "- Would take: one teacher\n"
        "- Verdict: proposed. Doubles the audience.\n"
        "- If adopted: Membership gains an institution tier."
    )


def test_a_set_aside_dream_keeps_its_reason():
    body = section(render.render(sample())["dreams.md"], "Set aside")
    assert "- Verdict: set-aside. Fights the one town constraint." in body
    assert "If adopted" not in body


def test_a_verdict_without_a_reason_ends_at_the_verdict():
    dream = set_aside().model_copy(update={"reason": ""})
    assert "- Verdict: set-aside\n" in render.render(sample(dreams=[dream]))["dreams.md"]


def test_an_unevaluated_dream_claims_no_verdict():
    body = section(render.render(sample())["dreams.md"], "Not yet evaluated")
    assert "### Lend nothing (d1)" in body
    assert "Verdict" not in body


def test_a_section_with_no_dreams_is_left_out():
    page = render.render(sample(dreams=[proposal()]))["dreams.md"]
    assert "## Proposals" in page
    assert "## Set aside" not in page
    assert "## Not yet evaluated" not in page


def test_a_plan_with_no_dreams_says_dreaming_has_not_run():
    page = render.render(sample(dreams=[]))["dreams.md"]
    assert "No dreams yet: dreaming has not run for this plan." in page
    assert "\n## " not in page


# -- findings and sources -------------------------------------------------


@pytest.mark.parametrize(
    "assumption, source_ids, expected",
    [
        (False, ["s1"], "- Drills sit idle. (sources: s1)"),
        (False, ["s1", "s2"], "- Drills sit idle. (sources: s1, s2)"),
        (True, ["s1"], "- **Assumption:** Drills sit idle. (sources: s1)"),
        (True, [], "- **Assumption:** Drills sit idle."),
        (False, ["ghost"], "- **Assumption:** Drills sit idle. (sources: ghost)"),
        (False, ["ghost", "s1"], "- Drills sit idle. (sources: ghost, s1)"),
        (False, ["s2", "s1"], "- Drills sit idle. (sources: s2, s1)"),
    ],
)
def test_a_finding_shows_its_label_and_its_citations(assumption, source_ids, expected):
    assert finding_line(Finding(text="Drills sit idle.", assumption=assumption, source_ids=source_ids)) == expected


def test_an_uncited_finding_is_an_assumption_even_when_flagged_otherwise():
    assert finding_line(Finding(text="Drills sit idle.", assumption=False)) == "- **Assumption:** Drills sit idle."


def test_sources_sharing_an_id_render_the_same_in_either_order():
    a = Source(id="s1", title="A", url="https://example.test/a")
    b = Source(id="s1", title="B", url="https://example.test/b")
    assert render.render(sample(sources=[a, b])) == render.render(sample(sources=[b, a]))


def test_dreams_sharing_an_id_render_the_same_in_either_order():
    a = unevaluated()
    b = a.model_copy(update={"title": "Another"})
    assert render.render(sample(dreams=[a, b])) == render.render(sample(dreams=[b, a]))


def test_sources_are_listed_with_their_links():
    page = render.render(sample())["sources.md"]
    assert "- s1: [First](https://example.test/1)\n- s2: [Second](https://example.test/2)\n" in page


def test_a_plan_with_no_sources_says_so():
    assert "No sources." in render.render(sample(sources=[]))["sources.md"]


# -- the stamp ------------------------------------------------------------


def test_a_plan_that_never_said_is_stamped_on_every_page_but_dreams():
    pages = render.render(sample())
    stamped = {name for name, text in pages.items() if STAMP in text}
    assert stamped == set(pages) - {"dreams.md"}


def test_researched_removes_the_stamp_and_changes_nothing_else():
    stamped, researched = render.render(sample()), render.render(sample(researched=True))
    assert not [name for name, text in researched.items() if "not researched" in text.lower()]
    assert researched == {name: text.replace(f"{STAMP}\n\n", "") for name, text in stamped.items()}


def test_dreams_stay_labelled_unresearched_when_the_plan_is_researched():
    page = render.render(sample(researched=True))["dreams.md"]
    assert "Nothing here is researched." in page


# -- order ----------------------------------------------------------------


def crowded(**over) -> Plan:
    """Two dreams share a section, so their order has somewhere to show."""
    return sample(**{"dreams": [later_proposal(), proposal(), set_aside(), unevaluated()], **over})


@pytest.mark.parametrize("field", ["edges", "sources", "dreams"])
@pytest.mark.parametrize("shift", [1, 2])
def test_output_ignores_the_order_of_a_field_in_plan_json(field, shift):
    original = list(getattr(crowded(), field))
    reordered = original[shift:] + original[:shift]
    assert reordered != original
    assert render.render(crowded(**{field: reordered})) == render.render(crowded())


@pytest.mark.parametrize("field", ["edges", "sources", "dreams"])
def test_reversing_a_field_in_a_saved_plan_changes_no_byte(tmp_path, field):
    crowded().save(tmp_path)
    expected = render.render(Plan.load(tmp_path))
    saved = crowded()
    getattr(saved, field).reverse()
    saved.save(tmp_path)
    assert render.render(Plan.load(tmp_path)) == expected


def test_dreams_in_one_section_read_in_id_order():
    body = section(render.render(crowded())["dreams.md"], "Proposals")
    assert body.index("(d2)") < body.index("(d9)")


def test_connections_read_in_sorted_order():
    body = section(render.render(sample())["PLAN.md"], "How the topics connect")
    assert body.strip().splitlines() == [
        "- Members informs Space",
        "- Space conflicts with Stock",
        "- Stock depends on Members",
    ]


def test_the_order_of_topics_is_the_plans_own():
    plan = sample()
    plan.topics.reverse()
    body = section(render.render(plan)["PLAN.md"], "Topic map")
    assert [line.split("]")[0] for line in body.strip().splitlines()] == ["- [Space", "- [Stock", "- [Members"]


def test_a_topic_page_lists_only_the_edges_touching_it():
    body = section(render.render(sample())["topics/members.md"], "Connections")
    assert body.strip().splitlines() == ["- Members informs Space", "- Stock depends on Members"]


# -- broken plans ---------------------------------------------------------


def test_dangling_references_render_as_their_raw_ids():
    topic = Topic(
        slug="members",
        title="Members",
        why="Who joins.",
        findings=[Finding(text="Cited.", assumption=False, source_ids=["ghost_source"])],
    )
    pages = render.render(
        sample(
            topics=[topic],
            edges=[
                Edge(from_topic="members", kind="depends-on", to_topic="ghost_topic"),
                Edge(from_topic="ghost_a", kind="informs", to_topic="ghost_b"),
            ],
            steps=[Step(topic="ghost_step", action="Act.", why="Because.")],
            dreams=[unevaluated().model_copy(update={"anchor": "ghost_anchor"})],
            sources=[],
        )
    )
    assert "- ghost_a informs ghost_b\n- Members depends on ghost_topic" in pages["PLAN.md"]
    assert "1. **ghost_step:** Act. Because." in pages["PLAN.md"]
    assert "- Members depends on ghost_topic" in pages["topics/members.md"]
    assert "- **Assumption:** Cited. (sources: ghost_source)" in pages["topics/members.md"]
    assert "- Extends: ghost_anchor" in pages["dreams.md"]


def test_a_cycle_renders_both_directions():
    edges = [
        Edge(from_topic="members", kind="depends-on", to_topic="stock"),
        Edge(from_topic="stock", kind="depends-on", to_topic="members"),
    ]
    body = section(render.render(sample(edges=edges))["PLAN.md"], "How the topics connect")
    assert body.strip().splitlines() == ["- Members depends on Stock", "- Stock depends on Members"]


def test_a_plan_with_nothing_in_it_renders_its_placeholders():
    pages = render.render(Plan(slug="bare", title="Bare", idea="bare"))
    assert set(pages) == {"PLAN.md", "dreams.md", "sources.md"}
    for heading in ("Constraints", "Open questions", "Topic map", "How the topics connect", "Where to start"):
        assert section(pages["PLAN.md"], heading).strip().startswith("None recorded.")
    assert "**Goal:** Not established." in pages["PLAN.md"]
    assert "**Direction:**" not in pages["PLAN.md"]


def test_a_direction_is_shown_when_there_is_one():
    assert "**Direction:** one town" in render.render(sample(direction="one town"))["PLAN.md"]


# -- dreams stay out of the plan ------------------------------------------


def test_no_dream_text_reaches_a_topic_page_or_the_plan_page(tmp_path):
    fields = ("title", "what_if", "lens", "takes", "reason", "if_adopted")
    dreams = [
        Dream.model_validate(
            {**{name: f"DREAM-{slug}-{name}" for name in fields}, "id": f"d-{slug}", "anchor": slug, "verdict": verdict}
        )
        for slug in ("members", "stock", "space")
        for verdict in ("proposed", "set-aside", None)
    ]
    written = render.write(sample(dreams=dreams), tmp_path)
    assert {"topics/members.md", "topics/stock.md", "topics/space.md"} <= set(written)

    pages = sorted((tmp_path / "topics").rglob("*")) + [tmp_path / "PLAN.md"]
    assert len(pages) == 4
    assert not [page.name for page in pages if "DREAM-" in page.read_text(encoding="utf-8")]
    assert "DREAM-members-what_if" in (tmp_path / "dreams.md").read_text(encoding="utf-8")


# -- the files ------------------------------------------------------------


def test_write_puts_every_rendered_page_on_disk_as_utf8(tmp_path):
    plan = sample(title="Bibliothèque d'outils 工具")
    written = render.write(plan, tmp_path)
    assert written == list(render.render(plan))
    for name, text in render.render(plan).items():
        assert (tmp_path / name).read_bytes() == text.encode("utf-8")
