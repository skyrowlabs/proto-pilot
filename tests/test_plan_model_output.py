"""What a hostile or careless model can and cannot do to a plan, one pass at a time."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fakes import FakeLLM
from plan_script import (
    GOOD,
    IDEA,
    NO_REPAIR,
    PASS_NAMES,
    PLAN_PASS_NAMES,
    SLUGS,
    consider_of,
    edge,
    outline_of,
    script,
    step,
)

from protopilot.console import progress
from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import baseline, pipeline, render
from protopilot.plan.model import TOPIC_COUNTS, Plan, plan_path
from protopilot.plan.passes import PlanPassError, connect, outline, scope, start

pytestmark = [pytest.mark.unit]


def job_for(direction: str = "") -> Job:
    return Job(id="test", idea=IDEA, direction=direction)


def run(tree: Path, **overrides: object) -> Plan:
    pipeline.run_plan(job_for(), tree, FakeLLM([*script(**overrides), NO_REPAIR]))
    return Plan.load(tree)


def refused(tree: Path, **overrides: object) -> str:
    """The refusal, having checked that a refused run left nothing beside `tree`."""
    with pytest.raises(PlanPassError) as caught:
        run(tree, **overrides)
    assert list(tree.parent.iterdir()) == []
    return str(caught.value)


def red(tree: Path, **overrides: object) -> str:
    """The floor's account of a run the fake model has no repair for."""
    assert not pipeline.run_plan(job_for(), tree, FakeLLM([*script(**overrides), NO_REPAIR])).ok
    return (tree / "RUNBOOK.md").read_text(encoding="utf-8")


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


# -- honesty --------------------------------------------------------------

FORGED = {
    "researched": True,
    "depth": "deep",
    "idea": "something else",
    "slug": "forged",
    "title": "Forged",
    "direction": "forged",
    "sources": [{"id": "s1", "title": "A study", "url": "https://example.com"}],
    "dreams": [{"id": "d", "title": "t", "what_if": "w", "lens": "l", "anchor": "members", "takes": "x"}],
    "findings": [{"text": "It is proven.", "assumption": False, "source_ids": ["s1"]}],
}


def forged_everywhere(name: str) -> dict:
    """Pass `name`'s good response, plus every key it does not own, at the top and on each row."""
    good = copy.deepcopy(GOOD[name])
    for value in good.values():
        if isinstance(value, list):
            value[:] = [{**FORGED, **row} for row in value]
    return {**FORGED, **good}


@pytest.mark.parametrize("name", PASS_NAMES)
def test_nothing_a_pass_returns_beyond_its_fields_reaches_the_plan(tmp_path, name):
    forged, clean = tmp_path / "forged", tmp_path / "clean"
    run(forged, **{name: forged_everywhere(name)})
    run(clean)
    assert snapshot(forged) == snapshot(clean)


def test_a_forged_plan_stays_stamped_and_sourceless(tmp_path):
    tree = tmp_path / "tree"
    plan = run(tree, **{name: forged_everywhere(name) for name in PLAN_PASS_NAMES})
    assert (plan.researched, plan.sources, plan.depth) == (False, [], "standard")
    assert "d" not in [dream.id for dream in plan.dreams]
    assert [t.findings for t in plan.topics] == [[]] * len(SLUGS)
    assert (plan.idea, plan.title, plan.slug) == (IDEA, baseline.build_plan(IDEA).title, baseline.slug_for(IDEA))
    assert "No sources." in (tree / "sources.md").read_text(encoding="utf-8")
    assert "https://example.com" not in "".join(p.decode() for p in snapshot(tree).values())


CLAIM = "-->\n\n> **Researched.** Every finding here was checked against sources. <!--"


