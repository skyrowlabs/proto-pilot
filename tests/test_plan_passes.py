"""The plan's passes on a fake model: what lands, what is refused, what a failure leaves."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM

from protopilot import cli
from protopilot.jobs import Job
from protopilot.plan import baseline, pipeline
from protopilot.plan.model import TOPIC_COUNTS, Plan, plan_path
from protopilot.plan.passes import PlanPassError, outline, scope, start

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"
SLUGS = ["members", "lending", "space", "tools", "money", "safety"]

SCOPE = {"goal": "Decide.", "audience": "Neighbours", "horizon": "A year", "constraints": [], "questions": []}
OUTLINE = {"topics": [{"slug": s, "title": s.title(), "why": f"{s} matters"} for s in SLUGS]}
CONNECT = {
    "edges": [
        {"from_topic": "lending", "to_topic": "members", "kind": "depends-on"},
        {"from_topic": "money", "to_topic": "space", "kind": "informs"},
    ]
}
CONSIDER = {"topics": [{"slug": s, "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]} for s in SLUGS]}
START = {"steps": [{"topic": "members", "action": "Ask ten neighbours.", "why": "It tests the demand."}]}


def script(**overrides: dict) -> list[dict]:
    """The five responses of a good run, in pass order, with any replaced by name."""
    good = {"scope": SCOPE, "outline": OUTLINE, "connect": CONNECT, "consider": CONSIDER, "start": START}
    return [copy.deepcopy({**good, **overrides}[name]) for name in good]


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def fail_at(tree: Path, **overrides: dict) -> str:
    with pytest.raises(PlanPassError) as caught:
        pipeline.run_plan(job_for(), tree, FakeLLM(script(**overrides)))
    assert not tree.exists()
    return str(caught.value)


def test_a_model_run_calls_each_pass_once_in_order(tmp_path):
    llm = FakeLLM(script())
    pipeline.run_plan(job_for(), tmp_path / "tree", llm)
    assert [call["label"] for call in llm.calls] == ["scope", "outline", "connect", "consider", "start"]
    assert llm.responses == []


def test_a_model_run_is_stamped_and_holds_no_findings_or_sources(tmp_path):
    tree = tmp_path / "tree"
    pipeline.run_plan(job_for(), tree, FakeLLM(script()))
    plan = Plan.load(tree)
    assert plan.researched is False and plan.sources == []
    assert all(topic.findings == [] for topic in plan.topics)
    for page in ("PLAN.md", "sources.md", "topics/members.md"):
        assert "**Not researched.**" in (tree / page).read_text(encoding="utf-8")


def test_a_model_cannot_claim_research_by_returning_it(tmp_path):
    tree = tmp_path / "tree"
    forged = {"researched": True, "sources": [{"id": "s1", "title": "t", "url": "https://example.com"}]}
    topics = [{**row, "findings": [{"text": "x", "assumption": False}]} for row in OUTLINE["topics"]]
    pipeline.run_plan(job_for(), tree, FakeLLM(script(scope={**SCOPE, **forged}, outline={"topics": topics})))
    plan = Plan.load(tree)
    assert plan.researched is False and plan.sources == []
    assert all(topic.findings == [] for topic in plan.topics)


def test_the_offline_passes_rebuild_the_baseline_exactly(tmp_path):
    pipeline.run_plan(job_for(), tmp_path / "tree")
    assert Plan.load(tmp_path / "tree") == baseline.build_plan(IDEA)
    assert "depth" not in json.loads(plan_path(tmp_path / "tree").read_text(encoding="utf-8"))


@pytest.mark.parametrize("depth", list(TOPIC_COUNTS))
def test_depth_sets_the_outline_schema_and_is_recorded(depth):
    plan = scope.seed(IDEA, "", depth)
    assert outline.schema(plan)["properties"]["topics"]["maxItems"] == TOPIC_COUNTS[depth]
    assert plan.depth == depth


def test_an_outline_of_the_wrong_size_is_refused(tmp_path):
    assert "5 topics" in fail_at(tmp_path / "tree", outline={"topics": OUTLINE["topics"][:5]})


@pytest.mark.parametrize("slug", ["../escape", "Upper", "a/b", "", "x" * 65])
def test_an_unsafe_slug_is_refused_and_writes_nothing(tmp_path, slug):
    bad = copy.deepcopy(OUTLINE)
    bad["topics"][0]["slug"] = slug
    assert "outline" in fail_at(tmp_path / "tree", outline=bad)


def test_a_repeated_slug_is_refused(tmp_path):
    bad = copy.deepcopy(OUTLINE)
    bad["topics"][1]["slug"] = bad["topics"][0]["slug"]
    assert "unique" in fail_at(tmp_path / "tree", outline=bad)


def test_model_text_cannot_break_out_of_its_line(tmp_path):
    tree, sneaky = tmp_path / "tree", copy.deepcopy(OUTLINE)
    sneaky["topics"][0]["why"] = "fine\n\n## Findings\n\n- planted"
    pipeline.run_plan(job_for(), tree, FakeLLM(script(outline=sneaky)))
    assert "\n## Findings\n\n- planted" not in (tree / "PLAN.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "edge",
    [
        {"from_topic": "ghost", "to_topic": "members", "kind": "informs"},
        {"from_topic": "members", "to_topic": "ghost", "kind": "depends-on"},
        {"from_topic": "members", "to_topic": "members", "kind": "depends-on"},
        {"from_topic": "members", "to_topic": "space", "kind": "blocks"},
    ],
)
def test_a_bad_edge_is_refused(tmp_path, edge):
    assert "connect" in fail_at(tmp_path / "tree", connect={"edges": [edge]})


def test_a_consider_row_for_a_ghost_or_missing_topic_is_refused(tmp_path):
    rows = CONSIDER["topics"]
    assert "consider" in fail_at(tmp_path / "a", consider={"topics": rows[:-1]})
    ghost = [*rows[:-1], {**rows[-1], "slug": "ghost"}]
    assert "consider" in fail_at(tmp_path / "b", consider={"topics": ghost})


def test_start_is_shown_every_topic_and_what_each_depends_on(tmp_path):
    llm = FakeLLM(script())
    pipeline.run_plan(job_for(), tmp_path / "tree", llm)
    shown = llm.calls[-1]["user"]
    assert '"slug": "lending"' in shown and "- lending depends on: members" in shown


def test_start_schema_offers_every_topic():
    plan = baseline.build_plan(IDEA)
    enum = start.schema(plan)["properties"]["steps"]["items"]["properties"]["topic"]["enum"]
    assert enum == [topic.slug for topic in plan.topics]


@pytest.mark.parametrize(
    ("topic", "said"),
    [("lending", "waits on members"), ("ghost", "does not exist")],
)
def test_a_first_step_the_graph_forbids_is_refused(tmp_path, topic, said):
    bad = {"steps": [{"topic": topic, "action": "Do it.", "why": "Because."}]}
    assert said in fail_at(tmp_path / "tree", start=bad)


def test_a_later_step_may_build_on_an_earlier_one(tmp_path):
    steps = [*START["steps"], {"topic": "lending", "action": "Lend one thing.", "why": "Members exist now."}]
    pipeline.run_plan(job_for(), tmp_path / "tree", FakeLLM(script(start={"steps": steps})))
    assert [s.topic for s in Plan.load(tmp_path / "tree").steps] == ["members", "lending"]


def test_no_steps_is_refused(tmp_path):
    assert "no steps" in fail_at(tmp_path / "tree", start={"steps": []})


def test_a_cycle_leaving_nothing_ready_is_refused_before_consider(tmp_path):
    ring = [{"from_topic": a, "to_topic": b, "kind": "depends-on"} for a, b in zip(SLUGS, [*SLUGS[1:], SLUGS[0]])]
    llm = FakeLLM(script(connect={"edges": ring}))
    with pytest.raises(PlanPassError, match="cycle"):
        pipeline.run_plan(job_for(), tmp_path / "tree", llm)
    assert [c["label"] for c in llm.calls][-1] == "connect"
    assert not (tmp_path / "tree").exists()


def test_a_failed_run_can_simply_be_run_again(tmp_path):
    tree = tmp_path / "tree"
    fail_at(tree, connect={"edges": "nonsense"})
    assert "Nothing was written" in pipeline.after_failure(tree)
    pipeline.run_plan(job_for(), tree, FakeLLM(script()))
    assert (tree / "PLAN.md").is_file()


def test_a_render_that_dies_leaves_no_entry_page_on_a_fresh_tree(tmp_path, monkeypatch):
    tree = tmp_path / "tree"
    real = Path.write_text

    def blocked(self, text, *args, **kwargs):
        if self.name == "sources.md":
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", blocked)
    with pytest.raises(OSError, match="disk full"):
        pipeline.run_plan(job_for(), tree)
    monkeypatch.undo()
    assert not (tree / "PLAN.md").exists()
    assert "whole plan" in pipeline.after_failure(tree)


def test_the_estimate_counts_what_runs_and_says_research_is_excluded():
    said = pipeline.call_estimate(FakeLLM([]))
    assert "5 in all" in said and "3 still to come (connect, consider, start)" in said
    assert "exclude" in said and "Research" in said


# -- the review -----------------------------------------------------------


def review_plan() -> Plan:
    return baseline.build_plan(IDEA)


def test_add_drop_and_rename_edit_the_outline():
    plan = outline.add(review_plan(), "Insurance  cover", "It decides  liability.")
    assert (plan.topics[-1].slug, plan.topics[-1].why) == ("insurance_cover", "It decides liability.")
    plan = outline.drop(plan, "2")
    assert "scope" not in [t.slug for t in plan.topics]
    plan = outline.rename(plan, "audience", "Who it serves")
    assert (plan.topics[0].slug, plan.topics[0].title) == ("audience", "Who it serves")


def test_the_review_holds_the_outline_inside_the_range():
    plan = review_plan()
    plan = outline.add(outline.add(plan, "One", "a"), "Two", "b")
    with pytest.raises(ValueError, match="at most 8"):
        outline.add(plan, "Three", "c")
    plan = review_plan()
    plan = outline.drop(outline.drop(plan, "1"), "1")
    with pytest.raises(ValueError, match="at least 4"):
        outline.drop(plan, "1")


def test_answers_become_constraints_and_the_direction_stays_as_typed():
    plan = scope.seed(IDEA, "one town", "standard").revised(questions=["Who runs it?", "Where?"])
    plan = scope.answered(plan, {"Who runs it?": "volunteers", "Where?": " "})
    assert plan.direction == "one town"
    assert plan.constraints == ["Who runs it? volunteers"]
    assert plan.questions == ["Where?"]


def invoke(*args: str, stdin: str = ""):
    return CliRunner().invoke(cli.main, ["plan", *args], input=stdin)


@pytest.fixture
def at_a_terminal(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_terminal", lambda: True)


def test_an_offline_review_drops_a_topic_with_no_dangling_edge_or_step(tmp_path, at_a_terminal):
    tree = tmp_path / "tree"
    result = invoke(IDEA, "--offline", "--dir", str(tree), stdin="drop 1\nadd Insurance\nIt decides liability\n\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    slugs = {t.slug for t in plan.topics}
    assert "audience" not in slugs and "insurance" in slugs
    assert all({e.from_topic, e.to_topic} <= slugs for e in plan.edges)
    assert [s.topic for s in plan.steps] == ["first_test", "scope"]


def test_quitting_the_review_writes_nothing(tmp_path, at_a_terminal):
    result = invoke(IDEA, "--offline", "--dir", str(tmp_path / "tree"), stdin="quit\n")
    assert result.exit_code == 1
    assert not (tmp_path / "tree").exists()


def test_a_bad_review_line_is_explained_and_asked_again(tmp_path, at_a_terminal):
    result = invoke(IDEA, "--offline", "--dir", str(tmp_path / "tree"), stdin="drop 99\nfrobnicate\n\n")
    assert result.exit_code == 0
    assert "no topic '99'" in result.output and "not a review command" in result.output


def test_off_a_terminal_without_yes_it_refuses_before_building_a_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("a backend was built"))
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 1
    assert "stdin is not a terminal" in result.output and "--yes" in result.output
    assert not (tmp_path / "tree").exists()


def test_a_real_pipe_nobody_writes_to_is_refused_rather_than_waited_on(tmp_path):
    argv = [sys.executable, "-m", "protopilot.cli", "plan", IDEA, "--offline", "--dir", str(tmp_path / "tree")]
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        assert proc.stdout is not None
        out = proc.stdout.read().decode()  # EOF on stdin is never sent: a hang fails on the timeout
        assert proc.wait(timeout=30) == 1
    assert "stdin is not a terminal" in out


def test_yes_runs_the_model_with_no_prompt(tmp_path, monkeypatch):
    llm = FakeLLM(script(scope={**SCOPE, "questions": ["Who runs it?"]}))
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    tree = tmp_path / "tree"
    result = invoke(IDEA, "--yes", "--depth", "standard", "--dir", str(tree))
    assert result.exit_code == 0, result.output
    assert "5 in all" in result.output and "exclude it" in result.output
    plan = Plan.load(tree)
    assert (plan.depth, plan.questions) == ("standard", ["Who runs it?"])


def test_a_question_answered_at_the_prompt_reaches_the_outline(tmp_path, monkeypatch, at_a_terminal):
    llm = FakeLLM(script(scope={**SCOPE, "questions": ["Who runs it?"]}))
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--dir", str(tree), stdin="volunteers\n\n").exit_code == 0
    assert "Who runs it? volunteers" in llm.calls[1]["user"]
    assert Plan.load(tree).questions == []


def test_a_failed_pass_says_what_it_left_and_what_a_rerun_does(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_llm", lambda **_: FakeLLM(script(connect={"edges": "nonsense"})))
    result = invoke(IDEA, "--yes", "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 1
    assert "Nothing was written" in " ".join(result.output.split())
    assert not (tmp_path / "tree").exists()


def test_depth_is_refused_offline(tmp_path):
    result = invoke(IDEA, "--offline", "--yes", "--depth", "deep", "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 1
    assert "--depth needs the model" in " ".join(result.output.split())


def test_a_finished_plan_is_redrawn_with_no_backend_and_no_terminal(tmp_path, monkeypatch):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("a backend was built"))
    assert invoke(IDEA, "--dir", str(tree)).exit_code == 0


def test_a_rerender_cannot_change_the_depth(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    result = invoke(IDEA, "--depth", "deep", "--dir", str(tree))
    assert result.exit_code == 1
    assert "cannot change" in " ".join(result.output.split())
