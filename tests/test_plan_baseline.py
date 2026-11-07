"""`plan.baseline`: the offline twin claims nothing, and its graph is usable."""

from __future__ import annotations

from graphlib import TopologicalSorter

import pytest

from protopilot.plan import baseline, render
from protopilot.plan.model import Plan
from protopilot.spec import SLUG_RE

pytestmark = [pytest.mark.unit]

IDEAS = [
    "start a community tool library",
    "3d print replacement parts",
    "the a an",
    "日本語のアイデア",
    'odd {braces} {0} {idea} "quotes" 100%',
]


def depends_on(plan: Plan) -> dict[str, set[str]]:
    needs: dict[str, set[str]] = {t.slug: set() for t in plan.topics}
    for edge in plan.edges:
        if edge.kind == "depends-on":
            needs[edge.from_topic].add(edge.to_topic)
    return needs


# -- slug_for -------------------------------------------------------------


@pytest.mark.parametrize(
    "idea, slug",
    [
        ("3d printing", "plan_3d_printing"),
        ("2024", "plan_2024"),
        ("1", "plan_1"),
        ("the 3 bears", "plan_3_bears"),
        ("printing in 3d", "printing_in_3d"),
    ],
)
def test_an_idea_opening_on_a_digit_gets_a_slug_opening_on_a_letter(idea, slug):
    assert baseline.slug_for(idea) == slug


@pytest.mark.parametrize("idea", ["", "   ", "the", "a an and", "Build A For The", "!!! ???"])
def test_an_idea_with_no_naming_word_falls_back(idea):
    assert baseline.slug_for(idea) == baseline.FALLBACK_SLUG


@pytest.mark.parametrize("idea", ["日本語", "Привет мир", "🎸🎸", "مرحبا"])
def test_an_idea_with_no_ascii_word_falls_back(idea):
    assert baseline.slug_for(idea) == baseline.FALLBACK_SLUG


def test_ascii_words_survive_beside_non_ascii_ones():
    assert baseline.slug_for("日本語 tool library") == "tool_library"


@pytest.mark.parametrize("idea", ["café au lait", "Ünïcode tools", "İstanbul market", "ﬁsh shop", "Straße", "_private"])
def test_accented_letters_still_give_a_valid_slug(idea):
    slug = baseline.slug_for(idea)
    assert SLUG_RE.fullmatch(slug), slug
    assert baseline.build_plan(idea).slug == slug


def test_filler_is_dropped_before_the_word_limit_is_counted():
    assert baseline.slug_for("start a very small but useful tool") == "very_small_but_useful"


def test_case_and_punctuation_do_not_change_the_slug():
    assert baseline.slug_for("Tools, Tools & MORE!") == baseline.slug_for("tools tools more") == "tools_tools_more"


# -- what the baseline claims ---------------------------------------------


@pytest.mark.parametrize("idea", IDEAS)
def test_the_baseline_cites_nothing_and_says_it_was_not_researched(idea):
    plan = baseline.build_plan(idea)
    assert plan.sources == []
    assert plan.researched is False
    findings = [f for t in plan.topics for f in t.findings]
    assert len(findings) == 2 * len(baseline.TOPICS)
    assert {(f.assumption, tuple(f.source_ids)) for f in findings} == {(True, ())}


def test_every_rendered_baseline_finding_reads_as_an_assumption():
    pages = render.render(baseline.build_plan(IDEAS[0]))
    topic_pages = [text for name, text in pages.items() if name.startswith("topics/")]
    assert len(topic_pages) == len(baseline.TOPICS)
    for page in topic_pages:
        findings = page.split("## Findings\n\n")[1].split("\n\n")[0].splitlines()
        assert len(findings) == 2
        assert all(line.startswith("- **Assumption:** ") for line in findings)
    assert "No sources." in pages["sources.md"]


# -- its graph ------------------------------------------------------------


@pytest.mark.parametrize("idea", IDEAS)
def test_depends_on_has_no_cycle(idea):
    needs = depends_on(baseline.build_plan(idea))
    assert set(TopologicalSorter(needs).static_order()) == set(needs)


def test_every_edge_and_step_names_a_topic_that_exists():
    plan = baseline.build_plan(IDEAS[0])
    slugs = {t.slug for t in plan.topics}
    assert {e.from_topic for e in plan.edges} | {e.to_topic for e in plan.edges} <= slugs
    assert {s.topic for s in plan.steps} <= slugs


def test_the_first_step_has_no_unmet_dependency():
    plan = baseline.build_plan(IDEAS[0])
    assert depends_on(plan)[plan.steps[0].topic] == set()


def test_each_step_depends_only_on_the_steps_before_it():
    plan = baseline.build_plan(IDEAS[0])
    needs = depends_on(plan)
    done: set[str] = set()
    for step in plan.steps:
        assert needs[step.topic] <= done, step.topic
        done.add(step.topic)


# -- the idea's words -----------------------------------------------------


def test_one_idea_has_one_spelling_however_it_was_typed():
    assert baseline.build_plan("  a   tool\n\tlibrary ") == baseline.build_plan("a tool library")


def test_the_idea_is_quoted_literally_even_when_it_looks_like_a_format_string():
    idea = "use {braces} and {0}"
    assert f'"{idea}"' in baseline.build_plan(idea).topics[0].why


def test_a_direction_becomes_the_one_constraint():
    plan = baseline.build_plan("a tool library", "  one   town ")
    assert (plan.direction, plan.constraints) == ("one town", ["one town"])


def test_no_direction_means_no_constraints():
    assert baseline.build_plan("a tool library").constraints == []


def test_the_title_capitalises_the_first_letter_and_nothing_else():
    assert baseline.build_plan("a Tool library").title == "A Tool library"
