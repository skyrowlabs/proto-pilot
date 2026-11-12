"""`plan.verify`: each check goes red on its planted failure, from a green baseline."""

from __future__ import annotations

import pytest

from protopilot.plan import baseline, render, verify
from protopilot.plan.model import DREAM_WORD_CAP, Dream, Edge, Finding, Plan, Source, Step

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"
WHAT_IF = "the library lent seeds as well as saws"


def source(fetched: bool = True, url: str = "https://example.com") -> Source:
    return Source(id="s1", title="A study", url=url, fetched=fetched)


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


def cited_by(slug: str) -> Plan:
    """`full()`, partly researched, with a topic research never reached citing the researched topic's source."""
    plan = full()
    borrowed = Finding(text="Borrowed.", assumption=False, source_ids=["s1"])
    topics = [t.model_copy(update={"findings": [*t.findings, borrowed]}) if t.slug == slug else t for t in plan.topics]
    return plan.revised(topics=topics)


def full() -> Plan:
    """A plan every check has a subject in, so a planted failure has a pass to turn red."""
    sourced = Finding(text="Lending works.", assumption=False, source_ids=["s1"])
    plan = with_finding(baseline.build_plan(IDEA), sourced)
    return plan.revised(researched=True, sources=[source()], dreams=[dream()], research=[fetched_record()])


def fetched_record(usable: bool = True) -> dict:
    """The ledger's record of a usable fetch of `source()`'s page, as a research run writes one."""
    fetch = {"url": "https://example.com/", "usable": usable, "why": "" if usable else "HTTP 403"}
    return {"topic": "audience", "state": "researched", "fetches": [fetch]}


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