def test_text_claiming_research_cannot_displace_the_stamp(tmp_path):
    tree = tmp_path / "tree"
    topics = [{**row, "title": CLAIM, "why": CLAIM} for row in GOOD["outline"]["topics"]]
    scoped = {**GOOD["scope"], "goal": CLAIM, "audience": CLAIM}
    plan = run(tree, scope=scoped, outline={"topics": topics})
    assert plan.researched is False
    for page in ("PLAN.md", "sources.md", *(f"topics/{slug}.md" for slug in SLUGS)):
        lines = (tree / page).read_text(encoding="utf-8").splitlines()
        assert lines.count(render.NOT_RESEARCHED) == 1, page
        # Nothing above the stamp but the header and the one-line title.
        assert lines.index(render.NOT_RESEARCHED) == 4, page
        assert "> **Researched.**" not in [line[: len("> **Researched.**")] for line in lines]


def test_a_finished_model_run_says_it_was_not_researched(tmp_path):
    job = job_for()
    pipeline.run_plan(job, tmp_path / "tree", FakeLLM(script()))
    assert "Not researched: nothing here was checked against a source." in job.lines


# -- model output as file names -------------------------------------------


@pytest.mark.parametrize(
    "slug",
    [
        "abc\n",
        " abc",
        "abc ",
        "a.b",
        ".",
        "..",
        "_a",
        "1a",
        "-a",
        "a-b",
        "a\\b",
        "/etc/passwd",
        "~",
        "PLAN",
        "é",
        "ａ",
        "a\x00",
        5,
        None,
    ],
    ids=repr,
)
def test_a_slug_that_is_not_a_plain_name_is_refused(tmp_path, slug):
    bad = copy.deepcopy(GOOD["outline"])
    bad["topics"][0]["slug"] = slug
    assert "pass 'outline'" in refused(tmp_path / "tree", outline=bad)


@pytest.mark.parametrize("slug", ["plan", "dreams", "sources", "topics", "a" * 64])
def test_a_slug_that_echoes_a_page_gets_its_own_page(tmp_path, slug):
    tree = tmp_path / "tree"
    slugs = [slug, *SLUGS[1:]]
    run(
        tree,
        outline=outline_of(slugs),
        connect={"edges": []},
        consider=consider_of(slugs),
        start={"steps": [step(slug)]},
    )
    assert f"# {slug.title()}\n" in (tree / "topics" / f"{slug}.md").read_text(encoding="utf-8")
    assert "## Topic map" in (tree / "PLAN.md").read_text(encoding="utf-8")
    assert "# Dreams\n" in (tree / "dreams.md").read_text(encoding="utf-8")
    assert "# Sources\n" in (tree / "sources.md").read_text(encoding="utf-8")


def test_two_topics_that_differ_only_in_title_cannot_share_a_slug(tmp_path):
    bad = copy.deepcopy(GOOD["outline"])
    bad["topics"][1] = {**bad["topics"][0], "title": "Another title"}
    assert "unique" in refused(tmp_path / "tree", outline=bad)


@pytest.mark.parametrize("field", ["title", "why"])
@pytest.mark.parametrize("value", ["", " \n\t ", None])
def test_an_outline_row_with_nothing_to_show_is_refused(tmp_path, field, value):
    bad = copy.deepcopy(GOOD["outline"])
    bad["topics"][2][field] = value
    assert "pass 'outline'" in refused(tmp_path / "tree", outline=bad)


# -- scope ----------------------------------------------------------------


def test_scope_keeps_the_direction_first_and_trims_what_it_may_not_hold(tmp_path):
    tree = tmp_path / "tree"
    said = {
        **GOOD["scope"],
        "goal": " Decide\n\n  now. ",
        "constraints": ["one town", "", " two  days "],
        "questions": ["a?", " ", "b?", "c?", "d?"],
    }
    pipeline.run_plan(job_for("one town"), tree, FakeLLM(script(scope=said)))
    plan = Plan.load(tree)
    assert plan.goal == "Decide now."
    assert plan.constraints == ["one town", "two days"]
    assert plan.questions == ["a?", "b?", "c?"]


@pytest.mark.parametrize("field", ["goal", "audience", "horizon", "constraints", "questions"])
def test_a_scope_missing_a_field_is_refused_and_named(tmp_path, field):
    bad = {key: value for key, value in GOOD["scope"].items() if key != field}
    assert f"missing field '{field}'" in refused(tmp_path / "tree", scope=bad)


