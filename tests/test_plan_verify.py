"""`plan.verify`: each check goes red on its planted failure, from a green baseline."""

from __future__ import annotations

import pytest

from protopilot.plan import baseline, render, verify
from protopilot.plan.model import DREAM_WORD_CAP, Dream, Edge, Finding, Plan, Source, Step

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"
WHAT_IF = "the library lent seeds as well as saws"


def source(fetched: bool = True) -> Source:
    return Source(id="s1", title="A study", url="https://example.com", fetched=fetched)


def dream(**changes: object) -> Dream:
    fields = {
        "id": "d1",
        "title": "Seeds",
        "what_if": WHAT_IF,
        "lens": "who else",
        "anchor": "audience",
        "takes": "A shelf",
        "verdict": "proposed",
    }
    return Dream.model_validate({**fields, **changes})


def with_finding(plan: Plan, finding: Finding) -> Plan:
    first = plan.topics[0].model_copy(update={"findings": [*plan.topics[0].findings, finding]})
    return plan.revised(topics=[first, *plan.topics[1:]])


def full() -> Plan:
    """A plan every check has a subject in, so a planted failure has a pass to turn red."""
    sourced = Finding(text="Lending works.", assumption=False, source_ids=["s1"])
    plan = with_finding(baseline.build_plan(IDEA), sourced)
    return plan.revised(researched=True, sources=[source()], dreams=[dream()])


def judged(plan: Plan, pages: dict[str, str] | None = None) -> verify.PlanVerdict:
    return verify.verdict(plan, render.render(plan) if pages is None else pages)


def states(result: verify.PlanVerdict) -> dict[str, str]:
    return {check.name: check.state for check in result.checks}


def edges(*extra: tuple[str, str, str]) -> Plan:
    plan = full()
    return plan.revised(edges=[*plan.edges, *(Edge(from_topic=a, kind=k, to_topic=b) for a, k, b in extra)])  # type: ignore[arg-type]


def steps(*topics: str) -> Plan:
    return full().revised(steps=[Step(topic=t, action="Do it.", why="Now.") for t in topics])


def without(name: str) -> tuple[Plan, dict[str, str]]:
    plan = full()
    pages = render.render(plan)
    del pages[name]
    return plan, pages


def unlinked() -> tuple[Plan, dict[str, str]]:
    plan = full()
    pages = render.render(plan)
    pages["PLAN.md"] = pages["PLAN.md"].replace("(topics/scope.md)", "")
    return plan, pages


def leaked(text: str, **dream_changes: object) -> Plan:
    plan = full().revised(dreams=[dream(**dream_changes)])
    first = plan.topics[0].model_copy(update={"risks": [text]})
    return plan.revised(topics=[first, *plan.topics[1:]])


OVER_CAP = " ".join(["word"] * (DREAM_WORD_CAP + 1))

