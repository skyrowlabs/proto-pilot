"""Research holes the tester found: the init check, the findings count, markdown from pages, forged state, URLs, resume."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plan_script import IDEA, script
from research_script import OTHER, URL, ResearchingLLM, assumed, cited, fetched, transcript

from protopilot.jobs import Job
from protopilot.llm import LLMError, OfflineLLM, research_result
from protopilot.plan import ledger, pipeline, render
from protopilot.plan.model import Plan, Topic, plan_path
from protopilot.plan.passes import research

pytestmark = [pytest.mark.unit]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def edited(tree: Path, change) -> None:  # noqa: ANN001
    data = json.loads(plan_path(tree).read_text(encoding="utf-8"))
    change(data)
    plan_path(tree).write_text(json.dumps(data), encoding="utf-8")


def topic(data: dict, slug: str) -> dict:
    return next(t for t in data["research"] if t["topic"] == slug)


# -- 1. the init check ----------------------------------------------------


def init_line(**fields: object) -> str:
    return json.dumps({"type": "system", "subtype": "init", **fields}) + "\n"


@pytest.mark.parametrize(
    "said",
    [
        init_line(mcp_servers=[]) + transcript().split("\n", 1)[1],
        init_line(tools=None, mcp_servers=[]) + transcript().split("\n", 1)[1],
        init_line(tools=["WebFetch"]) + transcript().split("\n", 1)[1],
        transcript() + init_line(tools=["Bash"], mcp_servers=[]),
        transcript() + init_line(tools=["WebFetch"], mcp_servers=[{"name": "drive"}]),
    ],
    ids=["tools-missing", "tools-null", "servers-missing", "a-later-init-holds-bash", "a-later-init-holds-mcp"],
)
def test_every_init_event_must_list_only_the_web(said: str):
    with pytest.raises(LLMError):
        research_result(said, "r")


# -- 2. the findings count -------------------------------------------------


def outline_plan() -> Plan:
    return Plan(slug="p", title="P", idea=IDEA, depth="shallow", topics=[Topic(slug="members", title="M", why="w")])


def test_more_findings_than_the_depth_allows_are_refused():
    with pytest.raises(ValueError, match="past the 4 this depth allows"):
        research.apply(outline_plan(), "members", {"findings": [assumed(f"F{n}.") for n in range(5)]}, [])


def test_a_replayed_transcript_past_the_count_fails_its_topic_on_resume(tmp_path):
    tree = tmp_path / "tree"
    with pytest.raises(RuntimeError):
        pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {"lending": RuntimeError("killed")}))
    long = transcript(findings=[assumed(f"F{n}.") for n in range(9)])
    (ledger.research_dir(tree) / "members.jsonl").write_text(long, encoding="utf-8")
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script()[2:], {})).ok
    assert Plan.load(tree).research_of("members").state == "failed"  # type: ignore[union-attr]


# -- 3. markdown from pages -----------------------------------------------

EVIL = "not a url\n## Injected heading\n[click](javascript:alert(1))"


def evil_tree(tmp_path: Path) -> Path:
    said = transcript(findings=[cited(title="x](https://evil.test) [y"), cited("Second.\n# H", url=EVIL), assumed()])
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {"members": said})).ok
    return tree


def test_nothing_a_page_or_model_wrote_opens_a_link_or_a_heading_in_sources(tmp_path):
    page = (evil_tree(tmp_path) / "sources.md").read_text(encoding="utf-8")
    assert "](https://evil.test)" not in page.replace("\\]", "")
    assert "\n## Injected" not in page and "](javascript:" not in page
    assert "`not%20a%20url%20##%20Injected" in page


def test_a_finding_is_one_escaped_line_on_its_topic_page(tmp_path):
    page = (evil_tree(tmp_path) / "topics" / "members.md").read_text(encoding="utf-8")
    assert "\n# H" not in page and "Second. # H" in page


def test_md_text_escapes_what_markdown_reads_as_syntax():
    assert render.md_text("a [b](c) *d*\n`e`") == "a \\[b\\](c) \\*d\\* \\`e\\`"


# -- 4. a hand edit cannot make a topic researched ------------------------


def researched_tree(tmp_path: Path, scripted: dict) -> Path:
    tree = tmp_path / "tree"
    assert pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), scripted)).ok
    return tree


def test_a_failed_record_flipped_to_researched_is_drawn_as_failed(tmp_path):
    tree = researched_tree(tmp_path, {"money": LLMError("net")})
    edited(tree, lambda d: topic(d, "money").update(state="researched", failure=""))
    pipeline.rerender(job_for(), tree)
    page = (tree / "topics" / "money.md").read_text(encoding="utf-8")
    assert render.TOPIC_RESEARCHED not in page and ledger.NO_EVIDENCE in page


def test_a_record_borrowing_another_topics_transcript_backs_nothing(tmp_path):
    tree = researched_tree(tmp_path, {"money": LLMError("net")})

    def borrow(data: dict) -> None:
        theirs = topic(data, "members")
        topic(data, "money").update(state="researched", transcript=theirs["transcript"], sha256=theirs["sha256"])
        page = next(t for t in data["topics"] if t["slug"] == "money")
        page["findings"] = [{"text": "Borrowed.", "assumption": False, "source_ids": ["s1"]}]

    edited(tree, borrow)
    assert pipeline.rerender(job_for(), tree).stage == "sources_fetched"


def test_a_citation_typed_onto_a_topic_that_never_fetched_it_is_red(tmp_path):
    tree = researched_tree(tmp_path, {"money": transcript(findings=[assumed()], fetches=[fetched(OTHER)])})

    def cite(data: dict) -> None:
        page = next(t for t in data["topics"] if t["slug"] == "money")
        page["findings"][0].update(assumption=False, source_ids=["s1"])

    edited(tree, cite)
    result = pipeline.rerender(job_for(), tree)
    assert result.stage == "sources_fetched" and "money cites s1" in result.report()


# -- 5. URLs with parentheses ---------------------------------------------


def test_a_url_with_balanced_parentheses_can_be_cited():
    wiki = "https://en.wikipedia.org/wiki/Sourdough_(bread)"
    plan, _ = research.apply(
        outline_plan(), "members", {"findings": [cited(url=wiki)]}, [ledger.judged(wiki, "A summary.", None, False)]
    )
    assert [s.url for s in plan.sources] == [wiki]
    assert "(https://en.wikipedia.org/wiki/Sourdough_%28bread%29)" in render.render(plan)["sources.md"]


@pytest.mark.parametrize("url", ["https://x.test/a)b", "https://x.test/(a", "https://x.test/((a))"])
def test_an_unbalanced_or_nested_parenthesis_is_still_refused(url: str):
    plan, _ = research.apply(
        outline_plan(), "members", {"findings": [cited(url=url)]}, [ledger.judged(url, "S.", None, False)]
    )
    assert plan.sources == []


# -- 6. resume guards in the pipeline -------------------------------------


def stopped(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    with pytest.raises(RuntimeError):
        pipeline.run_plan(job_for(), tree, ResearchingLLM(script(), {"lending": RuntimeError("killed")}))
    return tree


@pytest.mark.parametrize(
    ("options", "said"),
    [({"researching": False}, "--no-research"), ({"depth": "deep"}, "at depth standard")],
    ids=["no-research", "another-depth"],
)
def test_the_pipeline_refuses_a_resume_that_would_change_the_run(tmp_path, options: dict, said: str):
    tree = stopped(tmp_path)
    with pytest.raises(pipeline.PlanRefused, match=said):
        pipeline.run_plan(job_for(), tree, ResearchingLLM(script()[2:], {}), **options)
    assert (ledger.research_dir(tree) / ledger.DRAFT_FILE).is_file() and not plan_path(tree).exists()


def test_the_pipeline_refuses_to_resume_offline(tmp_path):
    tree = stopped(tmp_path)
    with pytest.raises(pipeline.PlanRefused, match="offline cannot research"):
        pipeline.run_plan(job_for(), tree, OfflineLLM())
    assert not plan_path(tree).exists()


# -- the heuristic, with no status code -----------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Request failed with status code 403",
        "403 Forbidden",
        "Page not found",
        "Error: Access denied",
        "Just a moment... Enable JavaScript and cookies to continue",
    ],
)
def test_a_failure_said_in_words_is_not_usable(text: str):
    assert not ledger.judged(URL, text, None, False).usable