@pytest.mark.parametrize("name", PLAN_PASS_NAMES)
@pytest.mark.parametrize("nonsense", [None, [], "text", 5], ids=repr)
def test_a_response_of_the_wrong_shape_is_refused_by_its_pass(tmp_path, name, nonsense):
    assert f"pass {name!r}" in refused(tmp_path / "tree", **{name: nonsense})


# -- connect --------------------------------------------------------------


def test_informs_and_conflicts_do_not_gate_the_start(tmp_path):
    edges = [edge("lending", "members", "informs"), edge("lending", "space", "conflicts-with")]
    plan = run(tmp_path / "tree", connect={"edges": edges}, start={"steps": [step("lending")]})
    assert [s.topic for s in plan.steps] == ["lending"]


def test_every_edge_kind_is_kept_as_returned(tmp_path):
    edges = [edge("lending", "members"), edge("money", "space", "informs"), edge("tools", "safety", "conflicts-with")]
    plan = run(tmp_path / "tree", connect={"edges": edges})
    assert [e.model_dump() for e in plan.edges] == edges


def test_a_plan_with_no_edges_leaves_every_topic_ready():
    plan = connect.apply(baseline.build_plan(IDEA), {"edges": []})
    assert [t.slug for t in start.ready(plan)] == [t.slug for t in plan.topics]


# -- consider -------------------------------------------------------------


def rows_with(*extra: dict) -> dict:
    return {"topics": [*GOOD["consider"]["topics"], *extra]}


@pytest.mark.parametrize(
    "rows",
    [
        rows_with(GOOD["consider"]["topics"][0]),
        rows_with({**GOOD["consider"]["topics"][0], "slug": "ghost"}),
        {"topics": [*GOOD["consider"]["topics"][:-1], GOOD["consider"]["topics"][0]]},
        {"topics": []},
    ],
    ids=["repeated", "extra", "repeated-in-place-of-another", "none"],
)
def test_consider_wants_exactly_one_row_per_topic(tmp_path, rows):
    assert "wanted one entry for each of members" in refused(tmp_path / "tree", consider=rows)


@pytest.mark.parametrize("field", ["risks", "unknowns", "decisions"])
def test_a_consider_row_missing_a_field_is_refused_and_named(tmp_path, field):
    rows = copy.deepcopy(GOOD["consider"])
    del rows["topics"][3][field]
    assert f"missing field '{field}'" in refused(tmp_path / "tree", consider=rows)


def test_consider_rows_land_on_their_own_topic_in_any_order(tmp_path):
    rows = [{"slug": s, "risks": [f"{s} risk", " "], "unknowns": [], "decisions": []} for s in reversed(SLUGS)]
    plan = run(tmp_path / "tree", consider={"topics": rows})
    assert [t.slug for t in plan.topics] == SLUGS
    assert [t.risks for t in plan.topics] == [[f"{s} risk"] for s in SLUGS]


# -- start ----------------------------------------------------------------

CHAIN = {"edges": [edge("lending", "members"), edge("tools", "lending"), edge("tools", "space")]}


@pytest.mark.parametrize(
    ("order", "said"),
    [
        (["lending", "members"], "step 1 (lending) waits on members"),
        (["space", "lending", "members"], "step 2 (lending) waits on members"),
        (["members", "lending", "tools"], "step 3 (tools) waits on space"),
        (["members", "tools"], "step 2 (tools) waits on lending, space"),
    ],
)
def test_a_step_ahead_of_its_dependency_reaches_the_verifier(tmp_path, order, said):
    assert said in red(tmp_path / "tree", connect=CHAIN, start={"steps": [step(t) for t in order]})


def test_a_step_may_follow_every_topic_it_waits_on(tmp_path):
    order = ["members", "space", "lending", "tools"]
    plan = run(tmp_path / "tree", connect=CHAIN, start={"steps": [step(t) for t in order]})
    assert [s.topic for s in plan.steps] == order


def test_steps_beyond_the_limit_are_cut(tmp_path):
    order = ["members", "space", "tools", "money", "safety", "lending"]
    plan = run(tmp_path / "tree", start={"steps": [step(t) for t in order]})
    assert [s.topic for s in plan.steps] == order[: start.MAX_STEPS]


