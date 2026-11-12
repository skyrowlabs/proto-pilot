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

from protopilot.jobs import Job, JobStore  # noqa: E402

pytestmark = pytest.mark.unit


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
    """A snapshot is plain JSON, and holds both channels."""
    job = Job(id="j", idea="an idea")
    job.log("intake...")
    job.event("pass_done", name="ui", index=5, of=5, files=["app/app.tcss"])

    snap = json.loads(json.dumps(job.snapshot()))
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
