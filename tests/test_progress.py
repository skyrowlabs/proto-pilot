"""The event fold, tested as a function.

`protopilot/progress.py` imports no view, so none of this needs one: a fold is
asked directly whether attempt 2 was counted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot.progress import DONE, FAILED, PENDING, RUNNING, fold, lines  # noqa: E402

pytestmark = pytest.mark.unit

PLAN = {"kind": "plan", "passes": ["schema", "smoke", "seed"]}


def states(p) -> dict:
    return {s.name: s.state for s in p.passes}


def test_nothing_folds_to_nothing():
    p = fold([])
    assert p.passes == [] and not p.finished
    assert lines(p) == [], "an empty fold must render nothing, not a frame of empty labels"


def test_the_plan_fills_the_list_before_anything_runs():
    """A view that learns each pass's name only as it starts shows a list that
    grows under the reader instead of filling in."""
    p = fold([PLAN])
    assert [s.name for s in p.passes] == ["schema", "smoke", "seed"]
    assert set(states(p).values()) == {PENDING}
    assert p.done_passes == 0


def test_a_pass_moves_pending_to_running_to_done_and_keeps_its_files():
    p = fold(
        [
            PLAN,
            {"kind": "pass_started", "name": "schema", "index": 1, "of": 3},
            {"kind": "pass_done", "name": "schema", "index": 1, "of": 3, "files": ["app/models.py"]},
            {"kind": "pass_started", "name": "smoke", "index": 2, "of": 3},
        ]
    )
    assert states(p) == {"schema": DONE, "smoke": RUNNING, "seed": PENDING}
    assert p.passes[0].files == ["app/models.py"]
    assert p.done_passes == 1


def test_a_pass_is_matched_by_name_and_not_by_index():
    """When the name and the index disagree, the name wins.

    The index is a **position in a list this fold may not have**: a reader
    attached to a job in flight, or one holding a plan a newer producer has
    since changed, has a list whose positions do not line up. A position-based
    write is then either an IndexError or — far worse — a silent write into the
    wrong pass, which renders as a completed step that never ran.

    The first case below is what the earlier version of this test asserted, and
    it does not discriminate: with no plan, name-matching and index-matching
    both fall through to "append a new pass" and both look right. Found by
    planting index-matching and watching this file stay green.
    """
    # No plan: the pass names itself, whichever way it is matched.
    bare = fold([{"kind": "pass_started", "name": "ui", "index": 5, "of": 5}])
    assert [s.name for s in bare.passes] == ["ui"]
    assert bare.passes[0].state == RUNNING

    # A plan, and an index that disagrees with the name's position. Only one
    # answer is right, and the two strategies give different ones.
    p = fold([PLAN, {"kind": "pass_done", "name": "schema", "index": 3, "of": 3, "files": ["app/models.py"]}])
    assert states(p) == {
        "schema": DONE,
        "smoke": PENDING,
        "seed": PENDING,
    }, "the event was about `schema`; matching on its index credits `seed` instead"
    assert p.passes[0].files == ["app/models.py"]


def test_a_failed_pass_is_distinct_from_a_pending_one():
    p = fold([PLAN, {"kind": "pass_failed", "name": "smoke", "index": 2, "of": 3, "error": "boom"}])
    assert states(p)["smoke"] == FAILED
    assert p.done_passes == 1, "a failed pass has finished; it is not still waiting"


def test_verify_attempts_replace_rather_than_accumulate():
    p = fold(
        [
            {"kind": "verify_started", "attempt": 1, "of": 3},
            {"kind": "verify_failed", "attempt": 1, "stage": "smoke", "summary": "2 failed"},
            {"kind": "repair_done", "attempt": 1, "files": ["app/screens.py"], "notes": "fixed"},
            {"kind": "verify_started", "attempt": 2, "of": 3},
            {"kind": "verify_passed", "attempt": 2, "summary": "green"},
        ]
    )
    assert p.verify_attempt == 2 and p.verify_state == DONE
    assert p.repairs == 1
    assert p.stage == "", "a green verify clears the stage a red one named"


def test_giving_up_is_not_the_same_question_as_not_being_ok():
    """A job still running is `not ok` too, and a view that conflates them
    reads "failed" the whole way through a healthy generation."""
    running = fold([PLAN, {"kind": "verify_started", "attempt": 1, "of": 3}])
    assert not running.ok and not running.gave_up

    red = fold(
        [
            {"kind": "verify_failed", "attempt": 1, "stage": "smoke", "summary": "x"},
            {"kind": "exhausted", "attempts": 1, "stage": "smoke"},
            {"kind": "finished", "ok": False, "attempts": 1, "project_dir": "/tmp/t"},
        ]
    )
    assert red.gave_up and red.stage == "smoke"

    green = fold([{"kind": "finished", "ok": True, "attempts": 1, "project_dir": "/tmp/t"}])
    assert green.finished and green.ok and not green.gave_up


def test_an_unknown_event_kind_is_ignored_rather_than_raising():
    """The channel is append-only and additive, so an older reader meeting a
    newer producer must degrade to a less detailed view, never to a crash."""
    p = fold([PLAN, {"kind": "something_invented_next_month", "detail": 1}, {"kind": "verify_started", "attempt": 1}])
    assert p.verify_attempt == 1 and len(p.passes) == 3


def test_a_rejected_repair_is_counted_separately_from_an_applied_one():
    """The one guardrail the prompt cannot enforce — a repair that passes by
    deleting tests — is reverted, and a view that showed it as an applied repair
    would be reporting the opposite of what happened."""
    p = fold(
        [
            {"kind": "repair_done", "attempt": 1, "files": ["a.py"], "notes": ""},
            {"kind": "repair_rejected", "attempt": 1, "before": 7, "after": 3},
        ]
    )
    assert p.repairs == 1 and p.rejected == 1
    assert "1 rejected" in "\n".join(lines(p))


# -- rendering ------------------------------------------------------------


def test_the_directory_is_on_a_line_of_its_own():
    """A long path is found by eye and copied whole only when nothing shares its line."""
    directory = "/srv/work/plans/community_tool_library"
    rendered = lines(fold([{"kind": "finished", "ok": True, "attempts": 1, "project_dir": directory}]))
    assert directory in rendered, f"the path is not on a line by itself: {rendered}"


def test_a_red_run_names_the_stage_and_points_at_the_runbook():
    p = fold(
        [
            {"kind": "verify_failed", "attempt": 3, "stage": "browser", "summary": "x"},
            {"kind": "exhausted", "attempts": 3, "stage": "browser"},
            {"kind": "finished", "ok": False, "attempts": 3, "project_dir": "/w/n"},
        ]
    )
    text = "\n".join(lines(p))
    assert "red at browser" in text and "RUNBOOK.md" in text