@pytest.mark.parametrize("field", ["action", "why"])
def test_a_step_with_nothing_to_say_is_refused(tmp_path, field):
    assert "empty" in refused(tmp_path / "tree", start={"steps": [{**step("members"), field: "  "}]})


LOOP = {"edges": [edge("lending", "space"), edge("space", "lending"), edge("tools", "lending")]}


def test_a_partial_cycle_is_kept_for_the_verifier_and_only_the_walk_keeps_steps_out(tmp_path):
    plan = run(tmp_path / "tree", connect=LOOP)
    assert len(plan.edges) == 3
    assert [t.slug for t in start.ready(plan)] == ["members", "money", "safety"]
    enum = start.schema(plan)["properties"]["steps"]["items"]["properties"]["topic"]["enum"]
    assert enum == SLUGS


@pytest.mark.parametrize("topic", ["lending", "space", "tools"])
def test_a_step_inside_a_partial_cycle_or_behind_one_reaches_the_verifier(tmp_path, topic):
    assert "waits on" in red(tmp_path / "tree", connect=LOOP, start={"steps": [step(topic)]})


def test_a_cycle_over_every_topic_fails_connect_before_consider_is_spent(tmp_path):
    ring = [edge(a, b) for a, b in zip(SLUGS, [*SLUGS[1:], SLUGS[0]])]
    job = job_for()
    llm = FakeLLM(script(connect={"edges": ring}))
    with pytest.raises(PlanPassError, match="has a cycle"):
        pipeline.run_plan(job, tmp_path / "tree", llm)
    failed = job.events[-1]
    assert (failed["kind"], failed["name"]) == ("pass_failed", "connect")
    assert [call["label"] for call in llm.calls][-1] == "connect"
    assert list(tmp_path.iterdir()) == []


# -- depth ----------------------------------------------------------------


@pytest.mark.parametrize("depth", list(TOPIC_COUNTS))
@pytest.mark.parametrize("off_by", [-1, 1])
def test_an_outline_off_by_one_for_its_depth_is_refused(tmp_path, depth, off_by):
    wanted = TOPIC_COUNTS[depth]
    slugs = [f"t{n}" for n in range(wanted + off_by)]
    job = job_for()
    llm = FakeLLM(script(outline=outline_of(slugs)))
    with pytest.raises(PlanPassError, match=f"{len(slugs)} topics, and {wanted} were asked for"):
        pipeline.run_plan(job, tmp_path / "tree", llm, depth)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("depth", list(TOPIC_COUNTS))
def test_each_depth_asks_for_its_count_and_records_itself(tmp_path, depth):
    slugs = [f"t{n}" for n in range(TOPIC_COUNTS[depth])]
    llm = FakeLLM(
        script(
            outline=outline_of(slugs),
            connect={"edges": []},
            consider=consider_of(slugs),
            start={"steps": [step("t0")]},
        )
    )
    pipeline.run_plan(job_for(), tmp_path / "tree", llm, depth)
    plan = Plan.load(tmp_path / "tree")
    assert (plan.depth, len(plan.topics)) == (depth, TOPIC_COUNTS[depth])
    assert f"Return exactly {TOPIC_COUNTS[depth]} topics." in llm.calls[1]["user"]
    assert json.loads(plan_path(tmp_path / "tree").read_text(encoding="utf-8"))["depth"] == depth


def test_no_depth_means_the_default_on_a_model_and_none_offline(tmp_path):
    assert run(tmp_path / "model").depth == "standard"
    pipeline.run_plan(job_for(), tmp_path / "offline", None, "deep")
    assert Plan.load(tmp_path / "offline").depth is None


# -- the outline event ----------------------------------------------------


def outline_events(job: Job) -> list[dict]:
    return [{k: v for k, v in e.items() if k != "at"} for e in job.events if e["kind"] == "outline"]


def test_the_outline_event_carries_exactly_what_a_view_needs(tmp_path):
    job = job_for()
    pipeline.run_plan(job, tmp_path / "tree", FakeLLM(script()), "standard")
    estimate = pipeline.call_estimate(FakeLLM([]))
    assert outline_events(job) == [{"kind": "outline", "topics": SLUGS, "depth": "standard", "estimate": estimate}]
    assert estimate in job.lines


