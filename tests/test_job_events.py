"""The structured channel, beside the text one.

`Job.lines` is what a person reads; `Job.events` is what a view folds into a
progress region. Two channels rather than one because the alternative is a view
that parses human-formatted output to recover structure the producer already
had — so the property under test is not only *that* events are emitted, but
that emitting them left `lines` alone. A change that quietly reworded the log to
suit a new view would be the failure this design exists to prevent, and it would
pass any test that only counted events.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot import build as builder  # noqa: E402
from protopilot.jobs import Job, JobStore  # noqa: E402
from protopilot.verify import VerifyResult  # noqa: E402

pytestmark = pytest.mark.unit


class Recorder:
    """A job's event sink, without a job. Records the call, nothing else."""

    def __init__(self):
        self.seen: list[tuple[str, dict]] = []

    def __call__(self, kind: str, **fields):
        self.seen.append((kind, fields))

    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.seen]

    def of(self, kind: str) -> list[dict]:
        return [fields for k, fields in self.seen if k == kind]


class ScriptedVerifier:
    """A verdict per call, so the repair loop can be driven without Docker."""

    def __init__(self, *results: VerifyResult):
        self._results = list(results)

    def verify(self) -> VerifyResult:
        return self._results.pop(0) if len(self._results) > 1 else self._results[0]


RED = VerifyResult(ok=False, stage="smoke", summary="2 of 7 tests failed")
GREEN = VerifyResult(ok=True, stage="smoke", summary="green -- 7 passed")


@pytest.fixture()
def offline_spec(spec):
    """A factory for `(spec, ctx, llm, modules)` against a real skeleton.

    A factory rather than a fixture value because one test generates twice, to
    compare `hide_tests` on and off, and two generations into one tree would be
    comparing a pass against its own leftovers.

    The terminal target, so nothing here wants Docker. `modules` is handed back
    from the same place `generate` reads it, so a target that gains a pass
    updates the expectation rather than breaking the test.
    """
    from protopilot import targets
    from protopilot.llm import OfflineLLM
    from protopilot.passes import PassContext
    from protopilot.render import render_skeleton

    def make(root: Path):
        root.mkdir(parents=True, exist_ok=True)
        spec.target = "tui"
        render_skeleton(spec, root)
        spec.save(root)
        return spec, PassContext(project_dir=root), OfflineLLM(), list(targets.for_spec(spec).CODE_PASSES)

    return make


# -- the Job side ---------------------------------------------------------


def test_an_event_is_stamped_and_kept_beside_the_log():
    job = Job(id="j", idea="an idea")
    job.log("intake...")
    job.event("pass_started", name="schema", index=1, of=5)

    assert job.lines == ["intake..."], "an event must not write into the text log"
    assert len(job.events) == 1
    event = job.events[0]
    assert event["kind"] == "pass_started"
    assert event["name"] == "schema" and event["index"] == 1 and event["of"] == 5
    assert event["at"], "stamped by the writer, so every producer's events are comparable"


def test_the_snapshot_carries_events_and_still_carries_lines():
    """The web front end renders `lines` and must keep working untouched."""
    job = Job(id="j", idea="an idea")
    job.log("intake...")
    job.event("pass_done", name="ui", index=5, of=5, files=["app/app.tcss"])

    snap = json.loads(json.dumps(job.snapshot()))  # it is served over HTTP
    assert snap["lines"] == ["intake..."]
    assert snap["events"][0]["files"] == ["app/app.tcss"]


def test_a_job_run_through_the_store_records_events_from_its_thread():
    store = JobStore()
    job = store.create("an idea", "")
    store.run(job, lambda j: j.event("pass_started", name="schema", index=1, of=5))
    for _ in range(300):
        if job.status in ("done", "failed"):
            break
        __import__("time").sleep(0.01)
    assert job.status == "done"
    assert job.events and job.events[0]["name"] == "schema"


# -- the two producing loops ----------------------------------------------


