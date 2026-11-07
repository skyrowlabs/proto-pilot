"""A red plan reads red everywhere, a re-render judges what it finds, and no check claims what it never read."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, edge, repair_of, script, step

from protopilot import cli
from protopilot.console import progress
from protopilot.jobs import Job
from protopilot.plan import pipeline, render, verify
from protopilot.plan.model import Plan, plan_path
from protopilot.plan.passes import repair

pytestmark = [pytest.mark.unit]

GOOD_EDGES = GOOD["connect"]["edges"]
OUT_OF_ORDER = {"steps": [step("lending"), step("members")]}
LOOP = [edge("lending", "space"), edge("space", "lending")]
TOPIC_PAGE = "topics/members.md"


def job_for() -> Job:
    return Job(id="test", idea=IDEA)


def run(tree: Path, *repairs: dict, **overrides: object) -> tuple[Job, verify.PlanVerdict]:
    job = job_for()
    return job, pipeline.run_plan(job, tree, FakeLLM([*script(**overrides), *repairs]))


def rerun(tree: Path) -> tuple[Job, verify.PlanVerdict]:
    job = job_for()
    return job, pipeline.run_plan(job, tree, FakeLLM([]))


def kinds(job: Job) -> list[str]:
    return [event["kind"] for event in job.events]


def page(tree: Path, name: str = "PLAN.md") -> str:
    return (tree / name).read_text(encoding="utf-8")


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def offline_tree(tree: Path) -> Path:
    assert pipeline.run_plan(job_for(), tree).ok
    return tree


def edit_plan_json(tree: Path, **changes: object) -> None:
    doc = json.loads(plan_path(tree).read_text(encoding="utf-8"))
    plan_path(tree).write_text(json.dumps({**doc, **changes}), encoding="utf-8")


@pytest.fixture
def no_backend(monkeypatch):
    def refuse(**_: object) -> None:
        raise AssertionError("a re-render built a backend")

    monkeypatch.setattr(cli, "build_llm", refuse)


def proto_plan(tree: Path, *extra: str):
    return CliRunner().invoke(cli.main, ["plan", IDEA, "--dir", str(tree), *extra])


def said(result) -> str:
    return " ".join(result.output.split())


# -- the floor says red everywhere ----------------------------------------

STILL_RED = repair_of(GOOD_EDGES, ["lending", "members", "space"])
FLOORS = {
    "out-of-order-no-answer-left": ({"start": OUT_OF_ORDER}, []),
    "loop-repair-changed-nothing": ({"connect": {"edges": LOOP}}, [repair_of(LOOP, ["members"])]),
    "repair-landed-and-stayed-red": ({"start": OUT_OF_ORDER}, [STILL_RED]),
}


@pytest.fixture(params=FLOORS, ids=list(FLOORS))
def floor(request, tmp_path) -> tuple[Path, Job, verify.PlanVerdict]:
    overrides, answers = FLOORS[request.param]
    tree = tmp_path / "tree"
    job, result = run(tree, *answers, **overrides)
    return tree, job, result


def test_a_floor_never_logs_a_green_word(floor):
    _, job, _ = floor
    logged = "\n".join(job.lines)
    for claim in ("Green", "Plan at", "no check failed", "coherent and traceable"):
        assert claim not in logged


def test_a_floor_emits_no_passing_verification(floor):
    _, job, _ = floor
    assert "verify_passed" not in kinds(job)
    assert kinds(job).count("exhausted") == 1
    assert job.events[-1]["kind"] == "finished" and job.events[-1]["ok"] is False


def test_a_floor_counts_the_same_number_in_every_place_it_gives_one(floor):
    tree, job, result = floor
    checks = kinds(job).count("verify_started")
    assert job.events[-1]["attempts"] == checks
    assert f"Not verified: red at {result.stage} after {checks} check(s)." in job.lines
    assert f"could not get this plan to green in {checks} check(s)" in page(tree, "RUNBOOK.md")


def test_a_floor_writes_no_green_word_into_any_file(floor):
    tree, _, _ = floor
    for name, data in snapshot(tree).items():
        assert b"Green" not in data, name
        assert b"coherent and traceable" not in data, name


def test_a_floor_keeps_no_verified_flag_in_plan_json(floor):
    tree, _, _ = floor
    assert not [key for key in json.loads(plan_path(tree).read_text(encoding="utf-8")) if "verif" in key]


def test_a_floor_says_what_is_wrong_in_the_runbook_and_points_to_it_from_the_entry_page(floor):
    tree, _, result = floor
    entry, said_there = page(tree), page(tree, "RUNBOOK.md")
    assert render.NOT_VERIFIED in entry and render.NOT_RESEARCHED in entry
    assert entry.index(render.NOT_VERIFIED) < entry.index("## The idea")
    assert f"[{result.stage}]" in said_there and "Nothing here is verified" in said_there


def test_a_floor_exits_one_and_says_so_from_the_real_command(tmp_path, monkeypatch):
    llm = FakeLLM([*script(start=OUT_OF_ORDER), STILL_RED, STILL_RED])
    monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
    tree = tmp_path / "tree"
    result = proto_plan(tree, "--yes")
    assert result.exit_code == 1
    assert "Not verified: red at start_order after 2 check(s)." in said(result)
    assert f"The tree is at {tree}" in said(result)
    assert "Green" not in said(result) and "Plan at" not in said(result)


def test_what_was_tried_lists_each_attempt_in_order_with_its_outcome(tmp_path):
    tree = tmp_path / "tree"
    rejected, landed = repair_of([], ["members"]), STILL_RED
    run(tree, rejected, landed, landed, start=OUT_OF_ORDER)
    said_there = page(tree, "RUNBOOK.md")
    assert "1. attempt 1 (start_order): rejected, because it removed edges on no loop" in said_there
    assert "2. attempt 2 (start_order): steps now lending, members, space" in said_there
    assert "3. attempt 3 (start_order): the repair changed nothing" in said_there
    assert "4. attempt" not in said_there


def test_model_text_in_a_runbook_cannot_hide_what_follows_it(tmp_path):
    tree = tmp_path / "tree"

    class Hostile(FakeLLM):
        def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
            if label == "repair":
                raise RuntimeError("<!-- swallow the rest")
            return super().structured(system=system, user=user, schema=schema, label=label)

    pipeline.run_plan(job_for(), tree, Hostile(script(start=OUT_OF_ORDER)))
    said_there = page(tree, "RUNBOOK.md")
    assert "<!--" not in said_there and "&lt;!-- swallow the rest" in said_there


def test_braces_in_what_failed_do_not_break_the_runbook(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    doc = json.loads(plan_path(tree).read_text(encoding="utf-8"))
    doc["topics"][0]["findings"] = [{"text": "a {placeholder} and {0}", "assumption": False}]
    plan_path(tree).write_text(json.dumps(doc), encoding="utf-8")
    _, result = rerun(tree)
    assert result.stage == "findings_traced"
    assert "a {placeholder} and {0}" in page(tree, "RUNBOOK.md")


def test_a_floor_whose_write_dies_leaves_no_entry_page_to_read_as_finished(tmp_path, monkeypatch):
    tree, real = tmp_path / "tree", Path.write_text

    def dies(self, text, *args, **kwargs):
        if self.name == render.SOURCES_FILE:
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", dies)
    job = job_for()
    with pytest.raises(OSError, match="disk full"):
        pipeline.run_plan(job, tree, FakeLLM(script(start=OUT_OF_ORDER)))
    assert not (tree / "PLAN.md").exists()
    assert "finished" not in kinds(job) and kinds(job)[-1] == "pass_failed"

    monkeypatch.setattr(Path, "write_text", real)
    _, result = rerun(tree)
    assert not result.ok and render.NOT_VERIFIED in page(tree)


# -- green after a floor --------------------------------------------------


def mended_by_hand(tree: Path) -> None:
    plan = Plan.load(tree)
    plan.edges = [e for e in plan.edges if e.from_topic != "space"]
    plan.save(tree)


def test_a_mended_plan_prints_green_exits_zero_and_needs_no_backend(tmp_path, monkeypatch):
    tree = tmp_path / "tree"
    run(tree, connect={"edges": LOOP})
    mended_by_hand(tree)
    monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("a re-render built a backend"))
    result = proto_plan(tree)
    assert result.exit_code == 0, result.output
    assert "Green: this plan is coherent and traceable" in said(result)
    assert not (tree / "RUNBOOK.md").exists()
    assert render.NOT_VERIFIED not in page(tree) and "RUNBOOK" not in page(tree)


def test_a_mended_plan_draws_what_a_never_red_plan_draws(tmp_path):
    tree = tmp_path / "tree"
    run(tree, connect={"edges": LOOP})
    mended_by_hand(tree)
    rerun(tree)
    assert render.read(tree) == render.render(Plan.load(tree))


def test_a_directory_named_runbook_survives_a_green_rerender(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    (tree / "RUNBOOK.md").mkdir()
    (tree / "RUNBOOK.md" / "keep.txt").write_text("mine", encoding="utf-8")
    _, result = rerun(tree)
    assert result.ok
    assert (tree / "RUNBOOK.md" / "keep.txt").read_text(encoding="utf-8") == "mine"


# -- a re-render judges the plan it finds ---------------------------------

CORRUPT: dict[str, bytes] = {
    "truncated": b'{"slug":',
    "empty": b"",
    "a-list": b"[]",
    "not-utf8": b"\xff\xfe\x00",
    "a-field-it-does-not-know": b'{"verified": true}',
}


@pytest.mark.parametrize("data", CORRUPT.values(), ids=list(CORRUPT))
def test_a_corrupt_plan_is_refused_and_nothing_in_the_tree_moves(tmp_path, no_backend, data):
    tree = offline_tree(tmp_path / "tree")
    plan_path(tree).write_bytes(data)
    before = snapshot(tree)
    result = proto_plan(tree, "--yes")
    assert result.exit_code == 1
    assert "cannot be read as a plan" in said(result)
    assert snapshot(tree) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"edges": [{"from_topic": "scope", "to_topic": "audience", "kind": "needs"}]},
        {"topics": [{"slug": "../evil", "title": "t", "why": "w"}]},
        {"topics": [{"slug": "a", "title": "t", "why": "w"}, {"slug": "a", "title": "t", "why": "w"}]},
    ],
    ids=["unknown-kind", "slug-escapes-the-tree", "two-topics-one-file"],
)
def test_a_plan_unsafe_to_store_is_refused_rather_than_judged(tmp_path, no_backend, changes):
    tree = offline_tree(tmp_path / "tree")
    edit_plan_json(tree, **changes)
    before = snapshot(tree)
    assert proto_plan(tree).exit_code == 1
    assert snapshot(tree) == before
    assert not (tree.parent / "evil.md").exists()


GHOST_EDGE = {"from_topic": "scope", "to_topic": "ghost", "kind": "informs"}
SELF_LOOP = {"from_topic": "scope", "to_topic": "scope", "kind": "depends-on"}
TYPED = {"id": "s1", "title": "A study", "url": "https://example.com"}
SHAPELESS = {"id": "d", "title": "t", "what_if": "w", "lens": "l", "anchor": "ghost", "takes": "x"}


@pytest.mark.parametrize(
    ("changes", "stage"),
    [
        ({"edges": [GHOST_EDGE]}, "topic_map"),
        ({"edges": [SELF_LOOP]}, "no_cycles"),
        ({"researched": True}, "sources_fetched"),
        ({"sources": [TYPED]}, "sources_fetched"),
        ({"steps": []}, "start_order"),
        ({"topics": [], "edges": [], "steps": []}, "start_order"),
        ({"dreams": [SHAPELESS]}, "dreams_shaped"),
    ],
    ids=["ghost-edge", "self-loop", "researched-no-source", "typed-source", "no-steps", "no-topics", "bad-dream"],
)
def test_a_hand_edit_goes_to_the_floor_with_no_model_and_exit_one(tmp_path, no_backend, changes, stage):
    tree = offline_tree(tmp_path / "tree")
    edit_plan_json(tree, **changes)
    result = proto_plan(tree)
    assert result.exit_code == 1
    assert f"Not verified: red at {stage} after 1 check(s)." in said(result)
    assert f"[{stage}]" in page(tree, "RUNBOOK.md")
    assert "A re-render calls no model, so no repair ran." in page(tree, "RUNBOOK.md")
    assert render.NOT_VERIFIED in page(tree)


def test_a_rerender_needs_no_terminal_and_no_yes(tmp_path, no_backend):
    tree = offline_tree(tmp_path / "tree")
    assert proto_plan(tree).exit_code == 0


def test_a_rerender_leaves_a_green_tree_byte_for_byte(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    before = snapshot(tree)
    rerun(tree)
    assert snapshot(tree) == before


def test_a_rerender_does_not_rewrite_plan_json(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    doc = plan_path(tree).read_text(encoding="utf-8").replace('"steps": [', '"steps":    [')
    plan_path(tree).write_text(doc, encoding="utf-8")
    rerun(tree)
    assert plan_path(tree).read_text(encoding="utf-8") == doc


def phase_three_tree(tree: Path) -> Path:
    """What Phase 3 left: no runbook, no banner, and nothing that ever checked it."""
    offline_tree(tree)
    assert not (tree / "RUNBOOK.md").exists()
    return tree


def test_a_phase_three_tree_that_holds_up_goes_green_and_is_unchanged(tmp_path):
    tree = phase_three_tree(tmp_path / "tree")
    before = snapshot(tree)
    _, result = rerun(tree)
    assert result.ok and snapshot(tree) == before


def test_a_phase_three_tree_with_a_real_fault_goes_red_and_gains_a_banner(tmp_path):
    tree = phase_three_tree(tmp_path / "tree")
    plan = Plan.load(tree)
    plan.steps = list(reversed(plan.steps))
    plan.save(tree)
    assert render.NOT_VERIFIED not in page(tree)
    _, result = rerun(tree)
    assert not result.ok
    assert render.NOT_VERIFIED in page(tree) and (tree / "RUNBOOK.md").is_file()


def test_a_stale_runbook_and_banner_go_when_the_plan_is_green(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    plan = Plan.load(tree)
    render.write(plan, tree, "# Runbook\n\nstale\n")
    assert render.NOT_VERIFIED in page(tree)
    _, result = rerun(tree)
    assert result.ok
    assert not (tree / "RUNBOOK.md").exists() and render.NOT_VERIFIED not in page(tree)


def test_a_stale_runbook_is_rewritten_when_the_plan_is_red_for_another_reason(tmp_path):
    tree = tmp_path / "tree"
    run(tree, connect={"edges": LOOP})
    assert "[no_cycles]" in page(tree, "RUNBOOK.md")
    mended_by_hand(tree)
    edit_plan_json(tree, steps=[])
    rerun(tree)
    said_there = page(tree, "RUNBOOK.md")
    assert "[start_order]" in said_there and "[no_cycles]" not in said_there


# -- no subject is never held ---------------------------------------------

INFORMS_ONLY = [edge("money", "space", "informs")]


def no_subject_run(tree: Path) -> tuple[Job, verify.PlanVerdict]:
    return run(tree, connect={"edges": INFORMS_ONLY})


def test_an_empty_check_is_absent_from_held_in_the_green_line(tmp_path):
    _, result = no_subject_run(tmp_path / "tree")
    held = result.summary.split("Held: ")[1].split(".")[0].split(", ")
    empty = result.summary.split("proved nothing: ")[1].split(".")[0].split(", ")
    assert held == ["topic_map", "start_order"]
    assert empty == ["no_cycles", "findings_traced", "sources_fetched", "dreams_shaped", "dreams_apart"]


def test_the_event_and_the_log_name_the_same_empty_checks_as_the_verdict(tmp_path):
    job, result = no_subject_run(tmp_path / "tree")
    passed = next(event for event in job.events if event["kind"] == "verify_passed")
    assert passed["no_subject"] == result.named(verify.NO_SUBJECT)
    assert passed["summary"] == result.summary
    assert result.summary in job.lines


def test_the_runbook_names_each_empty_check_and_never_lists_it_as_wrong(tmp_path):
    tree = tmp_path / "tree"
    _, result = run(tree, connect={"edges": INFORMS_ONLY}, start={"steps": [step("members"), step("members")]})
    said_there = page(tree, "RUNBOOK.md")
    wrong = said_there.split("## Still wrong")[1].split("## What was tried")[0]
    empty = said_there.split("## Checks with no subject")[1].split("## What to do")[0]
    for name in result.named(verify.NO_SUBJECT):
        assert f"- {name}: " in empty and f"[{name}]" not in wrong
    assert "Held" not in said_there


def test_a_runbook_with_nothing_empty_says_none():
    plan = Plan.model_validate(
        {
            "slug": "x",
            "title": "T",
            "idea": IDEA,
            "topics": [
                {
                    "slug": "a",
                    "title": "A",
                    "why": "W",
                    "findings": [{"text": "F", "assumption": False, "source_ids": ["s1"]}],
                }
            ],
            "edges": [{"from_topic": "a", "to_topic": "a", "kind": "depends-on"}],
            "steps": [{"topic": "a", "action": "Do.", "why": "Now."}],
            "sources": [{"id": "s1", "title": "S", "url": "u", "fetched": True}],
            "dreams": [
                {
                    "id": "d",
                    "title": "Long enough to be read at all",
                    "what_if": "x",
                    "lens": "l",
                    "anchor": "a",
                    "takes": "y",
                    "verdict": "proposed",
                }
            ],
        }
    )
    said_there = verify.runbook(verify.verdict(plan, render.render(plan)), 1, [])
    assert "they had nothing to look at.\n\nNone." in said_there
    assert "No repair ran." in said_there


@pytest.mark.parametrize(
    ("check", "changes"),
    [
        ("no_cycles", {"edges": []}),
        ("sources_fetched", {"sources": []}),
        ("dreams_shaped", {"dreams": []}),
        ("dreams_apart", {"dreams": []}),
    ],
    ids=["no-edges", "no-sources", "no-dreams-shaped", "no-dreams-apart"],
)
def test_an_empty_subject_is_no_subject_and_not_a_pass(tmp_path, check, changes):
    tree = offline_tree(tmp_path / "tree")
    edit_plan_json(tree, **changes)
    _, result = rerun(tree)
    assert {c.name: c.state for c in result.checks}[check] == verify.NO_SUBJECT
    assert check not in result.named(verify.PASSED)


# -- what stands in the way of a page -------------------------------------


def as_directory(name: str) -> Callable[[Path], Path]:
    def block(tree: Path) -> Path:
        path = tree / name
        path.unlink(missing_ok=True)
        path.mkdir()
        return path

    return block


def as_link_to_a_directory(name: str) -> Callable[[Path], Path]:
    def block(tree: Path) -> Path:
        path = tree / name
        path.unlink(missing_ok=True)
        path.symlink_to(tree / ".protopilot", target_is_directory=True)
        return path

    return block


def topics_as_link_to_a_file(tree: Path) -> Path:
    shutil.rmtree(tree / "topics")
    (tree / "topics").symlink_to(tree / "PLAN.md")
    return tree / "topics"


@pytest.mark.parametrize(
    "block",
    [
        as_directory("dreams.md"),
        as_directory("sources.md"),
        as_link_to_a_directory("PLAN.md"),
        as_link_to_a_directory("sources.md"),
        as_link_to_a_directory("topics/scope.md"),
        topics_as_link_to_a_file,
    ],
    ids=["dreams-dir", "sources-dir", "entry-link", "sources-link", "topic-link", "topics-link-to-file"],
)
def test_every_page_path_blocked_is_named_and_nothing_moves(tmp_path, block):
    tree = offline_tree(tmp_path / "tree")
    blocker = block(tree)
    before = snapshot(tree)
    job = job_for()
    with pytest.raises(pipeline.PlanRefused, match="a page needs this name") as refused:
        pipeline.run_plan(job, tree, FakeLLM([]))
    assert str(blocker) in str(refused.value)
    assert snapshot(tree) == before
    assert "finished" not in kinds(job) and kinds(job)[-1] == "pass_failed"


def test_a_blocked_page_clears_with_one_rerun_and_no_model(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    as_directory("sources.md")(tree).rmdir()
    _, result = rerun(tree)
    assert result.ok and (tree / "sources.md").is_file()


def test_the_runbook_path_blocks_only_a_red_plan(tmp_path):
    tree = offline_tree(tmp_path / "tree")
    as_link_to_a_directory("RUNBOOK.md")(tree)
    assert rerun(tree)[1].ok
    edit_plan_json(tree, steps=[])
    with pytest.raises(pipeline.PlanRefused, match="RUNBOOK.md"):
        rerun(tree)


def test_a_refused_page_on_the_real_command_names_the_next_step(tmp_path, no_backend):
    tree = offline_tree(tmp_path / "tree")
    edit_plan_json(tree, steps=[])
    as_directory("RUNBOOK.md")(tree)
    result = proto_plan(tree)
    assert result.exit_code == 1
    assert "nothing was drawn" in said(result) and "Move it out of the way and rerun" in said(result)
    assert "Green" not in said(result)


def test_a_rerender_write_that_dies_says_the_tree_may_be_partial(tmp_path, no_backend):
    tree = offline_tree(tmp_path / "tree")
    os.chmod(tree / "sources.md", 0o400)
    result = proto_plan(tree)
    assert result.exit_code == 1
    assert "holds the whole plan but maybe not every page" in said(result)
    assert "Green" not in said(result) and "Plan at" not in said(result)


# -- two verdicts disagree ------------------------------------------------


@pytest.fixture
def tampered(monkeypatch) -> list[str]:
    """Lose a page after a green drawing lands, as a sync client or a second process might."""
    real, drawn = render.write, []

    def writes(plan: Plan, tree: Path, runbook: str = "") -> list[str]:
        written = real(plan, tree, runbook)
        drawn.append(runbook)
        if not runbook:
            (Path(tree) / TOPIC_PAGE).unlink()
        return written

    monkeypatch.setattr(render, "write", writes)
    return drawn


def test_green_drawn_and_red_landed_ends_red_everywhere(tmp_path, tampered):
    tree = tmp_path / "tree"
    job, result = run(tree)
    assert not result.ok and result.stage == "topic_map"
    assert [bool(runbook) for runbook in tampered] == [False, True]
    assert render.NOT_VERIFIED in page(tree) and "is missing" in page(tree, "RUNBOOK.md")
    assert job.events[-1]["ok"] is False
    assert not [line for line in job.lines if line.startswith(("Green", "Plan at")) or "\nPlan at" in line]
    folded = progress.fold(job.events)
    assert folded.gave_up and folded.stage == "topic_map" and folded.verify_state == progress.FAILED


def test_green_drawn_and_red_landed_exits_one(tmp_path, monkeypatch, tampered):
    monkeypatch.setattr(cli, "build_llm", lambda **_: FakeLLM(script()))
    result = proto_plan(tmp_path / "tree", "--yes")
    assert result.exit_code == 1
    assert "the written tree failed at topic_map" in said(result)
    assert "Green" not in said(result)


def test_a_rerender_where_the_two_disagree_is_red_too(tmp_path, monkeypatch):
    tree = offline_tree(tmp_path / "tree")
    real = render.write

    def loses_scope(plan: Plan, where: Path, runbook: str = "") -> list[str]:
        written = real(plan, where, runbook)
        if not runbook:
            (Path(where) / "topics" / "scope.md").unlink()
        return written

    monkeypatch.setattr(render, "write", loses_scope)
    job, result = rerun(tree)
    assert not result.ok and result.stage == "topic_map"
    assert kinds(job).count("exhausted") == 1 and job.events[-1]["ok"] is False


def test_the_verdict_a_run_returns_is_the_one_it_finished_on(tmp_path):
    job, result = run(tmp_path / "tree", repair_of(GOOD_EDGES, ["members", "lending"]), start=OUT_OF_ORDER)
    assert result.ok is job.events[-1]["ok"] is True
    assert job.events[-1]["attempts"] == kinds(job).count("verify_started") == repair.ATTEMPTS - 1