def test_an_offline_outline_event_has_no_depth_and_no_calls(tmp_path):
    job = job_for()
    pipeline.run_plan(job, tmp_path / "tree")
    [event] = outline_events(job)
    assert event["depth"] is None
    assert event["topics"] == [t.slug for t in baseline.build_plan(IDEA).topics]
    assert event["estimate"].startswith("Estimated model calls: 0, because this run is offline.")


def test_the_outline_event_sits_between_the_outline_and_connect_passes(tmp_path):
    job = job_for()
    pipeline.run_plan(job, tmp_path / "tree", FakeLLM(script()))
    order = [(e["kind"], e.get("name", "")) for e in job.events]
    at = order.index(("outline", ""))
    assert order[at - 1 : at + 2] == [("pass_done", "outline"), ("outline", ""), ("pass_started", "connect")]


def test_the_outline_event_survives_json_and_the_console_fold(tmp_path):
    job = job_for()
    pipeline.run_plan(job, tmp_path / "tree", FakeLLM(script()))
    assert json.loads(json.dumps(job.snapshot()))["events"] == job.events
    assert [p.state for p in progress.fold(job.events).passes] == [progress.DONE] * (len(PASS_NAMES) + 1)


def test_a_run_that_stops_at_the_outline_emits_no_outline_event(tmp_path):
    job = job_for()
    with pytest.raises(PlanPassError):
        pipeline.run_plan(job, tmp_path / "tree", FakeLLM(script(outline={"topics": []})))
    assert outline_events(job) == []


# -- failure at each pass -------------------------------------------------


class DiesAt(FakeLLM):
    """A backend that fails outright at one pass, as a spent balance does."""

    def __init__(self, name: str):
        super().__init__(script())
        self.name = name

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == self.name:
            raise LLMError(f"pass {label!r} failed: out of credit")
        return super().structured(system=system, user=user, schema=schema, label=label)


@pytest.mark.parametrize("name", PLAN_PASS_NAMES)
def test_a_backend_failure_at_any_pass_is_a_failed_pass_and_no_tree(tmp_path, name):
    job, tree = job_for(), tmp_path / "tree"
    with pytest.raises(LLMError, match="out of credit"):
        pipeline.run_plan(job, tree, DiesAt(name))
    failed = job.events[-1]
    assert (failed["kind"], failed["name"], failed["index"]) == ("pass_failed", name, PASS_NAMES.index(name) + 1)
    assert list(tmp_path.iterdir()) == []
    assert pipeline.after_failure(tree).startswith(f"Nothing was written to {tree}.")


# -- the review's edits ---------------------------------------------------


def eight() -> Plan:
    plan = baseline.build_plan(IDEA)
    return outline.add(outline.add(plan, "One", "a"), "Two", "b")


def test_add_is_refused_at_the_limit_before_it_reads_anything_else():
    with pytest.raises(ValueError, match="at most 8"):
        outline.add(eight(), "", "")


@pytest.mark.parametrize(
    ("title", "why"),
    [("", "reason"), ("   ", "reason"), ("Title", ""), ("Title", " \n ")],
)
def test_add_needs_a_title_and_a_reason(title, why):
    with pytest.raises(ValueError, match="needs a title and a line on why"):
        outline.add(baseline.build_plan(IDEA), title, why)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Budget", "budget"),
        ("the budget", "Budget!"),
        ("alpha beta gamma delta epsilon", "alpha-beta gamma_delta zeta"),
    ],
)
def test_two_titles_that_slug_the_same_cannot_both_be_added(first, second):
    plan = outline.add(baseline.build_plan(IDEA), first, "a")
    with pytest.raises(ValueError, match="there is already a topic"):
        outline.add(plan, second, "b")


