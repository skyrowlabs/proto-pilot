"""`plan.pipeline`: the events a run emits, what it refuses, and what a re-render removes."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from protopilot import cli
from protopilot.console import progress
from protopilot.jobs import Job
from protopilot.plan import pipeline, render
from protopilot.plan.model import Plan, Topic, plan_path

pytestmark = [pytest.mark.unit]

IDEA = "start a community tool library"
PLAN_JSON = ".protopilot/plan.json"
PAGES = [
    "PLAN.md",
    "topics/audience.md",
    "topics/scope.md",
    "topics/resources.md",
    "topics/operations.md",
    "topics/risks.md",
    "topics/first_test.md",
    "dreams.md",
    "sources.md",
]


def job_for(idea: str = IDEA, direction: str = "") -> Job:
    return Job(id="test", idea=idea, direction=direction)


def built(tree: Path) -> Path:
    pipeline.run_plan(job_for(), tree)
    return tree


def events(job: Job) -> list[dict]:
    """The job's events without their clock."""
    return [{k: v for k, v in event.items() if k != "at"} for event in job.events]


def kinds(job: Job) -> list[tuple[str, str]]:
    return [(e["kind"], e.get("name", "")) for e in job.events]


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


class RenderBlocked(Job):
    """Puts a directory where PLAN.md belongs as the render starts, so a real write fails."""

    def event(self, kind: str, **fields: object) -> None:
        super().event(kind, **fields)
        if kind == "pass_started" and fields["name"] == "render":
            (Path(self.project_dir) / render.PLAN_FILE).mkdir(parents=True)


# -- events ---------------------------------------------------------------


def test_a_fresh_run_emits_the_whole_sequence_in_order(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    pipeline.run_plan(job, tree)
    passes = [(n, i) for i, n in enumerate(["scope", "outline", "connect", "consider", "start"], start=1)]
    sequence = [e for e in events(job) if e["kind"] != "outline"]
    assert sequence == [
        {"kind": "plan", "passes": [name for name, _ in passes] + ["render"]},
        *(
            {"kind": kind, "name": name, "index": index, "of": 6, **extra}
            for name, index in passes
            for kind, extra in (("pass_started", {}), ("pass_done", {"files": []}))
        ),
        {"kind": "pass_started", "name": "render", "index": 6, "of": 6},
        {"kind": "pass_done", "name": "render", "index": 6, "of": 6, "files": [PLAN_JSON, *PAGES]},
        {"kind": "finished", "ok": True, "attempts": 0, "project_dir": str(tree), "run_hint": ""},
    ]


def test_a_rerender_skips_the_baseline_and_leaves_plan_json_alone(tmp_path):
    tree = built(tmp_path / "tree")
    plan_path(tree).write_text(plan_path(tree).read_text(encoding="utf-8").replace("Who it is for", "Who it serves"))
    edited = plan_path(tree).read_bytes()

    job = job_for()
    pipeline.run_plan(job, tree)

    assert [e for e in events(job) if e["kind"] in ("plan", "pass_started")] == [
        {"kind": "plan", "passes": ["render"]},
        {"kind": "pass_started", "name": "render", "index": 1, "of": 1},
    ]
    assert plan_path(tree).read_bytes() == edited
    assert "Who it serves" in (tree / "PLAN.md").read_text(encoding="utf-8")


def test_a_run_records_its_tree_and_tells_a_person_where_to_start(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    pipeline.run_plan(job, tree)
    assert job.project_dir == str(tree)
    assert job.lines[-1] == f"Plan at {tree}. Start with PLAN.md."
    assert "  pass render..." in job.lines


def test_the_console_fold_reads_a_finished_run(tmp_path):
    job, tree = job_for(), tmp_path / "tree"
    pipeline.run_plan(job, tree)
    folded = progress.fold(job.events)
    assert [(p.name, p.state) for p in folded.passes] == [
        (name, progress.DONE) for name in ("scope", "outline", "connect", "consider", "start", "render")
    ]
    assert folded.passes[-1].files == [PLAN_JSON, *PAGES]
    assert (folded.finished, folded.ok, folded.gave_up) == (True, True, False)
    assert folded.project_dir == str(tree)


# -- pass_failed ----------------------------------------------------------


def test_a_render_that_dies_reports_pass_failed_and_never_finishes(tmp_path):
    tree = built(tmp_path / "tree")
    (tree / "PLAN.md").unlink()
    (tree / "PLAN.md").mkdir()

    job = job_for()
    with pytest.raises(pipeline.PlanRefused):
        pipeline.run_plan(job, tree)

    assert kinds(job) == [("plan", ""), ("pass_started", "render"), ("pass_failed", "render")]
    failed = events(job)[-1]
    assert (failed["index"], failed["of"]) == (1, 1)
    assert "PLAN.md" in failed["error"]


def test_a_save_that_dies_fails_the_render_pass_and_writes_nothing(tmp_path):
    blocker = tmp_path / "a_file"
    blocker.write_text("in the way")

    job = job_for()
    with pytest.raises(NotADirectoryError):
        pipeline.run_plan(job, blocker / "tree")

    assert kinds(job)[-2:] == [("pass_started", "render"), ("pass_failed", "render")]
    assert blocker.read_text() == "in the way"


def test_the_console_fold_shows_a_failed_pass_as_failed_and_unfinished(tmp_path):
    tree = built(tmp_path / "tree")
    (tree / "PLAN.md").unlink()
    (tree / "PLAN.md").mkdir()
    job = job_for()
    with pytest.raises(pipeline.PlanRefused):
        pipeline.run_plan(job, tree)
    folded = progress.fold(job.events)
    assert [(p.name, p.state) for p in folded.passes] == [("render", progress.FAILED)]
    assert folded.finished is False


def test_a_render_that_dies_on_a_fresh_run_leaves_a_tree_that_rerenders(tmp_path):
    tree = tmp_path / "tree"
    blocked = RenderBlocked(id="test", idea=IDEA)
    with pytest.raises(pipeline.PlanRefused):
        pipeline.run_plan(blocked, tree)
    assert kinds(blocked)[-1] == ("pass_failed", "render")
    assert plan_path(tree).is_file()

    (tree / "PLAN.md").rmdir()
    pipeline.run_plan(job_for(), tree)
    assert snapshot(tree) == snapshot(built(tmp_path / "clean"))


def blocked_page(tree: Path) -> Path:
    (tree / "PLAN.md").unlink()
    (tree / "PLAN.md").mkdir()
    return tree / "PLAN.md"


def blocked_topic_page(tree: Path) -> Path:
    (tree / "topics" / "scope.md").unlink()
    (tree / "topics" / "scope.md").mkdir()
    return tree / "topics" / "scope.md"


def blocked_topics_folder(tree: Path) -> Path:
    shutil.rmtree(tree / "topics")
    (tree / "topics").write_text("in the way")
    return tree / "topics"


@pytest.mark.parametrize("block", [blocked_page, blocked_topic_page, blocked_topics_folder])
def test_a_name_in_the_way_of_a_page_reaches_the_cli_as_a_sentence(tmp_path, block):
    tree = built(tmp_path / "tree")
    blocker = block(tree)
    before = snapshot(tree)

    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])

    said = " ".join(result.output.split())
    assert result.exit_code == 1
    assert f"a page needs this name: {blocker}." in said
    assert "Move it out of the way and rerun" in said
    assert "Error: PlanRefused" not in said and "Errno" not in said and "maybe not every page" not in said
    assert snapshot(tree) == before