PLANTS = {
    "topic_map": {
        "topic-page-lost": lambda: without("topics/scope.md"),
        "sources-page-lost": lambda: without("sources.md"),
        "topic-not-in-the-map": unlinked,
        "edge-to-a-ghost": lambda: edges(("scope", "informs", "ghost")),
        "edge-from-a-ghost": lambda: edges(("ghost", "informs", "scope")),
    },
    "no_cycles": {
        "two-topics": lambda: edges(("risks", "depends-on", "operations"), ("operations", "depends-on", "risks")),
        "itself": lambda: edges(("risks", "depends-on", "risks")),
    },
    "findings_traced": {
        "no-source-no-label": lambda: with_finding(full(), Finding(text="It is so.", assumption=False)),
        "cites-a-ghost": lambda: with_finding(full(), Finding(text="So.", assumption=False, source_ids=["s9"])),
        "one-real-one-ghost": lambda: with_finding(
            full(), Finding(text="So.", assumption=False, source_ids=["s1", "s9"])
        ),
        "assumption-citing-a-ghost": lambda: with_finding(
            full(), Finding(text="So.", assumption=True, source_ids=["s9"])
        ),
    },
    "sources_fetched": {
        "typed-by-the-model": lambda: full().revised(sources=[source(fetched=False)]),
        "field-absent-from-plan-json": lambda: full().revised(
            sources=[Source(id="s1", title="A study", url="https://example.com")]
        ),
        "researched-with-no-source": lambda: baseline.build_plan(IDEA).revised(researched=True),
    },
    "start_order": {
        "first-step-waits": lambda: steps("scope", "audience"),
        "later-step-jumps": lambda: steps("audience", "resources"),
        "repeated": lambda: steps("audience", "audience"),
        "ghost-topic": lambda: steps("ghost"),
        "no-steps": lambda: steps(),
    },
    "dreams_shaped": {
        "ghost-anchor": lambda: full().revised(dreams=[dream(anchor="ghost")]),
        "no-verdict": lambda: full().revised(dreams=[dream(verdict=None)]),
        "over-the-cap": lambda: full().revised(dreams=[dream(takes=OVER_CAP)]),
    },
    "dreams_apart": {
        "what-if-copied": lambda: leaked(WHAT_IF),
        "copied-with-other-case-and-punctuation": lambda: leaked("The Library, lent seeds as WELL as saws!"),
        "copied-inside-a-longer-sentence": lambda: leaked(f"Imagine that {WHAT_IF}, one day."),
        "copied-with-an-html-opener": lambda: leaked("a <div> beside the door", what_if="a <div> beside the door"),
        "takes-copied": lambda: leaked("two volunteers and a van", takes="two volunteers and a van"),
    },
}

CASES = [
    pytest.param(check, plant, id=f"{check}-{name}")
    for check, plants in PLANTS.items()
    for name, plant in plants.items()
]


def test_every_check_has_a_planted_failure():
    assert set(PLANTS) == {check.__name__ for check in verify.CHECKS}


def test_the_green_baseline_passes_every_check_with_a_subject():
    result = judged(full())
    assert result.ok
    assert set(states(result).values()) == {verify.PASSED}


@pytest.mark.parametrize(("check", "plant"), CASES)
def test_a_planted_failure_turns_its_check_red(check, plant):
    planted = plant()
    result = judged(*planted) if isinstance(planted, tuple) else judged(planted)
    assert not result.ok
    assert result.stage == check
    assert states(result)[check] == verify.FAILED
    assert result.summary.endswith((".", ".)"))


def test_a_red_verdict_keeps_every_failing_check_not_only_the_first():
    plan = edges(("risks", "depends-on", "risks")).revised(dreams=[dream(verdict=None)])
    result = judged(plan)
    assert result.named(verify.FAILED) == ["no_cycles", "dreams_shaped"]
    assert "[no_cycles]" in result.report() and "[dreams_shaped]" in result.report()


@pytest.mark.parametrize(
    ("plan", "problem"),
    [
        (steps("scope", "audience"), "step 1 (scope) waits on audience, which no earlier step covers"),
        (steps("audience", "resources"), "step 2 (resources) waits on scope, which no earlier step covers"),
    ],
    ids=["first", "later"],
)
def test_a_step_fault_names_the_step_and_what_it_waits_on(plan, problem):
    assert problem in judged(plan).report()


def test_a_cycle_names_only_the_links_on_the_loop():
    plan = edges(("risks", "depends-on", "operations"), ("operations", "depends-on", "risks"))
    looped = {(e.from_topic, e.to_topic) for e in verify.cycle_edges(plan)}
    assert looped == {("risks", "operations"), ("operations", "risks")}


def test_an_edge_that_only_leads_to_a_loop_is_not_on_it():
    plan = edges(("risks", "depends-on", "first_test"), ("first_test", "depends-on", "risks"))
    looped = {(e.from_topic, e.to_topic) for e in verify.cycle_edges(plan)}
    assert ("first_test", "audience") not in looped