def test_a_title_that_slugs_like_an_existing_topic_cannot_be_added():
    with pytest.raises(ValueError, match="already a topic 'risks'"):
        outline.add(baseline.build_plan(IDEA), "Risks", "b")


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("The", "plan"),
        ("保険", "plan"),
        ("!!!", "plan"),
        ("2024 budget", "plan_2024_budget"),
        ("../../etc/passwd", "etc_passwd"),
        ("x" * 200, "x" * 64),
    ],
)
def test_add_makes_a_safe_slug_from_any_title(title, slug):
    plan = outline.add(baseline.build_plan(IDEA), title, "why")
    assert plan.topics[-1].slug == slug


def test_add_after_dropping_a_slug_may_take_it_with_no_findings():
    plan = outline.drop(baseline.build_plan(IDEA), "scope")
    plan = outline.add(plan, "Scope", "A person's own topic.")
    assert (plan.topics[-1].slug, plan.topics[-1].findings) == ("scope", [])


def test_rename_changes_only_the_title():
    plan = baseline.build_plan(IDEA)
    renamed = outline.rename(plan, "2", "  The  boundary ")
    assert renamed.topics[1].title == "The boundary"
    assert renamed.topics[1].model_dump(exclude={"title"}) == plan.topics[1].model_dump(exclude={"title"})
    assert renamed.topics[2:] == plan.topics[2:]


def test_rename_to_another_topics_title_keeps_both_files():
    plan = baseline.build_plan(IDEA)
    renamed = outline.rename(plan, "1", plan.topics[1].title)
    assert len({f"{t.slug}.md" for t in renamed.topics}) == len(plan.topics)


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_rename_to_nothing_is_refused(title):
    with pytest.raises(ValueError, match="needs a title"):
        outline.rename(baseline.build_plan(IDEA), "1", title)


@pytest.mark.parametrize("which", ["0", "7", "-1", "ghost", "", "1.0"])
def test_an_unknown_topic_is_refused_by_drop_and_rename(which):
    plan = baseline.build_plan(IDEA)
    with pytest.raises(ValueError, match="no topic"):
        outline.drop(plan, which)
    with pytest.raises(ValueError, match="no topic"):
        outline.rename(plan, which, "Title")


def test_scope_seed_carries_no_baseline_content_for_a_model_to_inherit():
    plan = scope.seed(IDEA, "", "standard")
    assert (plan.goal, plan.constraints, plan.topics, plan.edges, plan.steps) == ("", [], [], [], [])


# -- what the tester found ------------------------------------------------


@pytest.mark.parametrize("bare", ["a bare string", {"a": "dict"}])
@pytest.mark.parametrize(
    ("name", "spoil"),
    [
        ("scope", lambda bare: {**GOOD["scope"], "constraints": bare}),
        ("scope", lambda bare: {**GOOD["scope"], "questions": bare}),
        ("consider", lambda bare: {"topics": [{**row, "risks": bare} for row in GOOD["consider"]["topics"]]}),
    ],
    ids=["constraints", "questions", "risks"],
)
def test_a_list_field_refuses_a_string_or_dict_rather_than_iterating_it(tmp_path, name, spoil, bare):
    assert "must be a list" in refused(tmp_path / "tree", **{name: spoil(bare)})


@pytest.mark.parametrize("empty", ["", {}])
def test_an_empty_string_or_dict_is_not_an_empty_list_of_edges(tmp_path, empty):
    assert "must be a list" in refused(tmp_path / "tree", connect={"edges": empty})


def test_the_summary_counts_the_topics_a_review_left():
    plan = scope.seed(IDEA, "", "standard").revised(topics=baseline.build_plan(IDEA).topics)
    assert "depth: standard (7 topics)" in outline.add(plan, "One more", "It matters.").summary()


def test_identical_edges_collapse_and_different_kinds_do_not(tmp_path):
    edges = [edge("lending", "members"), edge("lending", "members"), edge("lending", "members", "informs")]
    plan = run(tmp_path / "tree", connect={"edges": edges})
    assert [(e.from_topic, e.kind) for e in plan.edges] == [("lending", "depends-on"), ("lending", "informs")]


def test_the_same_topic_twice_in_start_reaches_the_verifier(tmp_path):
    said = red(tmp_path / "tree", start={"steps": [step("members"), step("space"), step("members")]})
    assert "step 3 (members) repeats a topic" in said