GONE = {"slug": "gone", "title": "Gone", "why": "Ruled out."}
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
        "typed-by-the-model": lambda: full().revised(sources=[source(url="https://example.com/typed")]),
        "field-absent-from-plan-json": lambda: full().revised(
            sources=[Source(id="s1", title="A study", url="https://example.com/typed")]
        ),
        "researched-with-no-source": lambda: baseline.build_plan(IDEA).revised(researched=True),
        "fetched-typed-with-no-ledger": lambda: full().revised(research=[]),
        "ledger-fetch-was-a-403": lambda: full().revised(research=[fetched_record(usable=False)]),
        "partly-and-no-topic-is-researched": lambda: full().revised(
            research=[{**fetched_record(), "state": "nothing cited"}]
        ),
        "partly-and-an-unresearched-topic-cites": lambda: cited_by("scope"),
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
        "on-offer-from-a-dropped-topic": lambda: full().revised(dropped_topics=[GONE], dreams=[dream(anchor="gone")]),
    },
    "dreams_apart": {
        "what-if-copied": lambda: leaked(WHAT_IF),
        "copied-with-other-case-and-punctuation": lambda: leaked("The Library, lent seeds as WELL as saws!"),
        "copied-inside-a-longer-sentence": lambda: leaked(f"Imagine that {WHAT_IF}, one day."),
        "copied-with-an-html-opener": lambda: leaked("a <div> beside the door", what_if="a <div> beside the door"),
        "takes-copied": lambda: leaked("two volunteers and a borrowed van", takes="two volunteers and a borrowed van"),
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
    line = judged(full()).summary
    assert "coherent and traceable" in line and "not the same as true" in line
    assert "read through a summary of the page" in line and "never that the claim is in the source" in line


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
    text = "two volunteers and a borrowed van"
    result = judged(leaked(text, **{field: text}))
    assert result.stage == "dreams_apart"
    assert f"topics/audience.md repeats the {field} of dream d1" in result.report()


def test_text_at_the_length_is_a_leak_and_one_character_less_is_not():
    assert judged(leaked(AT_THE_LENGTH, what_if=AT_THE_LENGTH)).stage == "dreams_apart"
    assert judged(leaked(AT_THE_LENGTH[1:], what_if=AT_THE_LENGTH[1:])).ok


def test_the_length_is_measured_on_the_words_and_not_on_their_punctuation():
    padded = "* a van! -- (now) *"
    assert judged(leaked("a van now", what_if=padded)).ok


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
    plan = full().revised(sources=[source(url="https://example.com/never")])
    assert judged(plan).named(verify.FAILED) == ["sources_fetched"]


def test_a_hand_typed_fetched_flag_is_named_as_such():
    said = judged(full().revised(research=[])).report()
    assert "has no usable fetch in this run's ledger, though plan.json marks it fetched" in said


def test_the_ledger_not_the_flag_is_the_evidence():
    assert judged(full().revised(sources=[source(fetched=False)])).ok


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


# -- dreams_apart: what a topic says, not what its page draws --------------


def furniture_dream(field: str, text: str) -> Plan:
    return full().revised(dreams=[dream(**{field: text})])


@pytest.mark.parametrize(
    ("field", "text"),
    [
        ("title", "Start a community tool library"),
        ("reason", "every finding is an assumption"),
        ("takes", "Decisions to make"),
        ("title", "The cheapest way to learn"),
        ("reason", "Rendered from .protopilot/plan.json"),
        ("takes", "What is in and what is out depends on Who it is for"),
    ],
    ids=["plan-title", "stamp", "heading", "topic-title", "header", "connection"],
)
def test_page_furniture_is_not_a_leak(field, text):
    assert states(judged(furniture_dream(field, text)))["dreams_apart"] != verify.FAILED


def test_the_idea_quoted_in_a_topic_is_not_a_dream_repeated_there():
    plan = baseline.build_plan(IDEA).revised(dreams=[dream(reason=IDEA)])
    assert IDEA in render.render(plan)["topics/audience.md"]
    assert states(judged(plan))["dreams_apart"] != verify.FAILED


def test_the_stamp_is_furniture_on_a_page_that_failed_verification_too():
    plan = furniture_dream("reason", "This plan failed its checks")
    pages = render.render(plan, runbook="x")
    assert "failed its checks" in pages["topics/audience.md"]
    assert states(judged(plan, pages))["dreams_apart"] != verify.FAILED


def test_a_dream_matches_whole_words_and_never_the_middle_of_one():
    assert judged(leaked("the library lent seeds as well", what_if="he library lent seeds")).ok


def test_furniture_is_only_what_the_page_draws_itself():
    plan = full()
    pages = render.render(plan)
    pages["topics/audience.md"] += f"\nDecisions to make {WHAT_IF}\n"
    assert judged(plan, pages).stage == "dreams_apart"


# -- dreams_apart: a copy dressed up --------------------------------------


@pytest.mark.parametrize(
    "copy",
    [
        "the library lent _seeds_ as well as saws",
        "THE LIBRARY LENT SEEDS, AS WELL AS SAWS!",
        "the library lent free seeds as well as saws",
        "the library lent seeds as well as tools",
        "the library lent seeds as well saws",
    ],
    ids=["underscores", "case-and-punctuation", "one-word-inserted", "one-word-changed", "one-word-missing"],
)
def test_a_copy_with_a_word_or_its_dressing_changed_is_still_a_copy(copy):
    assert judged(leaked(copy)).stage == "dreams_apart"


def test_decomposed_accents_cannot_hide_a_copy():
    composed = "le caf\u00e9 pr\u00eate des graines et des scies"
    decomposed = "le cafe\u0301 pre\u0302te des graines et des scies"
    assert judged(leaked(decomposed, what_if=composed)).stage == "dreams_apart"


def test_a_short_sentence_in_a_script_without_spaces_is_long_enough_to_compare():
    sentence = "\u56f3\u66f8\u9928\u306f\u7a2e\u3082\u30ce\u30b3\u30ae\u30ea\u3082\u8cb8\u305b\u308b"
    assert len(sentence) == 14
    assert judged(leaked(f"\u524d{sentence}\u5f8c", what_if=sentence)).stage == "dreams_apart"


def test_a_short_text_changed_by_one_word_is_not_called_a_copy():
    assert judged(leaked("seed swap and shelf", what_if="seed swap shelf night")).ok


def test_a_paraphrase_passes_and_that_is_the_stated_limit():
    assert judged(leaked("saws and seeds can both be borrowed from the library")).ok


# -- dreams_apart and dreams_shaped: what a person settled -----------------


def test_a_promoted_dream_is_no_longer_compared():
    plan = leaked(WHAT_IF, verdict="promoted", promoted_to="audience")
    assert states(judged(plan))["dreams_apart"] != verify.FAILED


def test_a_dropped_dream_is_compared_except_for_the_persons_reason():
    assert judged(leaked(WHAT_IF, verdict="dropped")).stage == "dreams_apart"
    assert judged(
        leaked("the first version is far too large", verdict="dropped", reason="the first version is far too large")
    ).ok


def test_a_takes_under_six_words_is_an_ordinary_phrase_and_that_is_the_stated_limit():
    five, six = "a part time coordinator here", "a part time coordinator here please"
    assert judged(leaked(five, takes=five)).ok
    assert judged(leaked(six, takes=six)).stage == "dreams_apart"


def test_a_promoted_dream_must_name_a_topic_the_plan_holds():
    assert judged(full().revised(dreams=[dream(verdict="promoted", promoted_to="ghost")])).stage == "dreams_shaped"
    assert judged(full().revised(dreams=[dream(verdict="promoted")])).stage == "dreams_shaped"


def test_only_a_promoted_dream_may_name_a_topic():
    assert judged(full().revised(dreams=[dream(promoted_to="audience")])).stage == "dreams_shaped"


def test_a_repeated_dream_id_is_red_because_promote_could_not_tell_them_apart():
    result = judged(full().revised(dreams=[dream(), dream(title="Other")]))
    assert result.stage == "dreams_shaped" and "more than one dream has the id d1" in result.report()


def test_a_joined_up_dream_cannot_hide_from_the_cap():
    assert judged(full().revised(dreams=[dream(takes=OVER_CAP.replace(" ", "-"))])).stage == "dreams_shaped"


def test_the_green_line_says_dreams_are_not_findings_only_when_a_dream_check_held():
    assert "Dreams are guesses" in judged(full()).summary
    assert "Dreams are guesses" not in judged(full().revised(dreams=[])).summary


@pytest.mark.parametrize("verdict", verify.SETTLED_VERDICTS)
def test_a_dream_no_longer_on_offer_may_keep_the_anchor_of_a_dropped_topic(verdict):
    promoted_to = "scope" if verdict == "promoted" else ""
    kept = dream(anchor="gone", verdict=verdict, promoted_to=promoted_to)
    result = judged(full().revised(dropped_topics=[GONE], dreams=[kept]))
    assert states(result)["dreams_shaped"] == verify.PASSED


def test_a_dropped_slug_a_live_topic_holds_again_is_an_anchor_like_any_other():
    back = {"slug": "audience", "title": "Who it is for", "why": "Ruled out."}
    assert states(judged(full().revised(dropped_topics=[back])))["dreams_shaped"] == verify.PASSED