def test_informs_and_conflicts_cannot_make_a_cycle():
    plan = edges(("risks", "informs", "first_test"), ("audience", "conflicts-with", "audience"))
    assert verify.cycle_edges(plan) == []


def test_an_assumption_with_no_source_is_traced():
    assert judged(with_finding(full(), Finding(text="Maybe.", assumption=True))).ok


def test_a_short_dream_title_shared_with_a_topic_is_not_a_leak():
    assert judged(leaked("Seeds grow.", title="Seeds")).ok


def test_a_dream_at_the_cap_fits():
    at_cap = " ".join(["word"] * (DREAM_WORD_CAP - 2 - len(WHAT_IF.split())))
    assert judged(full().revised(dreams=[dream(title="Seeds now", takes=at_cap)])).ok


# -- no subject -----------------------------------------------------------


def test_a_check_with_no_subject_says_so_and_is_not_a_pass():
    plan = baseline.build_plan(IDEA).revised(edges=[])
    plan = plan.revised(topics=[t.model_copy(update={"findings": []}) for t in plan.topics])
    result = judged(plan)
    assert result.ok
    expected = ["no_cycles", "findings_traced", "sources_fetched", "dreams_shaped", "dreams_apart"]
    assert result.named(verify.NO_SUBJECT) == expected
    assert result.named(verify.PASSED) == ["topic_map", "start_order"]


def test_no_steps_is_red_and_never_merely_no_subject():
    assert states(judged(steps()))["start_order"] == verify.FAILED


def test_a_plan_with_no_topics_has_nothing_mapped_and_is_still_red():
    plan = baseline.build_plan(IDEA).revised(topics=[], edges=[], steps=[])
    assert states(judged(plan))["topic_map"] == verify.NO_SUBJECT
    assert not judged(plan).ok


# -- the green line -------------------------------------------------------


def test_the_green_line_states_the_limit_in_words():
    line = judged(baseline.build_plan(IDEA)).summary
    assert "coherent and traceable" in line and "not the same as true" in line
    assert "a summary of it was read, not that a claim is in the original" in line


def test_the_green_line_keeps_what_held_apart_from_what_had_no_subject():
    line = judged(baseline.build_plan(IDEA)).summary
    held = line.split("Held: ")[1].split(".")[0]
    empty = line.split("proved nothing: ")[1].split(".")[0]
    assert held == "topic_map, no_cycles, findings_traced, start_order"
    assert empty == "sources_fetched, dreams_shaped, dreams_apart"


def test_a_plan_where_every_check_had_a_subject_claims_no_empty_check():
    assert "No subject" not in judged(full()).summary


# -- pages on disk --------------------------------------------------------


def test_the_pages_on_disk_read_back_as_drawn(tmp_path):
    plan = full()
    render.write(plan, tmp_path)
    assert render.read(tmp_path) == render.render(plan)


def test_a_page_deleted_from_disk_is_red_when_read_back(tmp_path):
    plan = full()
    render.write(plan, tmp_path)
    (tmp_path / "topics" / "scope.md").unlink()
    assert judged(plan, render.read(tmp_path)).stage == "topic_map"


def test_dream_text_written_into_a_topic_page_is_red_when_read_back(tmp_path):
    plan = full()
    render.write(plan, tmp_path)
    page = tmp_path / "topics" / "scope.md"
    page.write_text(page.read_text() + f"\n{WHAT_IF}\n")
    assert judged(plan, render.read(tmp_path)).stage == "dreams_apart"


def test_a_runbook_lists_what_is_wrong_what_was_tried_and_what_had_no_subject():
    plan = edges(("risks", "depends-on", "risks")).revised(dreams=[], sources=[], researched=False)
    plan = plan.revised(topics=[t.model_copy(update={"findings": []}) for t in plan.topics])
    text = verify.runbook(judged(plan), 4, ["attempt 1 (no_cycles): nothing changed"])
    assert "[no_cycles]" in text and "risks depends on risks" in text
    assert "1. attempt 1 (no_cycles): nothing changed" in text
    assert "- sources_fetched: The plan has no sources to check." in text
    assert "Nothing here is verified" in text