# -- refusals, reached through run_plan -----------------------------------


def assert_refused(job: Job, tree: Path, message: str) -> None:
    """Refused before anything happened: no event, no tree recorded, no byte moved."""
    before = snapshot(tree)
    with pytest.raises(pipeline.PlanRefused, match=message):
        pipeline.run_plan(job, tree)
    assert job.events == []
    assert job.project_dir == ""
    assert snapshot(tree) == before


def test_run_plan_refuses_a_directory_holding_no_plan(tmp_path):
    (tmp_path / "keep.txt").write_text("mine")
    assert_refused(job_for(), tmp_path, "holds no plan; refusing to overwrite it")


def test_run_plan_refuses_an_empty_directory(tmp_path):
    assert_refused(job_for(), tmp_path, "holds no plan")


def test_run_plan_refuses_a_path_that_is_a_file(tmp_path):
    target = tmp_path / "a_file"
    target.write_text("mine")
    with pytest.raises(pipeline.PlanRefused, match="holds no plan"):
        pipeline.run_plan(job_for(), target)
    assert target.read_text() == "mine"


def test_run_plan_refuses_a_plan_for_another_idea_and_names_it(tmp_path):
    tree = built(tmp_path / "tree")
    assert_refused(job_for("another idea"), tree, f"holds a plan for '{IDEA}' with no direction")


def test_run_plan_refuses_a_plan_with_another_direction_and_names_it(tmp_path):
    tree = tmp_path / "tree"
    pipeline.run_plan(job_for(direction="one town"), tree)
    assert_refused(job_for(direction="two towns"), tree, "with direction 'one town'")


def test_dropping_the_direction_is_also_another_plan(tmp_path):
    tree = tmp_path / "tree"
    pipeline.run_plan(job_for(direction="one town"), tree)
    assert_refused(job_for(), tree, "with direction 'one town'")


