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
from protopilot.plan import baseline, ledger, pipeline, render, revising, verify
from protopilot.plan.model import MAX_TOPICS, MIN_TOPICS, Edge, Plan
from protopilot.plan.passes import connect, consider, outline, repair, research

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


def renamed(plan: Plan, slug: str, name: str, said_: str | None = None) -> Plan:
    """`plan` with `slug`'s record naming the transcript `name`, hashed as `said_` if that is given."""
    update = {"transcript": name, **({"sha256": ledger.digest(said_)} if said_ is not None else {})}
    return plan.revised(research=[r.model_copy(update=update) if r.topic == slug else r for r in plan.research])


def test_with_two_transcripts_for_a_topic_the_ledger_reads_the_one_its_record_names(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    plan = Plan.load(tree)
    second = transcript([cited(url=OTHER)], [fetched(OTHER), fetched("https://x.test/403", code=403)])
    ledger.write_transcript(tree, "members", second, 2)
    first = ledger.reconciled(plan, tree).research_of("members")
    current = ledger.reconciled(renamed(plan, "members", "members.2.jsonl", second), tree).research_of("members")
    assert first is not None and current is not None
    assert [f.url for f in first.fetches] == [URL]
    assert [(f.url, f.usable) for f in current.fetches] == [(OTHER, True), ("https://x.test/403", False)]
    # The plan's findings still cite the first page, so the second transcript backs none of them.
    assert (first.state, current.state) == ("researched", "nothing cited")


@pytest.mark.parametrize("name", ["lending.2.jsonl", "members.1.jsonl", "members.02.jsonl", "members.x.jsonl", ""])
def test_a_record_may_name_only_its_own_topics_transcripts(tmp_path, name):
    tree = researched_plan(tmp_path / "tree")
    said_ = ledger.read_transcript(tree, "members") or ""
    if name:
        (ledger.research_dir(tree) / name).write_text(said_, encoding="utf-8")
    record = ledger.reconciled(renamed(Plan.load(tree), "members", name, said_), tree).research_of("members")
    assert record is not None and (record.state, record.failure) == ("failed", ledger.NO_EVIDENCE)


def test_a_numbered_transcript_that_was_altered_is_no_evidence(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    ledger.write_transcript(tree, "members", transcript(), 2)
    record = ledger.reconciled(renamed(Plan.load(tree), "members", "members.2.jsonl", "other"), tree)
    assert record.research_of("members").state == "failed"  # type: ignore[union-attr]


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


# -- proto research SLUG --------------------------------------------------

AGAIN = transcript([cited("Loans run a week.", url=OTHER, title="Cover"), assumed()], [fetched(OTHER)])


def noted(slug: str = "members", word: str = "new") -> dict:
    return {"topics": [{"slug": slug, "risks": [f"{word} r"], "unknowns": [f"{word} u?"], "decisions": [f"{word} d"]}]}


def refit(*links: dict, slug: str = "members") -> list[dict]:
    """The two answers a re-research asks for: the topic's links, kept unless given, and its notes."""
    kept = [link for link in GOOD["connect"]["edges"] if slug in (link["from_topic"], link["to_topic"])]
    return [{"edges": list(links) or kept}, noted(slug)]


def again(tree: Path, llm: FakeLLM, slug: str = "members", deeper: bool = False) -> verify.PlanVerdict:
    return pipeline.research_topic(job_for(), tree, slug, llm, deeper)


class NeverAsked(FakeLLM):
    """Answers the structured passes, and fails the test that makes a research call."""

    def research(self, **_: object):
        raise AssertionError("a research call was made, and a transcript was there to replay")


def test_research_replaces_one_topics_findings_and_record_and_keeps_the_old_transcript(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    before, first = Plan.load(tree), ledger.read_transcript(tree, "members")
    llm = ResearchingLLM(refit(), {"members": AGAIN})
    assert again(tree, llm).ok
    after = Plan.load(tree)
    record = after.research_of("members")
    assert record is not None
    assert (llm.researched, [call["label"] for call in llm.calls]) == (["members"], ["connect", "consider"])
    assert [f.text for f in after.topics[0].findings] == ["Loans run a week.", "Volunteers will turn up every week."]
    assert (record.transcript, record.sha256, record.state) == ("members.2.jsonl", ledger.digest(AGAIN), "researched")
    assert ledger.read_transcript(tree, "members") == first and ledger.read_transcript(tree, "members", 2) == AGAIN
    assert after.topics[0].risks == ["new r"] and after.topics[1:] == before.topics[1:]
    assert [r for r in after.research if r.topic != "members"] == [r for r in before.research if r.topic != "members"]
    assert verify.verdict(ledger.reconciled(after, tree), render.read(tree)).ok


def test_research_changes_that_topics_page_and_the_sources_and_no_other_page(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    assert again(tree, ResearchingLLM(refit(), {"members": AGAIN})).ok
    assert changed(before, snapshot(tree)) == [
        ".protopilot/plan.json",
        ".protopilot/research/members.2.jsonl",
        "sources.md",
        "topics/members.md",
    ]


def test_research_from_the_command_line_says_what_it_replaced(tmp_path, monkeypatch):
    tree = researched_plan(tmp_path / "tree")
    monkeypatch.setattr(cli, "build_llm", lambda **_: ResearchingLLM(refit(), {"members": AGAIN}))
    result = invoke("research", "members", "--backend", "claude-code", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert "members: 1 cited finding(s), 1 of 1 fetch(es) usable" in said(result)
    assert "Members (members) is researched again, and its earlier transcript stays beside the new one." in said(result)


def test_only_the_researched_topics_links_are_open_and_the_rest_stay(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    llm = ResearchingLLM(refit(edge("members", "tools", "informs")), {"members": AGAIN})
    assert again(tree, llm).ok
    links = [e.model_dump() for e in Plan.load(tree).edges]
    assert links == [edge("money", "space", "informs"), edge("members", "tools", "informs")]
    assert "lending" not in (tree / "topics" / "members.md").read_text(encoding="utf-8").lower()
    asked = llm.calls[0]["user"]
    assert "Only the links of `members` are open" in asked and "- money informs space" in asked
    assert "Return one entry, for `members` alone" in llm.calls[1]["user"]


@pytest.mark.parametrize(
    ("answers", "reason"),
    [
        ([{"edges": [edge("money", "safety")]}], "an edge leaves out members"),
        ([refit()[0], noted("lending")], "wanted one entry for each of members; got lending"),
        ([LLMError("out of credit")], "out of credit"),
    ],
    ids=["a-link-between-others", "notes-for-another-topic", "backend"],
)
def test_a_fit_that_reaches_another_topic_changes_nothing_and_the_rerun_replays(tmp_path, answers, reason):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match=reason) as refused:
        again(tree, ResearchingLLM(answers, {"members": AGAIN}))
    assert "Its transcript is kept, and a rerun replays it" in str(refused.value)
    assert changed(before, snapshot(tree)) == [".protopilot/research/members.2.jsonl"]
    job = job_for()
    assert pipeline.research_topic(job, tree, "members", NeverAsked(refit())).ok
    assert any("replayed from the transcript an earlier try left" in line for line in job.lines)
    assert Plan.load(tree).research_of("members").transcript == "members.2.jsonl"  # type: ignore[union-attr]


def test_a_research_call_that_fails_changes_nothing_and_leaves_no_transcript(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="members was not researched, and nothing was changed: timed out"):
        again(tree, ResearchingLLM([], {"members": LLMError("timed out")}))
    assert snapshot(tree) == before


def test_a_research_that_cannot_be_drawn_puts_the_tree_back_and_keeps_only_the_transcript(tmp_path, monkeypatch):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    dying_write(monkeypatch, "sources.md")
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        again(tree, ResearchingLLM(refit(), {"members": AGAIN}))
    assert changed(before, snapshot(tree)) == [".protopilot/research/members.2.jsonl"]


def test_a_topic_whose_first_research_failed_can_be_researched_alone(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {"tools": LLMError("timed out")})).ok
    assert Plan.load(tree).research_of("tools").state == "failed"  # type: ignore[union-attr]
    job = job_for()
    assert pipeline.research_topic(job, tree, "tools", ResearchingLLM([{"edges": []}, noted("tools")], {})).ok
    record = Plan.load(tree).research_of("tools")
    assert record is not None and (record.state, record.transcript) == ("researched", "tools.jsonl")
    assert "Tools (tools) is researched. Its findings and its record are replaced, not merged." in job.lines


def test_a_source_only_the_researched_topic_cited_leaves_when_it_stops_citing_it(tmp_path):
    tree = cites_apart(tmp_path / "tree")
    assert [s.id for s in Plan.load(tree).sources] == ["s1", "s2"]
    assert again(tree, ResearchingLLM(refit(slug="lending"), {}), "lending").ok
    plan = Plan.load(tree)
    assert [(s.id, s.url) for s in plan.sources] == [("s1", URL)]
    assert OTHER not in (tree / "sources.md").read_text(encoding="utf-8")


def test_research_that_cites_nothing_this_time_leaves_the_topic_not_researched(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    nothing = transcript([assumed()], [fetched(OTHER, code=403)])
    assert again(tree, ResearchingLLM(refit(), {"members": nothing})).ok
    plan = Plan.load(tree)
    assert plan.research_of("members").state == "nothing cited" and plan.researched  # type: ignore[union-attr]
    assert "Research ran and cited no page it fetched." in (tree / "topics" / "members.md").read_text(encoding="utf-8")


def at_depth(tree: Path, depth: str) -> Path:
    """A researched plan recorded at `depth`: the depth is what research reads, whatever the topic count."""
    Plan.load(researched_plan(tree)).revised(depth=depth).save(tree)
    return tree


def test_deeper_gives_one_call_the_next_depths_effort_and_stores_nothing(tmp_path):
    tree = at_depth(tmp_path / "tree", "shallow")
    seen: list[tuple[str, dict]] = []

    class Watching(ResearchingLLM):
        def research(self, *, system: str, user: str, schema: dict, label: str):
            seen.append((system, schema))
            return super().research(system=system, user=user, schema=schema, label=label)

    lo, hi, pages = research.EFFORT["standard"]
    five = transcript([cited(), *(assumed(f"Guess {n}.") for n in range(hi - 1))])
    assert again(tree, Watching(refit(), {"members": five}), deeper=True).ok
    system, schema = seen[0]
    assert f"Read at most {pages} pages" in system
    assert (schema["properties"]["findings"]["minItems"], schema["properties"]["findings"]["maxItems"]) == (lo, hi)
    plan = Plan.load(tree)
    assert plan.depth == "shallow" and len(plan.topics[0].findings) == hi > research.EFFORT["shallow"][1]


def test_deeper_on_the_deepest_plan_is_refused_before_any_call(tmp_path):
    tree = at_depth(tmp_path / "tree", "deep")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match="at depth deep, the most research reads"):
        again(tree, NeverAsked([]), deeper=True)
    assert snapshot(tree) == before


def test_an_offline_plan_has_no_depth_and_deeper_reads_as_one_past_the_default():
    plan = Plan(slug="p", title="P", idea=IDEA)
    assert (plan.depth, research.deeper(plan)) == (None, "deep")


@pytest.mark.parametrize("flags", [("--offline",), ("--backend", "offline")])
def test_research_offline_is_refused_in_a_sentence(tmp_path, flags):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("research", "scope", "--dir", str(tree), *flags)
    assert result.exit_code == 1 and "reads the web, and offline reads nothing" in said(result)
    assert snapshot(tree) == before


def test_a_backend_that_says_it_cannot_research_is_refused_before_a_job(tmp_path, monkeypatch):
    tree = offline_plan(tmp_path / "tree")

    class Refuses(FakeLLM):
        research_refusal = "Research runs only on another backend."

    monkeypatch.setattr(cli, "build_llm", lambda **_: Refuses([]))
    result = invoke("research", "scope", "--dir", str(tree))
    assert result.exit_code == 1
    assert "Research runs only on another backend. No model was called." in said(result)


@pytest.mark.parametrize(
    ("llm", "reason"),
    [(pipeline.OfflineLLM(), "research does not run offline"), (FakeLLM([]), "this backend has no research call")],
    ids=["offline", "no-research-call"],
)
def test_the_pipeline_refuses_a_backend_that_cannot_research(tmp_path, llm, reason):
    tree = offline_plan(tmp_path / "tree")
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match=reason):
        again(tree, llm, "scope")
    assert snapshot(tree) == before


def test_research_refuses_a_topic_the_plan_does_not_hold(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    with pytest.raises(pipeline.PlanRefused, match="no topic 'ghost'; it holds: members, lending"):
        again(tree, NeverAsked([]), "ghost")


# -- the passes, narrowed to one topic ------------------------------------


def test_the_twins_of_a_narrowed_pass_return_that_topic_alone():
    plan = baseline.build_plan(IDEA)
    assert consider.offline(plan, only="scope") == {
        "topics": [{"slug": "scope", **{f: getattr(plan.topics[1], f) for f in consider.FIELDS}}]
    }
    links = connect.offline(plan, only="operations")["edges"]
    assert links == [edge("operations", "resources")]
    assert connect.apply(plan, {"edges": links}, only="operations").edges == plan.edges
    assert consider.schema(plan, only="scope")["properties"]["topics"]["items"]["properties"]["slug"]["enum"] == [
        "scope"
    ]


# -- the held-topic guard on repair ---------------------------------------

WAITS = edge("members", "tools")
#: The plan's links once `members` is fitted to wait on `tools`, which its one step then jumps.
REFITTED = [edge("lending", "members"), edge("money", "space", "informs"), WAITS]
MENDED = repair_of(REFITTED, ["tools", "members"])
#: A repair that mends the step and also links two topics the change never touched.
STRAYS = repair_of([*REFITTED, edge("money", "safety")], ["tools", "members"])


def test_a_planted_repair_that_rewrites_another_topics_links_is_thrown_away(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    llm = ResearchingLLM([*refit(edge("lending", "members"), WAITS), STRAYS, MENDED], {"members": AGAIN})
    job = job_for()
    assert pipeline.research_topic(job, tree, "members", llm).ok
    rejected = [e["reason"] for e in job.events if e["kind"] == "repair_rejected"]
    assert rejected == ["it added links between settled topics: money depends-on safety"]
    plan = Plan.load(tree)
    assert [e.model_dump() for e in plan.edges] == REFITTED and [s.topic for s in plan.steps] == ["tools", "members"]


def test_a_repair_after_a_change_is_told_which_topic_changed(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    llm = ResearchingLLM([*refit(edge("lending", "members"), WAITS), MENDED], {"members": AGAIN})
    assert again(tree, llm).ok
    asked = llm.calls[-1]["user"]
    assert "A person has just changed one part of this plan: members." in asked
    assert repair.SETTLED_RULE not in asked


def test_a_repair_that_only_ever_strays_changes_nothing(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    llm = ResearchingLLM([*refit(edge("lending", "members"), WAITS), STRAYS, STRAYS, STRAYS], {"members": AGAIN})
    with pytest.raises(pipeline.PlanRefused, match="Nothing was changed, because the result failed its checks"):
        again(tree, llm)
    assert changed(before, snapshot(tree)) == [".protopilot/research/members.2.jsonl"]


def held_and(change) -> tuple[Plan, Plan]:
    held = baseline.build_plan(IDEA)
    return held, change(held)


def reworded(plan: Plan, slug: str) -> Plan:
    topics = [t.model_copy(update={"risks": ["Rewritten."]}) if t.slug == slug else t for t in plan.topics]
    return plan.revised(topics=topics)


def test_a_repair_that_rewrites_another_topic_is_named_and_the_changed_one_is_free():
    held, after = held_and(lambda plan: reworded(plan, "risks"))
    assert repair.unsettled(held, after, frozenset({"scope"})) == "it rewrote settled topics: risks"
    assert repair.unsettled(held, after, frozenset({"risks"})) == ""


def test_only_the_changed_topics_links_and_steps_may_move():
    held, after = held_and(lambda plan: plan.revised(edges=plan.edges[1:], steps=plan.steps[:2]))
    lost = "scope depends-on audience"
    assert repair.unsettled(held, after, frozenset({"risks"})) == f"it removed settled links: {lost}"
    assert repair.unsettled(held, after, frozenset({"scope"})) == ""
    assert repair.unsettled(held, held.revised(steps=held.steps[1:]), frozenset({"scope"})) == (
        "it changed settled steps: audience"
    )


def test_with_no_topic_named_the_guard_still_opens_only_the_new_ones():
    held = baseline.build_plan(IDEA)
    grown = outline.add(held, "Insurance", "It matters.")
    linked = grown.revised(edges=[*grown.edges, Edge(from_topic="insurance", to_topic="scope", kind="informs")])
    assert repair.unsettled(held, linked) == ""
    assert repair.unsettled(held, reworded(linked, "risks")) == "it rewrote settled topics: risks"


# -- the partly-researched stamp ------------------------------------------


def unresearched_plan(tree: Path) -> Path:
    """A model plan made with research off, as `--no-research` makes one."""
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script()), researching=False).ok
    return tree


def entry(tree: Path, name: str = "PLAN.md") -> str:
    return (tree / name).read_text(encoding="utf-8")


def test_researching_one_topic_of_an_unresearched_plan_stamps_it_partly(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    assert render.NOT_RESEARCHED in entry(tree)
    assert again(tree, ResearchingLLM(refit(), {})).ok
    plan = Plan.load(tree)
    assert plan.researched and [r.topic for r in plan.research] == ["members"]
    for page in (entry(tree), entry(tree, "sources.md")):
        assert "> **Partly researched.** 1 of 6 topics are researched." in page
        assert render.RESEARCHED not in page and render.NOT_RESEARCHED not in page
        assert "> - Lending: Research did not run for it." in page and "> - Members:" not in page
    assert render.TOPIC_RESEARCHED in entry(tree, "topics/members.md")


def test_the_first_research_of_an_unresearched_plan_redraws_no_other_topics_page(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    before = snapshot(tree)
    assert again(tree, ResearchingLLM(refit(), {})).ok
    assert changed(before, snapshot(tree)) == [
        ".protopilot/plan.json",
        ".protopilot/research/members.jsonl",
        "PLAN.md",
        "sources.md",
        "topics/members.md",
    ]
    assert render.NOT_RESEARCHED in entry(tree, "topics/lending.md")


def test_a_plan_is_stamped_whole_only_when_every_topic_is_researched(tmp_path):
    whole = researched_plan(tmp_path / "whole")
    assert render.RESEARCHED in entry(whole) and "Partly researched" not in entry(whole)
    part = tmp_path / "part"
    assert pipeline.run_plan(job_for(), part, ResearchingLLM(script(), {"money": LLMError("timed out")})).ok
    assert "> **Partly researched.** 5 of 6 topics are researched." in entry(part)
    assert render.RESEARCHED not in entry(part)


def test_a_topic_added_to_a_researched_plan_makes_it_partly_and_is_stamped_as_never_reached(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    fitted = {"edges": [], "risks": [], "unknowns": [], "decisions": []}
    assert pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", FakeLLM([fitted])).ok
    assert "> **Partly researched.** 6 of 7 topics are researched." in entry(tree)
    assert "> - Insurance: Research did not run for it." in entry(tree)
    assert render.NOT_RESEARCHED in entry(tree, "topics/insurance.md")


def test_when_the_only_researched_topic_cites_nothing_again_the_plan_is_stamped_not_researched(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    assert again(tree, ResearchingLLM(refit(), {})).ok
    nothing = transcript([assumed()], [fetched(OTHER, code=403)])
    assert again(tree, ResearchingLLM(refit(), {"members": nothing})).ok
    plan = Plan.load(tree)
    assert (plan.researched, plan.sources) == (False, [])
    assert render.NOT_RESEARCHED in entry(tree) and "Partly researched" not in entry(tree)
    assert f"{render.NOT_RESEARCHED} Research ran and cited no page it fetched." in entry(tree, "topics/members.md")