# -- dreams_apart: what counts as a copy ----------------------------------

AT_THE_LENGTH = "a" * 16


@pytest.mark.parametrize("field", ["title", "what_if", "takes", "reason", "if_adopted"])
def test_every_field_a_dream_writes_is_compared(field):
    text = "two volunteers and a van"
    result = judged(leaked(text, **{field: text}))
    assert result.stage == "dreams_apart"
    assert f"topics/audience.md repeats the {field} of dream d1" in result.report()


def test_text_at_the_length_is_a_leak_and_one_character_less_is_not():
    assert judged(leaked(AT_THE_LENGTH, takes=AT_THE_LENGTH)).stage == "dreams_apart"
    assert judged(leaked(AT_THE_LENGTH[1:], takes=AT_THE_LENGTH[1:])).ok


def test_the_length_is_measured_on_the_words_and_not_on_their_punctuation():
    padded = "* a van! -- (now) *"
    assert judged(leaked("a van now", takes=padded)).ok


@pytest.mark.parametrize(
    "risk",
    [
        "Volunteers may not turn up on the day.",
        "The library may lend saws that are unsafe.",
        "Seeds and saws need different shelves.",
        "lent seeds as well",
    ],
    ids=["unrelated", "shares-words", "shares-the-nouns", "a-fragment-of-the-dream"],
)
def test_ordinary_plan_text_near_a_dream_is_not_a_leak(risk):
    assert judged(leaked(risk)).ok


def test_a_dream_repeated_on_its_own_page_and_the_entry_page_is_not_a_leak():
    plan = full().revised(constraints=[WHAT_IF])
    pages = render.render(plan)
    assert WHAT_IF in pages["dreams.md"] and WHAT_IF in pages["PLAN.md"]
    assert judged(plan).ok


def test_each_page_a_dream_leaks_into_is_named():
    plan = full()
    tops = [t.model_copy(update={"risks": [WHAT_IF]}) for t in plan.topics[:2]]
    result = judged(plan.revised(topics=[*tops, *plan.topics[2:]]))
    assert {problem.split()[0] for problem in result.failed[0].problems} == {f"topics/{t.slug}.md" for t in tops}


# -- what the checks do not say -------------------------------------------


def test_a_step_with_a_fault_is_reported_once_and_covers_what_follows():
    plan = steps("scope", "audience", "resources")
    assert [fault.topic for fault in verify.step_faults(plan)] == ["scope"]


def test_a_step_waiting_on_a_ghost_is_red_at_both_checks_that_can_see_it():
    plan = edges(("audience", "depends-on", "ghost"))
    result = judged(plan)
    assert result.named(verify.FAILED) == ["topic_map", "start_order"]
    assert "step 1 (audience) waits on ghost" in result.report()


def test_an_edge_from_a_ghost_cannot_make_a_real_step_wait():
    assert verify.step_faults(edges(("ghost", "depends-on", "audience"))) == []


def test_a_finding_citing_a_source_the_plan_holds_but_never_fetched_is_red_at_the_source():
    plan = full().revised(sources=[source(fetched=False)])
    assert judged(plan).named(verify.FAILED) == ["sources_fetched"]


def test_the_green_line_is_absent_from_a_red_verdict():
    result = judged(steps("scope", "audience"))
    assert not result.ok and "Green" not in result.summary and "Green" not in result.report()


def test_a_loop_of_three_names_all_three_links_and_nothing_else():
    plan = edges(
        ("risks", "depends-on", "operations"),
        ("operations", "depends-on", "first_test"),
        ("first_test", "depends-on", "risks"),
    )
    looped = {(e.from_topic, e.to_topic) for e in verify.cycle_edges(plan)}
    on_the_ring = {("risks", "operations"), ("operations", "first_test"), ("first_test", "risks")}
    assert on_the_ring <= looped
    assert all(a in {"risks", "operations", "first_test"} for a, _ in looped)
