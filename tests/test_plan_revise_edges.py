"""Revising a finished plan, at its edges: look-alike slugs, stale transcripts, and a write that dies anywhere."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, script
from research_script import OTHER, URL, ResearchingLLM, assumed, cited, fetched, transcript

from protopilot import cli
from protopilot.jobs import Job
from protopilot.llm import LLMError
from protopilot.plan import ledger, pipeline, render, verify
from protopilot.plan.model import Finding, Plan

pytestmark = [pytest.mark.unit]

SLUGS = ["members", "lending", "space", "tools", "money", "safety"]
BEFORE = Path(__file__).resolve().parent / "fixtures" / "plan_before_living_plans.json"
AGAIN = transcript([cited("Loans run a week.", url=OTHER, title="Cover"), assumed()], [fetched(OTHER)])
THIRD_URL = "https://example.com/third"
THIRD = transcript([cited("Third.", url=THIRD_URL, title="Third")], [fetched(THIRD_URL)])
NOTHING = transcript([assumed()], [fetched("https://x.test/403", code=403)])
BARE = {"edges": [], "risks": [], "unknowns": [], "decisions": []}


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def invoke(*args: str, **options: object):
    return CliRunner().invoke(cli.main, list(args), **options)  # type: ignore[arg-type]


def said(result) -> str:
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def changed(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def offline_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree).ok
    return tree


def questioned(tree: Path, questions: tuple[str, ...] = ("Who runs it?", "Which town?")) -> Path:
    Plan.load(offline_plan(tree)).revised(questions=list(questions)).save(tree)
    assert pipeline.rerender(job_for(), tree).ok
    return tree


def researched_plan(tree: Path, research: dict[str, object] | None = None) -> Path:
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), research or {})).ok
    return tree


def unresearched_plan(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree, FakeLLM(script()), researching=False).ok
    return tree


def refit(slug: str = "members") -> list[dict]:
    """The two answers a re-research asks for: the topic's own links, kept, and its notes."""
    kept = [link for link in GOOD["connect"]["edges"] if slug in (link["from_topic"], link["to_topic"])]
    return [{"edges": kept}, {"topics": [{"slug": slug, "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]}]}]


def again(tree: Path, slug: str, said_: object = None, answers: list | None = None, deeper: bool = False):
    llm = ResearchingLLM(refit(slug) if answers is None else answers, {slug: said_} if said_ is not None else {})
    return pipeline.research_topic(job_for(), tree, slug, llm, deeper)


class NeverAsked(FakeLLM):
    """Answers the structured passes, and fails the test that makes a research call."""

    def research(self, **_: object):
        raise AssertionError("a research call was made")


def stamp(tree: Path) -> str:
    return next(line for line in (tree / "PLAN.md").read_text(encoding="utf-8").splitlines() if line.startswith("> **"))


def dying_write(monkeypatch, name: str) -> list[bool]:
    """The first write of a file called `name` fails, as a full disk would. The list empties when it did."""
    real, armed = Path.write_text, [True]

    def dies(self, text, *args, **kwargs):
        if self.name == name and armed and armed.pop():
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)
    return armed


# -- whose transcript a name is -------------------------------------------


@pytest.mark.parametrize(
    ("name", "slug", "number"),
    [
        ("members.2.jsonl", "members", 2),
        ("members.10.jsonl", "members", 10),
        ("members_2.jsonl", "members_2", 1),
        ("members_2.2.jsonl", "members_2", 2),
        ("members_2.jsonl", "members", 0),
        ("members.2.jsonl", "members_2", 0),
        ("members_2.2.jsonl", "members", 0),
        ("members2.jsonl", "members", 0),
        ("members.2.jsonl", "member", 0),
        ("members.2.2.jsonl", "members", 0),
        ("members.2.jsonl\n", "members", 0),
        ("../members.2.jsonl", "members", 0),
        ("sub/members.jsonl", "members", 0),
        ("members.0.jsonl", "members", 0),
        ("membersX2.jsonl", "members", 0),
    ],
)
def test_a_transcript_name_belongs_to_one_slug_whatever_the_slug_ends_in(name, slug, number):
    assert ledger.transcript_number(name, slug) == number


def test_topics_whose_slugs_look_alike_each_keep_their_own_transcripts(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert pipeline.add_topic(job_for(), tree, "Members 2", "It matters.", FakeLLM([BARE])).ok
    assert again(tree, "members_2", THIRD, [{"edges": []}, refit("members_2")[1]]).ok
    assert again(tree, "members", AGAIN).ok
    plan = Plan.load(tree)
    ours, theirs = plan.research_of("members"), plan.research_of("members_2")
    assert ours is not None and theirs is not None
    assert (ours.transcript, theirs.transcript) == ("members.2.jsonl", "members_2.jsonl")
    assert ([f.url for f in ours.fetches], [f.url for f in theirs.fetches]) == ([OTHER], [THIRD_URL])
    # The newer topic's record, pointed at the older topic's second transcript, is no evidence.
    lent = theirs.model_copy(update={"transcript": ours.transcript, "sha256": ours.sha256})
    forged = plan.revised(research=[lent if r.topic == "members_2" else r for r in plan.research])
    record = ledger.reconciled(forged, tree).research_of("members_2")
    assert record is not None and (record.state, record.failure) == ("failed", ledger.NO_EVIDENCE)
    assert not verify.verdict(ledger.reconciled(forged, tree), render.render(forged)).ok


def test_a_record_under_a_name_that_only_looks_like_a_topic_vouches_for_no_topic(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert again(tree, "members", AGAIN).ok
    plan = Plan.load(tree)
    ghost = [r.model_copy(update={"topic": "members.2"}) if r.topic == "members" else r for r in plan.research]
    redrawn = ledger.reconciled(plan.revised(research=ghost), tree)
    record = redrawn.research_of("members.2")
    assert record is not None and record.state == "nothing cited"
    result = verify.verdict(redrawn, render.render(redrawn))
    assert result.named(verify.FAILED) == ["sources_fetched"]
    assert "topic members cites s2, which its own research never fetched" in result.report()


def test_a_transcript_left_by_a_failed_landing_vouches_for_nothing_until_it_lands(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    assert again(tree, "members", AGAIN).ok
    with pytest.raises(pipeline.PlanRefused, match="Its transcript is kept"):
        again(tree, "members", THIRD, [LLMError("out of credit")])
    held = snapshot(tree)
    assert ".protopilot/research/members.3.jsonl" in held
    record = ledger.reconciled(Plan.load(tree), tree).research_of("members")
    assert record is not None
    assert (record.transcript, [f.url for f in record.fetches]) == ("members.2.jsonl", [OTHER])
    assert pipeline.rerender(job_for(), tree).ok and snapshot(tree) == held
    assert pipeline.research_topic(job_for(), tree, "members", NeverAsked(refit())).ok
    plan = Plan.load(tree)
    landed = plan.research_of("members")
    assert landed is not None
    assert (landed.transcript, [f.url for f in landed.fetches]) == ("members.3.jsonl", [THIRD_URL])
    assert [f.text for f in plan.topics[0].findings] == ["Third."]
    assert (ledger.research_dir(tree) / "members.2.jsonl").is_file()


# -- put-back, whichever page the write dies on ---------------------------


def _answer(tree: Path):
    return pipeline.answer(job_for(), tree, {"Who runs it?": "Volunteers"})


def _rename(tree: Path):
    return pipeline.rename_topic(job_for(), tree, "operations", "Keeping it going")


def _drop(tree: Path):
    return pipeline.drop_topic(job_for(), tree, "audience", "Known.", pipeline.OfflineLLM)


def _add(tree: Path):
    return pipeline.add_topic(job_for(), tree, "Insurance", "It matters.", pipeline.OfflineLLM())


@pytest.mark.parametrize(
    ("verb", "page"),
    [
        (_rename, "dreams.md"),
        (_rename, "operations.md"),
        (_rename, "resources.md"),
        (_drop, "dreams.md"),
        (_drop, "scope.md"),
        (_drop, "first_test.md"),
        (_add, "insurance.md"),
    ],
    ids=lambda value: getattr(value, "__name__", value),
)
def test_a_write_that_dies_on_any_page_leaves_the_plan_and_every_page_as_they_were(tmp_path, monkeypatch, verb, page):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    armed = dying_write(monkeypatch, page)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        verb(tree)
    assert not armed and snapshot(tree) == before
    monkeypatch.undo()
    assert verb(tree).ok


@pytest.mark.parametrize("page", ["PLAN.md", "members.md", "lending.md"])
def test_a_research_whose_write_dies_on_any_page_keeps_only_its_transcript(tmp_path, monkeypatch, page):
    tree = researched_plan(tmp_path / "tree")
    before = snapshot(tree)
    armed = dying_write(monkeypatch, page)
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was: disk full"):
        again(tree, "members", AGAIN)
    assert not armed and changed(before, snapshot(tree)) == [".protopilot/research/members.2.jsonl"]
    monkeypatch.undo()
    assert pipeline.research_topic(job_for(), tree, "members", NeverAsked(refit())).ok


def test_an_answer_put_back_can_be_given_again(tmp_path, monkeypatch):
    tree = questioned(tmp_path / "tree")
    dying_write(monkeypatch, "PLAN.md")
    with pytest.raises(pipeline.PlanRefused, match="the tree is back as it was"):
        _answer(tree)
    monkeypatch.undo()
    assert _answer(tree).ok
    plan = Plan.load(tree)
    assert (plan.constraints, plan.questions) == (["Who runs it? Volunteers"], ["Which town?"])


# -- proto topic drop -----------------------------------------------------


def test_dropping_the_only_citer_of_the_first_source_keeps_the_other_and_its_id(tmp_path):
    tree = researched_plan(tmp_path / "tree", dict.fromkeys(SLUGS[1:], AGAIN))
    assert [(s.id, s.url) for s in Plan.load(tree).sources] == [("s1", URL), ("s2", OTHER)]
    assert pipeline.drop_topic(job_for(), tree, "members", "Known.", pipeline.OfflineLLM).ok
    plan = Plan.load(tree)
    assert [(s.id, s.url) for s in plan.sources] == [("s2", OTHER)]
    assert {i for t in plan.topics for f in t.findings for i in f.source_ids} == {"s2"}
    page = (tree / "sources.md").read_text(encoding="utf-8")
    assert OTHER in page and URL not in page
    # A page fetched later takes an id no kept source holds.
    assert again(tree, "lending", transcript(), [{"edges": []}, refit("lending")[1]]).ok
    plan = Plan.load(tree)
    assert [(s.id, s.url) for s in plan.sources] == [("s2", OTHER), ("s3", URL)]
    assert [f.source_ids for f in plan.topics[0].findings if not f.assumption] == [["s3"]]


def test_a_promoted_dream_outlives_the_drop_of_the_topic_it_extended(tmp_path):
    tree = offline_plan(tmp_path / "tree")
    assert pipeline.promote(job_for(), tree, "d1", pipeline.OfflineLLM()).ok
    grown = Plan.load(tree).topics[-1].slug
    result = invoke("topic", "drop", "audience", "--why", "Known.", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    dream = plan.dreams[0]
    assert (dream.anchor, dream.verdict, dream.promoted_to) == ("audience", "promoted", grown)
    assert grown in [t.slug for t in plan.topics] and "set aside dream d1" not in said(result)
    assert "(a dropped topic)" in (tree / "dreams.md").read_text(encoding="utf-8")


def test_dropping_the_one_topic_research_missed_makes_a_partly_researched_plan_whole(tmp_path):
    tree = researched_plan(tmp_path / "tree", {"money": LLMError("timed out")})
    assert stamp(tree).startswith("> **Partly researched.** 5 of 6 topics")
    assert pipeline.drop_topic(job_for(), tree, "money", "Later.", pipeline.OfflineLLM).ok
    assert stamp(tree) == render.RESEARCHED


# -- proto topic rename ---------------------------------------------------


def test_a_rename_of_a_researched_topic_keeps_its_record_its_links_its_step_and_its_dreams(tmp_path):
    tree = researched_plan(tmp_path / "tree")
    before, pages = Plan.load(tree), snapshot(tree)
    result = invoke("topic", "rename", "members", "The people", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    after = Plan.load(tree)
    assert [t.slug for t in after.topics] == SLUGS and after.topics[0].title == "The people"
    assert (after.research, after.edges, after.steps, after.dreams, after.sources) == (
        before.research,
        before.edges,
        before.steps,
        before.dreams,
        before.sources,
    )
    assert [d.anchor for d in after.dreams] == ["members", "members"] and after.steps[0].topic == "members"
    now = snapshot(tree)
    assert sorted(now) == sorted(pages)
    assert now[".protopilot/research/members.jsonl"] == pages[".protopilot/research/members.jsonl"]
    assert render.TOPIC_RESEARCHED in (tree / "topics" / "members.md").read_text(encoding="utf-8")
    assert verify.verdict(ledger.reconciled(after, tree), render.read(tree)).ok


# -- proto answer ---------------------------------------------------------


@pytest.mark.parametrize("number", ["0", "x", "1.5"])
def test_a_number_that_is_no_question_number_is_a_usage_error_and_changes_nothing(tmp_path, number):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", number, "--dir", str(tree), input="Volunteers\n")
    assert result.exit_code == 2 and "[N]" in result.output
    assert snapshot(tree) == before


@pytest.mark.parametrize(("args", "piped"), [(("1",), ""), ((), "Volunteers\n")], ids=["at-once", "partway"])
def test_input_that_ends_before_every_answer_is_given_changes_nothing(tmp_path, args, piped):
    tree = questioned(tmp_path / "tree")
    before = snapshot(tree)
    result = invoke("answer", *args, "--dir", str(tree), input=piped)
    assert result.exit_code == 1 and "Aborted" in result.output
    assert snapshot(tree) == before


def test_every_question_answered_from_a_pipe_leaves_none_open(tmp_path):
    tree = questioned(tmp_path / "tree")
    result = invoke("answer", "--dir", str(tree), input="  Volunteers  \nOne town\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert (plan.constraints, plan.questions) == (["Who runs it? Volunteers", "Which town? One town"], [])
    assert "2 answer(s) are constraints now, and 0 question(s) stay open." in said(result)
    again_ = invoke("answer", "1", "--dir", str(tree))
    assert again_.exit_code == 0 and "no open question" in said(again_)


# -- the partly-researched stamp ------------------------------------------


def test_topics_researched_one_at_a_time_count_up_and_the_last_makes_the_plan_whole(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    assert stamp(tree).startswith(render.NOT_RESEARCHED)
    for done, slug in enumerate(SLUGS[:-1], start=1):
        assert again(tree, slug).ok
        assert stamp(tree).startswith(f"> **Partly researched.** {done} of 6 topics are researched.")
    assert again(tree, SLUGS[-1]).ok
    assert stamp(tree) == render.RESEARCHED
    assert "not researched" not in (tree / "PLAN.md").read_text(encoding="utf-8").lower()


def test_a_citation_typed_into_a_topic_research_never_reached_stops_every_verb(tmp_path):
    tree = unresearched_plan(tmp_path / "tree")
    assert again(tree, "members").ok
    plan = Plan.load(tree)
    typed = Finding(text="Typed by hand.", assumption=False, source_ids=["s1"])
    topics = [
        t.model_copy(update={"findings": [*t.findings, typed]}) if t.slug == "lending" else t for t in plan.topics
    ]
    plan.revised(topics=topics).save(tree)
    before = snapshot(tree)
    for args in (("topic", "rename", "space", "Room"), ("topic", "drop", "space", "--why", "No.", "--offline")):
        result = invoke(*args, "--dir", str(tree))
        assert result.exit_code == 1
        assert "Red at sources_fetched" in said(result)
        assert "topic lending cites s1, which its own research never fetched" in said(result)
    assert snapshot(tree) == before


# -- proto research -------------------------------------------------------


def test_deeper_on_the_deepest_plan_is_refused_from_the_command_line_with_no_call(tmp_path, monkeypatch):
    tree = researched_plan(tmp_path / "tree")
    Plan.load(tree).revised(depth="deep").save(tree)
    before = snapshot(tree)
    llm = NeverAsked([])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    result = invoke("research", "members", "--deeper", "--backend", "claude-code", "--dir", str(tree))
    assert result.exit_code == 1
    assert "at depth deep, the most research reads" in said(result) and "No model was called." in said(result)
    assert llm.calls == [] and snapshot(tree) == before


def test_research_offline_is_refused_before_it_looks_for_a_plan_or_a_topic(tmp_path):
    result = invoke("research", "ghost", "--offline", "--deeper", "--dir", str(tmp_path))
    assert result.exit_code == 1
    assert said(result) == (
        "Error: `proto research` reads the web, and offline reads nothing. Choose a backend that researches. "
        "Nothing was changed."
    )
    assert list(tmp_path.iterdir()) == []


# -- a plan.json written before any of this -------------------------------


def old_tree(tree: Path) -> Path:
    """The fixture's plan.json with the transcripts its ledger names, drawn as `proto plan` would draw it."""
    (tree / ".protopilot").mkdir(parents=True)
    (tree / ".protopilot" / "plan.json").write_bytes(BEFORE.read_bytes())
    for slug, said_ in {"members": transcript(), "lending": AGAIN, "space": NOTHING}.items():
        ledger.write_transcript(tree, slug, said_)
    for slug in ("money", "safety"):
        ledger.write_transcript(tree, slug, transcript())
    assert pipeline.rerender(job_for(), tree).ok
    return tree


def plan_json(tree: Path) -> bytes:
    return (tree / ".protopilot" / "plan.json").read_bytes()


@pytest.mark.parametrize(
    ("args", "piped", "code"),
    [
        (("answer",), "\n", 0),
        (("answer", "2"), None, 1),
        (("topic", "rename", "members", "Members"), None, 1),
        (("topic", "rename", "ghost", "A title"), None, 1),
        (("topic", "drop", "ghost", "--why", "No.", "--offline"), None, 1),
        (("topic", "drop", "members", "--why", " ", "--offline"), None, 1),
        (("topic", "add", "Members", "--why", "It matters.", "--offline"), None, 1),
        (("topic", "add", "Insurance", "--why", " ", "--offline"), None, 1),
        (("research", "members", "--offline"), None, 1),
    ],
    ids=lambda value: " ".join(value) if isinstance(value, tuple) else None,
)
def test_an_old_plan_is_byte_identical_after_a_verb_that_does_not_change_it(tmp_path, args, piped, code):
    tree = old_tree(tmp_path / "tree")
    before = snapshot(tree)
    assert before[".protopilot/plan.json"] == BEFORE.read_bytes()
    result = invoke(*args, "--dir", str(tree), input=piped)
    assert result.exit_code == code, result.output
    assert snapshot(tree) == before


def test_an_old_plan_renamed_and_renamed_back_is_byte_identical(tmp_path):
    tree = old_tree(tmp_path / "tree")
    before = snapshot(tree)
    assert invoke("topic", "rename", "members", "The people", "--dir", str(tree)).exit_code == 0
    assert b"dropped_topics" not in plan_json(tree) and plan_json(tree) != BEFORE.read_bytes()
    assert invoke("topic", "rename", "members", "Members", "--dir", str(tree)).exit_code == 0
    assert snapshot(tree) == before


def test_an_old_plan_gains_only_the_answer_when_its_question_is_answered(tmp_path):
    tree = old_tree(tmp_path / "tree")
    assert invoke("answer", "1", "--dir", str(tree), input="Volunteers\n").exit_code == 0
    was, now = Plan.model_validate_json(BEFORE.read_bytes()), Plan.load(tree)
    assert now == was.revised(constraints=[*was.constraints, "Who runs it? Volunteers"], questions=[])
    assert b"dropped_topics" not in plan_json(tree)