def test_generate_emits_a_started_and_a_done_for_every_pass(tmp_path, offline_spec):
    """`index` and `of` come from the producer, which is the point.

    A view cannot count the passes itself: which ones run belongs to the
    target, so "pass 3 of 5" is knowable in `generate` and nowhere downstream.
    """
    spec, ctx, llm, modules = offline_spec(tmp_path)
    emit = Recorder()

    builder.generate(spec, ctx, llm, log=lambda _m: None, emit=emit)

    started = emit.of("pass_started")
    done = emit.of("pass_done")
    assert len(started) == len(modules), f"expected one start per pass, got {emit.kinds()}"
    assert len(done) == len(modules)
    assert [e["name"] for e in started] == [m.NAME for m in modules], "order is the running order"
    assert [e["index"] for e in started] == list(range(1, len(modules) + 1))
    assert {e["of"] for e in started} == {len(modules)}


def test_a_hidden_test_file_is_hidden_from_the_event_too(tmp_path, offline_spec):
    """`hide_tests` is presentation, and the event feeds a presentation.

    A demo that keeps the suite out of the log must not surface it in the
    progress region instead — the tree built is identical either way, which is
    the property `hide_tests` is allowed to leave alone and this one is not.
    """
    spec, ctx, llm, _ = offline_spec(tmp_path)
    shown, hidden = Recorder(), Recorder()

    builder.generate(spec, ctx, llm, log=lambda _m: None, hide_tests=False, emit=shown)
    spec2, ctx2, llm2, _ = offline_spec(tmp_path / "second")
    builder.generate(spec2, ctx2, llm2, log=lambda _m: None, hide_tests=True, emit=hidden)

    all_shown = [f for e in shown.of("pass_done") for f in e["files"]]
    all_hidden = [f for e in hidden.of("pass_done") for f in e["files"]]
    assert any(builder.is_test_path(f) for f in all_shown), "fixture proves nothing without a test file"
    assert not any(builder.is_test_path(f) for f in all_hidden), f"a test file leaked into the events: {all_hidden}"


def test_a_green_first_attempt_emits_started_then_passed(tmp_path, offline_spec):
    spec, ctx, llm, _ = offline_spec(tmp_path)
    emit = Recorder()

    outcome = builder.drive_to_green(
        spec, ctx, llm, ScriptedVerifier(GREEN), attempts=3, log=lambda _m: None, emit=emit
    )

    assert outcome.ok
    assert emit.kinds() == ["verify_started", "verify_passed"]
    assert emit.of("verify_started")[0] == {"attempt": 1, "of": 3}


def test_giving_up_is_a_distinct_event_from_failing(tmp_path, offline_spec):
    """A view that only ever saw `verify_failed` could not tell "still trying"
    from "gave up", and that difference is the whole point of the RUNBOOK the
    caller writes next. Offline repair cannot patch, so this run reaches the
    floor by the shortest honest route."""
    spec, ctx, llm, _ = offline_spec(tmp_path)
    emit = Recorder()

    outcome = builder.drive_to_green(spec, ctx, llm, ScriptedVerifier(RED), attempts=3, log=lambda _m: None, emit=emit)

    assert not outcome.ok
    kinds = emit.kinds()
    assert "verify_failed" in kinds and "exhausted" in kinds, kinds
    assert kinds[-1] == "exhausted", "the floor is the last thing a view hears about"
    assert emit.of("exhausted")[0]["stage"] == "smoke", "and it names where it stopped"
    assert emit.of("verify_failed")[0]["stage"] == "smoke"


def test_the_default_channel_is_silent_so_the_cli_is_untouched(tmp_path, offline_spec):
    """`proto new` passes no `emit` and must keep behaving exactly as it did.

    Asserted by running the real loop with the parameter omitted: if the
    default were anything but a no-op this raises rather than failing quietly.
    """
    spec, ctx, llm, _ = offline_spec(tmp_path)
    lines: list[str] = []

    builder.generate(spec, ctx, llm, log=lines.append)
    outcome = builder.drive_to_green(spec, ctx, llm, ScriptedVerifier(GREEN), attempts=3, log=lines.append)

    assert outcome.ok
    assert any("pass " in line for line in lines), "the text channel still carries everything"