@pytest.mark.parametrize(("count", "most"), [(4, 4), (6, 5)])
def test_start_is_asked_for_at_most_five_steps_and_never_more_than_the_topics(count, most):
    whole = baseline.build_plan(IDEA)
    plan = whole.revised(topics=whole.topics[:count], edges=[])
    assert start.schema(plan)["properties"]["steps"]["maxItems"] == most
    assert f"at most {most} steps" in start.build(plan)[1]


@pytest.mark.parametrize("opener", ["<!-- gone", "<!DOCTYPE x", "<?php", "<script>", "<STYLE>", "<details>", "</div>"])
def test_model_text_cannot_open_an_html_block_that_hides_the_page(tmp_path, opener):
    tree, spoilt = tmp_path / "tree", outline_of(SLUGS)
    spoilt["topics"][0]["why"] = opener
    run(tree, outline=spoilt)
    for page in ("PLAN.md", "topics/members.md"):
        body = (tree / page).read_text(encoding="utf-8").split("-->", 1)[1]
        assert opener not in body and "&lt;" + opener[1:] in body
    assert Plan.load(tree).topics[0].why == opener


class Finishes(FakeLLM):
    """A model that is overtaken: another run's plan lands while `start` is thinking."""

    def __init__(self, tree: Path, rival: Plan):
        super().__init__(script())
        self.tree, self.rival = tree, rival

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == "start":
            self.rival.save(self.tree)
        return super().structured(system=system, user=user, schema=schema, label=label)


def test_a_plan_that_appears_during_the_passes_is_not_overwritten(tmp_path):
    tree, rival = tmp_path / "tree", baseline.build_plan(IDEA)
    with pytest.raises(pipeline.PlanRefused, match="gained a plan"):
        pipeline.run_plan(job_for(), tree, Finishes(tree, rival))
    assert Plan.load(tree) == rival


def half_a_write(monkeypatch) -> None:
    """Writes to plan.json, or to anything beside it, die after half the text has landed."""
    real = Path.write_text

    def dies(self, text, *args, **kwargs):
        if "plan.json" in self.name:
            real(self, text[: len(text) // 2], *args, **kwargs)
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)


def test_a_save_that_dies_keeps_the_plan_that_was_there(tmp_path, monkeypatch):
    tree, plan = tmp_path / "tree", baseline.build_plan(IDEA)
    plan.save(tree)
    before = snapshot(tree)
    half_a_write(monkeypatch)
    with pytest.raises(OSError, match="disk full"):
        plan.revised(goal="Another goal.").save(tree)
    assert snapshot(tree) == before


def test_a_first_save_that_dies_leaves_no_directory_behind(tmp_path, monkeypatch):
    half_a_write(monkeypatch)
    with pytest.raises(OSError, match="disk full"):
        baseline.build_plan(IDEA).save(tmp_path / "deep" / "tree")
    assert list(tmp_path.iterdir()) == []


def test_after_failure_says_so_when_a_tree_holds_no_plan(tmp_path):
    said = pipeline.after_failure(tmp_path)
    assert "holds no plan" in said and "refused" in said
    assert "Nothing was written" not in said


class HoldsToItsSchema(FakeLLM):
    """A fake that refuses, as a real backend would, a `start` its schema does not allow."""

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        response = super().structured(system=system, user=user, schema=schema, label=label)
        if label == "start":
            steps = schema["properties"]["steps"]
            allowed = steps["items"]["properties"]["topic"]["enum"]
            assert len(response["steps"]) <= steps["maxItems"]
            assert all(row["topic"] in allowed for row in response["steps"])
        return response


def test_a_chain_graph_gets_more_than_one_step(tmp_path):
    chain = {"edges": [edge(a, b) for a, b in zip(SLUGS[1:], SLUGS)]}
    order = SLUGS[:4]
    llm = HoldsToItsSchema(script(connect=chain, start={"steps": [step(t) for t in order]})[:5])
    pipeline.run_plan(job_for(), tmp_path / "tree", llm, dream=False)
    assert [s.topic for s in Plan.load(tmp_path / "tree").steps] == order
    shown = llm.calls[-1]["user"]
    assert "- lending depends on: members" in shown and "- members depends on: nothing" in shown
