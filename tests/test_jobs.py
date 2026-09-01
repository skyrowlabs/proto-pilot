"""Background generations.

A generation takes minutes, so the front end starts a job and polls. The
failure mode that matters is a job that dies quietly: a thread that raises
leaves the UI showing "running" forever unless the status is recorded.
"""

from __future__ import annotations

import time

import pytest

from protopilot.jobs import JobStore

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


def wait_for(job, *, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline and job.status in ("pending", "running"):
        time.sleep(0.01)
    return job


def test_a_successful_job_finishes_and_keeps_its_log():
    store = JobStore()
    job = store.create("an idea", "a direction")
    store.run(job, lambda j: j.log("pass schema...\n  1 file(s)"))
    wait_for(job)
    assert job.status == "done"
    assert job.lines == ["pass schema...", "  1 file(s)"]


def test_a_failing_job_records_the_error_rather_than_hanging():
    store = JobStore()
    job = store.create("an idea")

    def boom(j):
        raise RuntimeError("credit balance is too low")

    store.run(job, boom)
    wait_for(job)
    assert job.status == "failed"
    assert "credit balance is too low" in job.error
    assert job.finished_at


def test_stray_stdout_is_captured_into_the_transcript():
    # The passes log through the callback, but anything that prints instead
    # would otherwise vanish -- and a silent failure is the worst outcome.
    store = JobStore()
    job = store.create("an idea")
    store.run(job, lambda j: print("printed, not logged"))
    wait_for(job)
    assert any("printed, not logged" in line for line in job.lines)


def test_snapshot_is_json_safe():
    import json

    store = JobStore()
    job = store.create("an idea")
    store.run(job, lambda j: j.log("hello"))
    wait_for(job)
    assert json.loads(json.dumps(job.snapshot()))["status"] == "done"