def test_the_same_idea_spelt_with_other_whitespace_is_the_same_plan(tmp_path):
    tree = built(tmp_path / "tree")
    job = job_for("  start  a community\ttool library ")
    pipeline.run_plan(job, tree)
    assert kinds(job)[-1] == ("finished", "")


# -- corrupt plan.json ----------------------------------------------------


def valid_json_with(tree: Path, old: str, new: str) -> bytes:
    return plan_path(tree).read_text(encoding="utf-8").replace(old, new, 1).encode("utf-8")


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda tree: b"{ this is not json",
        lambda tree: b"",
        lambda tree: b"[]",
        lambda tree: b"{}",
        lambda tree: b"\xff\xfe not utf-8",
        lambda tree: valid_json_with(tree, '"researched"', '"researchd"'),
        lambda tree: valid_json_with(tree, '"slug": "audience"', '"slug": "../../evil"'),
        lambda tree: valid_json_with(tree, '"slug": "scope"', '"slug": "audience"'),
    ],
    ids=["syntax", "empty", "list", "no-fields", "not-utf8", "unknown-field", "traversal", "duplicate-topic"],
)
def test_a_corrupt_plan_is_refused_by_name_and_left_for_a_person(tmp_path, corrupt):
    tree = built(tmp_path / "tree")
    plan_path(tree).write_bytes(corrupt(tree))
    assert_refused(job_for(), tree, f"{plan_path(tree)} cannot be read as a plan")
    assert not (tmp_path / "evil.md").exists()


def test_a_plan_json_that_is_a_directory_is_refused(tmp_path):
    plan_path(tmp_path).mkdir(parents=True)
    with pytest.raises(pipeline.PlanRefused, match="cannot be read as a plan"):
        pipeline.run_plan(job_for(), tmp_path)


def test_a_corrupt_plan_reaches_the_cli_as_a_sentence_not_a_traceback(tmp_path):
    tree = built(tmp_path / "tree")
    plan_path(tree).write_text("{ this is not json")
    result = CliRunner().invoke(cli.main, ["plan", IDEA, "--offline", "--yes", "--dir", str(tree)])
    assert result.exit_code == 1
    assert "cannot be read as a plan" in " ".join(result.output.split())
    assert isinstance(result.exception, SystemExit)
    assert plan_path(tree).read_text() == "{ this is not json"


# -- stale pages ----------------------------------------------------------


def without_topic(tree: Path, slug: str) -> None:
    plan = Plan.load(tree)
    plan.topics = [t for t in plan.topics if t.slug != slug]
    plan.save(tree)


def test_a_rerender_removes_the_page_of_a_topic_the_plan_lost(tmp_path):
    tree = built(tmp_path / "tree")
    without_topic(tree, "risks")
    pipeline.run_plan(job_for(), tree)
    assert sorted(p.name for p in (tree / "topics").iterdir()) == sorted(
        Path(page).name for page in PAGES if page.startswith("topics/") and "risks" not in page
    )


def test_a_renamed_topic_moves_its_page(tmp_path):
    tree = built(tmp_path / "tree")
    plan = Plan.load(tree)
    plan.topics.append(Topic(slug="funding", title="Funding", why="Who pays."))
    plan.topics = [t for t in plan.topics if t.slug != "resources"]
    plan.save(tree)
    pipeline.run_plan(job_for(), tree)
    assert (tree / "topics" / "funding.md").is_file()
    assert not (tree / "topics" / "resources.md").exists()


def test_a_rerender_leaves_everything_but_stale_topic_pages_alone(tmp_path):
    tree = built(tmp_path / "tree")
    kept = {
        "topics/notes.txt": b"mine",
        "topics/diagram.png": b"\x89PNG",
        "topics/UPPER.MD": b"not matched",
        "topics/drafts/old.md": b"one level down",
        "notes.md": b"beside the plan",
    }
    for name, data in kept.items():
        (tree / name).parent.mkdir(exist_ok=True)
        (tree / name).write_bytes(data)
    without_topic(tree, "risks")

    pipeline.run_plan(job_for(), tree)

    after = snapshot(tree)
    assert {name: after.get(name) for name in kept} == kept
    assert "topics/risks.md" not in after


def test_a_directory_named_like_a_page_does_not_stop_a_rerender(tmp_path):
    tree = tmp_path / "tree"
    pipeline.run_plan(Job(id="1", idea="x"), tree)
    (tree / "topics" / "drafts.md").mkdir()
    pipeline.run_plan(Job(id="2", idea="x"), tree)
    assert (tree / "topics" / "drafts.md").is_dir()
