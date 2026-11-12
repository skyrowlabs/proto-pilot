"""Revising a finished plan: what the outline's edits and the ledger do to one."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, NO_REPAIR, edge, repair_of, script, step
from research_script import OTHER, URL, ResearchingLLM, assumed, cited, fetched, transcript

from protopilot import cli
from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import ledger, pipeline, render, revising, verify
from protopilot.plan.model import MAX_TOPICS, MIN_TOPICS, Plan
from protopilot.plan.passes import outline

pytestmark = [pytest.mark.unit]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def invoke(*args: str, **options: object):
    return CliRunner().invoke(cli.main, list(args), **options)  # type: ignore[arg-type]


def said(result) -> str:
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def offline_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree).ok
    return tree


def researched_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {})).ok
    return tree


def model_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script())).ok
    return tree


def judged(plan: Plan) -> verify.PlanVerdict:
    return verify.verdict(plan, render.render(plan))


# -- what the review's edits do to a finished plan ------------------------


def test_a_rename_on_a_finished_plan_changes_the_title_and_nothing_else(tmp_path):
    before = Plan.load(offline_plan(tmp_path / "tree"))
    after = outline.rename(before, "scope", "The boundary")
    assert [t.slug for t in after.topics] == [t.slug for t in before.topics]
    assert after.topics[1].title == "The boundary"
    assert after.topics[1].model_copy(update={"title": before.topics[1].title}) == before.topics[1]
    assert (after.edges, after.steps, after.dreams, after.research) == (
        before.edges,
        before.steps,
        before.dreams,
        before.research,
    )
    assert judged(after).ok


def test_a_drop_on_a_finished_plan_removes_the_topic_alone_and_leaves_the_plan_red(tmp_path):
    before = Plan.load(offline_plan(tmp_path / "tree"))
    after = outline.drop(before, "audience")
    assert "audience" not in [t.slug for t in after.topics]
    assert (after.edges, after.steps, after.dreams) == (before.edges, before.steps, before.dreams)
    result = judged(after)
    assert result.named(verify.FAILED) == ["topic_map", "start_order", "dreams_shaped"]


# -- which transcript the ledger reads ------------------------------------


def test_the_ledger_is_redrawn_from_the_transcript_each_record_names(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    forged = [r.model_copy(update={"fetches": [], "state": "nothing cited"}) for r in plan.research]
    redrawn = ledger.reconciled(plan.revised(research=[r.model_dump() for r in forged]), tree)
    assert redrawn.research == plan.research


def test_a_record_that_names_another_topics_transcript_has_no_evidence(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    theirs = plan.research_of("lending")
    assert theirs is not None
    borrowed = [
        r.model_copy(update={"transcript": theirs.transcript, "sha256": theirs.sha256}) if r.topic == "members" else r
        for r in plan.research
    ]
    record = ledger.reconciled(plan.revised(research=[r.model_dump() for r in borrowed]), tree).research_of("members")
    assert record is not None
    assert (record.state, record.failure, record.fetches) == ("failed", ledger.NO_EVIDENCE, [])


def test_a_second_transcript_for_a_topic_is_not_one_the_ledger_reads_today(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    said_again = ledger.read_transcript(tree, "members")
    assert said_again is not None
    (ledger.research_dir(tree) / "members.2.jsonl").write_text(said_again, encoding="utf-8")
    moved = [
        r.model_copy(update={"transcript": "members.2.jsonl"}) if r.topic == "members" else r for r in plan.research
    ]
    record = ledger.reconciled(plan.revised(research=[r.model_dump() for r in moved]), tree).research_of("members")
    assert record is not None
    assert (record.state, record.failure) == ("failed", ledger.NO_EVIDENCE)


# -- proto answer ---------------------------------------------------------

QUESTIONS = ["Who runs it?", "Which town?"]


def questioned(tree: Path) -> Path:
    """An offline plan holding two open questions, drawn as `proto plan` would draw it."""
    Plan.load(offline_plan(tree)).revised(questions=QUESTIONS).save(tree)
    assert pipeline.rerender(job_for(), tree).ok
    return tree


def changed(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


@pytest.fixture
def no_backend(monkeypatch):
    """Building any backend fails the test that tried."""

    def refuse(**_: object):
        raise AssertionError("a backend was built")

    monkeypatch.setattr(cli, "build_llm", refuse)


def dying_write(monkeypatch, name: str = "PLAN.md") -> None:
    """The first write of `name` fails, as a full disk would, and every later one works."""
    real, armed = Path.write_text, [True]

    def dies(self, text, *args, **kwargs):
        if self.name == name and armed and armed.pop():
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)


def test_an_answer_becomes_a_constraint_and_only_the_entry_page_moves(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "2", "--dir", str(tree), input="One town only\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert (plan.constraints, plan.questions) == (["Which town? One town only"], ["Who runs it?"])
    assert changed(before, snapshot(tree)) == [".protopilot/plan.json", "PLAN.md"]
    assert "- Which town? One town only" in (tree / "PLAN.md").read_text(encoding="utf-8")
    assert "1 answer(s) are constraints now, and 1 question(s) stay open." in said(result)


def test_with_no_number_each_question_is_asked_and_enter_leaves_one_open(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    result = invoke("answer", "--dir", str(tree), input="\nOne town only\n")
    assert result.exit_code == 0, result.output
    assert "1. Who runs it?" in said(result) and "2. Which town?" in said(result)
    assert Plan.load(tree).questions == ["Who runs it?"]


def test_an_answer_reruns_no_pass_and_leaves_every_topic_as_it_was(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    before = Plan.load(tree)
    assert invoke("answer", "1", "--dir", str(tree), input="Volunteers\n").exit_code == 0
    after = Plan.load(tree)
    assert (after.topics, after.edges, after.steps, after.dreams) == (
        before.topics,
        before.edges,
        before.steps,
        before.dreams,
    )


@pytest.mark.parametrize("typed", ["\n", "   \n"], ids=["enter", "spaces"])
def test_no_answer_changes_nothing_and_is_not_an_error(tmp_path, no_backend, typed):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "1", "--dir", str(tree), input=typed)
    assert result.exit_code == 0 and "No answer was given" in said(result)
    assert snapshot(tree) == before


def test_a_plan_with_no_open_question_says_so_and_exits_zero(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", "--dir", str(tree))
    assert result.exit_code == 0 and "no open question" in said(result)
    assert snapshot(tree) == before


def test_a_number_past_the_last_question_is_refused(tmp_path, no_backend):
    tree = questioned(tmp_path / "tree")
    result = invoke("answer", "3", "--dir", str(tree))
    assert result.exit_code == 1 and "there is no question 3" in said(result)


def test_answer_refuses_a_folder_with_no_plan_and_a_plan_that_is_red(tmp_path, no_backend):
    empty = invoke("answer", "--dir", str(tmp_path))
    assert empty.exit_code == 1 and "there is nothing here to revise" in said(empty)
    tree = questioned(tmp_path / "tree")
    plan = Plan.load(tree)
    plan.revised(steps=list(reversed(plan.steps))).save(tree)
    red = invoke("answer", "1", "--dir", str(tree), input="x\n")
    assert red.exit_code == 1 and "fails its checks" in said(red)


def test_a_question_closed_while_the_answer_was_typed_is_refused(tmp_path):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="not an open question"):
        pipeline.answer(job_for(), tree, {"Who pays?": "Nobody"})
    with pytest.raises(pipeline.PlanRefused, match="No answer was given"):
        pipeline.answer(job_for(), tree, {"Who runs it?": " "})
    assert snapshot(tree) == before


def test_an_answer_that_cannot_be_drawn_puts_the_tree_back(tmp_path, monkeypatch):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.answer(job_for(), tree, {"Who runs it?": "Volunteers"})
    assert snapshot(tree) == before


# -- proto topic rename ---------------------------------------------------


def test_a_rename_keeps_the_slug_the_file_and_everything_keyed_on_it(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before, pages = Plan.load(tree), snapshot(tree)
    result = invoke("topic", "rename", "scope", "The boundary", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    after = Plan.load(tree)
    assert after == outline.rename(before, "scope", "The boundary")
    assert sorted(snapshot(tree)) == sorted(pages)
    assert "# The boundary" in (tree / "topics" / "scope.md").read_text(encoding="utf-8")
    assert "now 'The boundary'" in said(result)


def test_a_rename_redraws_only_the_pages_that_name_the_topic(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    assert invoke("topic", "rename", "operations", "Keeping it going", "--dir", str(tree)).exit_code == 0
    # Operations links to resources alone, and one dream extends it.
    assert changed(before, snapshot(tree)) == [
        ".protopilot/plan.json",
        "PLAN.md",
        "dreams.md",
        "topics/operations.md",
        "topics/resources.md",
    ]


@pytest.mark.parametrize(
    ("slug", "title", "reason"),
    [
        ("ghost", "A title", "no topic 'ghost'; it holds: audience, scope"),
        ("scope", "  ", "a topic needs a title"),
        ("scope", "What is in and what is out", "already called"),
        ("2", "A title", "no topic '2'"),
    ],
    ids=["no-such-topic", "empty-title", "same-title", "a-number-is-not-a-slug"],
)
def test_a_rename_it_cannot_make_changes_nothing(tmp_path, no_backend, slug, title, reason):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("topic", "rename", slug, title, "--dir", str(tree))
    assert result.exit_code == 1 and reason in said(result)
    assert snapshot(tree) == before


def test_a_rename_that_cannot_be_drawn_puts_the_tree_back(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.rename_topic(job_for(), tree, "scope", "The boundary")
    assert snapshot(tree) == before


# -- the dropped-topics list ----------------------------------------------

BEFORE = Path(__file__).resolve().parent / "fixtures" / "plan_before_living_plans.json"


def test_a_plan_json_written_before_topics_could_be_dropped_loads_and_saves_byte_identical(tmp_path):
    written = BEFORE.read_bytes()
    plan = Plan.model_validate_json(written)
    assert plan.dropped_topics == []
    assert plan.save(tmp_path).read_bytes() == written


def test_the_dropped_list_is_left_out_of_plan_json_until_a_topic_is_dropped(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    assert b"dropped_topics" not in (tree / ".protopilot" / "plan.json").read_bytes()
    assert invoke("topic", "drop", "risks", "--why", "Not now.", "--dir", str(tree)).exit_code == 0
    assert [t.model_dump() for t in Plan.load(tree).dropped_topics] == [
        {"slug": "risks", "title": "What could sink it", "why": "Not now."}
    ]
    assert "- What could sink it (`risks`): Not now." in (tree / "PLAN.md").read_text(encoding="utf-8")


def test_a_dropped_topics_slug_is_checked_as_a_topics_is():
    with pytest.raises(ValueError, match="snake_case"):
        Plan.model_validate(
            {**Plan.model_validate_json(BEFORE.read_bytes()).model_dump(), "dropped_topics": [BAD_DROP]}
        )


BAD_DROP = {"slug": "../etc", "title": "T", "why": "w"}


# -- proto topic drop -----------------------------------------------------


def naming(title: str, *snapshots: dict[str, bytes]) -> set[str]:
    """The pages that name a topic by its title, in any of `snapshots`."""
    return {name for pages in snapshots for name, data in pages.items() if title.encode() in data}


def test_a_drop_takes_the_topic_and_what_pointed_at_it_and_says_what_went(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before, pages = Plan.load(tree), snapshot(tree)
    result = invoke("topic", "drop", "audience", "--why", "We know who it is for.", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    after = Plan.load(tree)
    assert [t.slug for t in after.topics] == [t.slug for t in before.topics if t.slug != "audience"]
    assert not [e for e in after.edges if "audience" in (e.from_topic, e.to_topic)]
    assert [s.topic for s in after.steps] == ["first_test", "scope"]
    for note in (
        "removed the link scope depends-on audience",
        "removed step 1: Name the people this is for",
        "set aside dream d1, because its topic was dropped",
        "Who it is for (audience) is dropped",
    ):
        assert note in said(result)
    assert "topics/audience.md" not in snapshot(tree) and "topics/audience.md" in pages


def test_a_drop_redraws_only_the_pages_that_named_the_topic(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    assert invoke("topic", "drop", "audience", "--why", "Known.", "--dir", str(tree)).exit_code == 0
    moved = changed(before, snapshot(tree))
    assert set(moved) <= naming("Who it is for", before) | {".protopilot/plan.json"}
    assert {"topics/resources.md", "topics/operations.md", "topics/risks.md", "sources.md"}.isdisjoint(moved)


def test_a_dream_that_extended_a_dropped_topic_is_set_aside_and_never_deleted(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    before = Plan.load(tree)
    assert invoke("topic", "drop", "audience", "--why", "Known.", "--dir", str(tree)).exit_code == 0
    after = Plan.load(tree)
    was, now = before.dreams[0], after.dreams[0]
    assert (was.anchor, was.verdict, now.anchor, now.verdict) == ("audience", "proposed", "audience", "set-aside")
    assert now.reason == f"{revising.TOPIC_DROPPED} Proposed before: {was.reason}"
    assert after.dreams[1:] == before.dreams[1:]
    page = (tree / "dreams.md").read_text(encoding="utf-8")
    assert "- Extends: Who it is for (a dropped topic)" in page


def test_dropping_a_promoted_topic_drops_the_dream_it_came_from_with_the_persons_reason(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    assert pipeline.promote(job_for(), tree, "d2", pipeline.OfflineLLM()).ok
    new = Plan.load(tree).topics[-1].slug
    assert invoke("topic", "drop", new, "--why", "Tried it; no.", "--dir", str(tree)).exit_code == 0
    dream = Plan.load(tree).dreams[1]
    assert (dream.verdict, dream.promoted_to, dream.reason) == ("dropped", "", "Tried it; no.")


def test_a_set_aside_dream_of_a_dropped_topic_can_still_be_promoted_offline_and_links_to_nothing(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert pipeline.drop_topic(job_for(), tree, "audience", "Known.", pipeline.OfflineLLM).ok
    assert pipeline.promote(job_for(), tree, "d1", pipeline.OfflineLLM()).ok
    plan = Plan.load(tree)
    assert not [e for e in plan.edges if plan.topics[-1].slug in (e.from_topic, e.to_topic)]


def cites_apart(tree: Path) -> Path:
    """A researched plan in which `lending` alone cites a second page."""
    theirs = transcript([cited("Loans run a week.", url=OTHER, title="Cover"), assumed()], [fetched(OTHER)])
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {"lending": theirs})).ok
    return tree


def test_a_dropped_topics_sources_go_only_if_no_other_topic_cites_them(tmp_path, no_backend):
    tree = cites_apart(tmp_path / "tree")
    assert [s.url for s in Plan.load(tree).sources] == [ledger.normal(u) for u in (URL, OTHER)]
    result = invoke("topic", "drop", "lending", "--why", "No lending.", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert [s.url for s in plan.sources] == [URL] and plan.research_of("lending") is None
    assert "removed source s2, which no other topic cites" in said(result)
    assert (ledger.research_dir(tree) / "lending.jsonl").is_file()
    assert invoke("topic", "drop", "money", "--why", "No money.", "--dir", str(tree)).exit_code == 0
    assert [s.url for s in Plan.load(tree).sources] == [URL]


def test_a_plan_keeps_its_fewest_topics(tmp_path, no_backend):
    tree = offline_plan(tmp_path / "tree")
    for slug in ("operations", "risks"):
        assert invoke("topic", "drop", slug, "--why", "No.", "--dir", str(tree)).exit_code == 0
    before = snapshot(tree)
    result = invoke("topic", "drop", "resources", "--why", "No.", "--dir", str(tree))
    assert result.exit_code == 1 and f"at least {MIN_TOPICS} topics" in said(result)
    assert snapshot(tree) == before


@pytest.mark.parametrize(
    ("slug", "why", "reason"),
    [("ghost", "No.", "no topic 'ghost'"), ("scope", "  ", "--why needs a reason")],
    ids=["no-such-topic", "empty-why"],
)
def test_a_drop_it_cannot_make_changes_nothing(tmp_path, no_backend, slug, why, reason):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("topic", "drop", slug, "--why", why, "--dir", str(tree))
    assert result.exit_code == 1 and reason in said(result)
    assert snapshot(tree) == before


def test_why_is_required_to_drop_a_topic(tmp_path):
    result = invoke("topic", "drop", "scope", "--dir", str(tmp_path))
    assert result.exit_code == 2 and "--why" in result.output


def test_dropping_the_only_step_runs_start_again_and_nothing_else(tmp_path):
    tree = model_plan(tmp_path / "tree")
    llm = FakeLLM([{"steps": [step("space")]}])
    assert pipeline.drop_topic(job_for(), tree, "members", "Known.", lambda: llm).ok
    assert [call["label"] for call in llm.calls] == ["start"]
    assert [s.topic for s in Plan.load(tree).steps] == ["space"]


def test_offline_a_drop_that_leaves_no_step_takes_the_twins(tmp_path):
    tree = model_plan(tmp_path / "tree")
    result = invoke("topic", "drop", "members", "--why", "Known.", "--offline", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert "no step is left to begin on" in said(result)
    assert [s.topic for s in Plan.load(tree).steps] == ["lending"]


def test_a_start_that_jumps_ahead_after_a_drop_goes_to_repair(tmp_path):
    tree = model_plan(tmp_path / "tree")
    Plan.load(tree).revised(edges=[edge("lending", "space")]).save(tree)
    llm = FakeLLM([{"steps": [step("lending")]}, repair_of([edge("lending", "space")], ["space", "lending"])])
    assert pipeline.drop_topic(job_for(), tree, "members", "Known.", lambda: llm).ok
    assert [call["label"] for call in llm.calls] == ["start", "repair"]
    assert [s.topic for s in Plan.load(tree).steps] == ["space", "lending"]


@pytest.mark.parametrize(
    "answers", [[LLMError("out of credit")], [{"steps": [step("ghost")]}]], ids=["backend", "shape"]
)
def test_a_start_that_fails_after_a_drop_changes_nothing(tmp_path, answers):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="members was not dropped, and nothing was changed"):
        pipeline.drop_topic(job_for(), tree, "members", "Known.", lambda: FakeLLM(answers))
    assert snapshot(tree) == before


def test_a_backend_that_cannot_be_built_after_a_drop_changes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)

    def unbuildable():
        raise LLMError("no key")

    with pytest.raises(pipeline.PlanRefused, match="nothing was changed: no key"):
        pipeline.drop_topic(job_for(), tree, "members", "Known.", unbuildable)
    assert snapshot(tree) == before


def test_a_drop_that_cannot_be_drawn_puts_the_tree_back_with_its_page(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.drop_topic(job_for(), tree, "audience", "Known.", pipeline.OfflineLLM)
    assert snapshot(tree) == before


# -- proto topic add ------------------------------------------------------


def add(tree: Path, title: str = "Insurance", why: str = "A borrowed saw can hurt someone.", *flags: str):
    return invoke("topic", "add", title, "--why", why, "--dir", str(tree), *(flags or ("--offline",)))


def test_an_added_topic_lands_offline_as_a_promoted_one_does(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    before, pages = Plan.load(tree), snapshot(tree)
    result = add(tree)
    assert result.exit_code == 0, result.output
    after = Plan.load(tree)
    new = after.topics[-1]
    assert (new.slug, new.title, new.why) == ("insurance", "Insurance", "A borrowed saw can hurt someone.")
    assert (new.findings, new.risks, new.unknowns, new.decisions) == ([], [], [], [])
    assert (after.topics[:-1], after.edges, after.steps, after.dreams) == (
        before.topics,
        before.edges,
        before.steps,
        before.dreams,
    )
    assert changed(pages, snapshot(tree)) == [".protopilot/plan.json", "PLAN.md", "topics/insurance.md"]
    assert render.NOT_RESEARCHED in (tree / "topics" / "insurance.md").read_text(encoding="utf-8")
    assert "it is not researched" in said(result)


def test_with_a_model_an_added_topic_is_connected_and_considered_in_one_call(tmp_path, monkeypatch):
    tree = model_plan(tmp_path / "tree")
    fitted = {"edges": [edge("insurance", "members")], "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]}
    llm = FakeLLM([fitted])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    assert add(tree, "Insurance", "It matters.", "--backend", "api").exit_code == 0
    plan = Plan.load(tree)
    assert [call["label"] for call in llm.calls] == ["promote"]
    assert (plan.topics[-1].risks, plan.edges[-1].model_dump()) == (["r"], edge("insurance", "members"))
    assert "## The new topic" in llm.calls[0]["user"] and '"slug": "insurance"' in llm.calls[0]["user"]


def test_a_link_from_an_added_topic_that_breaks_the_start_is_mended_at_the_new_link(tmp_path):
    tree = model_plan(tmp_path / "tree")
    links = [*GOOD["connect"]["edges"], edge("members", "insurance")]
    fitted = {"edges": [edge("members", "insurance")], "risks": [], "unknowns": [], "decisions": []}
    llm = FakeLLM([fitted, repair_of(links, ["insurance", "members"])])
    assert pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", llm).ok
    assert [s.topic for s in Plan.load(tree).steps] == ["insurance", "members"]


def test_an_addition_that_stays_red_changes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    fitted = {"edges": [edge("members", "insurance")], "risks": [], "unknowns": [], "decisions": []}
    with pytest.raises(pipeline.PlanRefused, match="Nothing was changed, because the result failed its checks"):
        pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", FakeLLM([fitted, NO_REPAIR]))
    assert snapshot(tree) == before


def test_a_backend_failure_while_adding_changes_nothing(tmp_path):
    tree = model_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="'Insurance' was not added, and nothing was changed"):
        pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", FakeLLM([LLMError("out of credit")]))
    assert snapshot(tree) == before


@pytest.mark.parametrize(
    ("title", "why", "reason"),
    [
        ("Audience", "It matters.", "there is already a topic 'audience'"),
        ("Insurance", "  ", "a topic needs a title and a line on why it matters"),
        ("  ", "It matters.", "a topic needs a title and a line on why it matters"),
    ],
    ids=["collides", "empty-why", "empty-title"],
)
def test_an_addition_it_cannot_make_changes_nothing(tmp_path, title, why, reason):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = add(tree, title, why)
    assert result.exit_code == 1 and reason in said(result)
    assert snapshot(tree) == before


def test_a_plan_holds_at_most_its_most_topics(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    for number in range(MAX_TOPICS - 6):
        assert add(tree, f"Extra {'abc'[number]}").exit_code == 0
    result = add(tree, "One too many")
    assert result.exit_code == 1 and f"at most {MAX_TOPICS} topics" in said(result)


def test_adding_a_dropped_topic_again_is_told_it_was_dropped_and_why(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("topic", "drop", "risks", "--why", "Not now.", "--offline", "--dir", str(tree)).exit_code == 0
    result = add(tree, "Risks", "Now.")
    assert result.exit_code == 0, result.output
    assert "What could sink it was dropped before, because: Not now. It is a topic again" in said(result)
    plan = Plan.load(tree)
    assert plan.topics[-1].slug == "risks" and plan.dropped_topics == []
    assert "## Dropped topics" not in (tree / "PLAN.md").read_text(encoding="utf-8")


def test_a_dropped_title_added_under_a_new_slug_is_told_and_the_old_slug_stays_remembered(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert invoke("topic", "drop", "audience", "--why", "Known.", "--offline", "--dir", str(tree)).exit_code == 0
    result = add(tree, "who it is for", "We do not know after all.")
    assert result.exit_code == 0, result.output
    assert "Who it is for was dropped before, because: Known. It is a topic again" in said(result)
    plan = Plan.load(tree)
    assert plan.topics[-1].slug == "who_it_is" and [t.slug for t in plan.dropped_topics] == ["audience"]


def test_an_addition_that_cannot_be_drawn_puts_the_tree_back(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", pipeline.OfflineLLM())
    assert snapshot(tree) == before


# -- the three together, as the plan's done-check has them ----------------


def test_drop_then_add_then_answer_each_land_and_touch_only_pages_that_name_the_topic(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    start = snapshot(tree)
    assert invoke("topic", "drop", "operations", "--why", "Later.", "--offline", "--dir", str(tree)).exit_code == 0
    dropped = snapshot(tree)
    assert set(changed(start, dropped)) <= naming("How it runs day to day", start) | {".protopilot/plan.json"}
    assert add(tree).exit_code == 0
    grown = snapshot(tree)
    assert changed(dropped, grown) == [".protopilot/plan.json", "PLAN.md", "topics/insurance.md"]
    assert invoke("answer", "--dir", str(tree)).exit_code == 0
    assert snapshot(tree) == grown
    untouched = ["audience", "scope", "risks", "first_test"]
    assert all(grown[f"topics/{slug}.md"] == start[f"topics/{slug}.md"] for slug in untouched)
