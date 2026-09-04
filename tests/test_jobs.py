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


# ── two at once, which the global redirect could not do ──────────────────


def test_two_concurrent_jobs_do_not_capture_each_other(tmp_path):
    """The defect `redirect_stdout` had, stated as a test.

    `contextlib.redirect_stdout` rebinds `sys.stdout` for the whole process, so
    two generations on two threads captured each other's output and braided two
    transcripts together with nothing marking the seam. `proto serve` never hit
    it because nobody had run two at once.

    Each job prints many interleaved lines rather than one, deliberately: with a
    single print each, a run where the two happened not to overlap would pass
    and prove nothing about the thing under test.
    """
    import threading

    store = JobStore()
    first, second = store.create("first"), store.create("second")
    both_started = threading.Barrier(2, timeout=5)

    def chatter(tag):
        def work(job):
            both_started.wait()  # guarantee the overlap the test is about
            for i in range(50):
                print(f"{tag}-{i}")
                time.sleep(0.001)

        return work

    store.run(first, chatter("alpha"))
    store.run(second, chatter("beta"))
    wait_for(first, timeout=10)
    wait_for(second, timeout=10)

    assert first.status == "done" and second.status == "done", (first.error, second.error)
    assert len(first.lines) == 50 and len(second.lines) == 50, (len(first.lines), len(second.lines))
    assert all(line.startswith("alpha-") for line in first.lines), first.lines[:5]
    assert all(line.startswith("beta-") for line in second.lines), second.lines[:5]
    # Order is preserved within a job even though the two interleaved in time.
    assert first.lines == [f"alpha-{i}" for i in range(50)]


def test_a_print_from_a_thread_with_no_job_still_reaches_real_stdout(capsys):
    """The router must be invisible to everything that is not a job.

    It is installed process-wide and left there, so a main-thread `print` after
    any job has ever run must behave exactly as it did before.
    """
    store = JobStore()
    job = store.create("an idea")
    store.run(job, lambda j: print("inside the job"))
    wait_for(job)

    print("outside any job")
    assert "outside any job" in capsys.readouterr().out
    assert job.lines == ["inside the job"]


def test_output_arrives_during_the_job_rather_than_at_the_end():
    """A print reaches the transcript **live**.

    The version this replaced buffered into a `StringIO` and appended it in the
    `finally`, so anything printed rather than logged arrived when the job
    ended -- one block, twenty-one minutes late on a real generation. Held open
    on an event so the assertion is made mid-run and cannot accidentally be
    made against a finished job.
    """
    import threading

    released = threading.Event()
    store = JobStore()
    job = store.create("an idea")

    def work(j):
        print("the first line")
        released.wait(timeout=5)
        print("the second line")

    store.run(job, work)
    deadline = time.time() + 5
    while time.time() < deadline and not job.lines:
        time.sleep(0.01)

    assert job.lines == ["the first line"], "a print did not arrive until the job ended"
    assert job.status == "running"
    released.set()
    wait_for(job)
    assert job.lines == ["the first line", "the second line"]


def test_a_partial_line_is_not_lost_when_the_job_ends():
    """`print` issues text and its terminator separately, and a job can also
    write without one at all. Anything left in hand at the end still belongs in
    the transcript -- a silent loss is the worst outcome."""
    store = JobStore()
    job = store.create("an idea")
    store.run(job, lambda j: print("no newline here", end=""))
    wait_for(job)
    assert job.lines == ["no newline here"]
