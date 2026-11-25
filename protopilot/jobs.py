"""A plan run, as a job.

A run takes minutes and stops for a person twice, so its halves share one job:
a log a person reads, and a list of typed events a view folds. The work runs
on a thread while the caller follows the log.

In-process and in-memory on purpose. This is a single-user tool; a job queue
with a broker would be more machinery than the thing it schedules.
"""

from __future__ import annotations

import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


@dataclass
class Job:
    id: str
    idea: str
    direction: str = ""
    #: The person's brief beside the idea, as plain data: `plan.model.Brief` validates it.
    brief: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | failed
    lines: list[str] = field(default_factory=list)
    #: The structured half of the transcript, **beside `lines` and never
    #: instead of it**. `lines` is what a person reads; `events` is what a view
    #: derives a progress region from. Two channels so no view parses
    #: human-formatted text, which leaves a log line free to be reworded.
    #:
    #: Append-only and untyped on purpose. A consumer folds the list to get
    #: current state, so a new event kind is additive and an old reader that
    #: does not know it skips it rather than breaking.
    events: list[dict] = field(default_factory=list)
    error: str = ""
    project_dir: str = ""
    started_at: str = ""
    finished_at: str = ""

    def log(self, message: str) -> None:
        for line in str(message).splitlines() or [""]:
            self.lines.append(line)

    def event(self, kind: str, **fields: object) -> None:
        """Record one structured step.

        Stamped here rather than by the caller, so every producer's events are
        comparable and no loop has to remember to do it. `kind` is positional
        because it is the one field every consumer switches on.
        """
        self.events.append({"kind": kind, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields})

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "idea": self.idea,
            "direction": self.direction,
            "brief": dict(self.brief),
            "status": self.status,
            "lines": list(self.lines),
            "events": list(self.events),
            "error": self.error,
            "project_dir": self.project_dir,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class _JobWriter:
    """A file-like that turns writes into `job.log` calls, a line at a time.

    Not a buffer: a line reaches the log when it is printed, not when the job
    ends, so a follower sees it as it happens.

    Partial writes are held until a newline, because `print` issues the text and
    the terminator as two separate calls and a line-per-write writer would
    double every line.
    """

    def __init__(self, job: "Job") -> None:
        self._job = job
        self._partial = ""

    def write(self, text: str) -> int:
        self._partial += text
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            self._job.log(line)
        return len(text)

    def flush(self) -> None:
        """Whatever a job printed without a trailing newline still belongs in
        the transcript; a silent loss is the worst outcome."""
        if self._partial:
            self._job.log(self._partial)
            self._partial = ""


class _RoutedStdout:
    """`sys.stdout`, dispatched by calling thread.

    `contextlib.redirect_stdout` rebinds `sys.stdout` for the whole **process**,
    so two jobs on two threads would capture each other's output.

    This is the same idea done per thread: a job registers a writer for its own
    thread, and every other thread -- the main one, another job's -- goes on
    reaching the real stdout untouched.

    Installed once and left in place rather than swapped in and out around each
    job. Restoring on the last unregister looks tidier and races: a second job
    registering while the first restores loses its routing, which is the exact
    class of bug this replaces. With no writer registered every call delegates
    to the original object, so leaving it installed is not observable.
    """

    def __init__(self, base) -> None:
        self._base = base
        self._writers: dict[int, _JobWriter] = {}
        self._lock = threading.Lock()

    def register(self, writer: _JobWriter) -> None:
        with self._lock:
            self._writers[threading.get_ident()] = writer

    def unregister(self) -> None:
        with self._lock:
            writer = self._writers.pop(threading.get_ident(), None)
        if writer is not None:
            writer.flush()

    def _target(self):
        return self._writers.get(threading.get_ident(), self._base)

    def write(self, text: str) -> int:
        return self._target().write(text)

    def flush(self) -> None:
        self._target().flush()

    def __getattr__(self, name: str):
        """Everything else is the real stdout's business.

        `isatty`, `encoding`, `fileno` and the rest have to keep answering
        truthfully: a library asking whether stdout is a terminal, or asking for
        its file descriptor, is asking about the process and not about this
        job's transcript.
        """
        return getattr(self._base, name)


def _routed_stdout() -> _RoutedStdout:
    """Install the router once, and hand back the installed one."""
    current = sys.stdout
    if isinstance(current, _RoutedStdout):
        return current
    router = _RoutedStdout(current)
    sys.stdout = router
    return router


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, idea: str, direction: str = "", brief: dict | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], idea=idea, direction=direction, brief=dict(brief or {}))
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)

    def run(self, job: Job, work: Callable[[Job], None]) -> None:
        """Run `work` on a thread, capturing its stdout into the job's log."""

        router = _routed_stdout()

        def target() -> None:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            # Registered from inside the thread, because the routing key is the
            # thread's own id. Doing it in `run` would tag the caller's thread
            # and send this job's output wherever the caller happened to be.
            router.register(_JobWriter(job))
            try:
                work(job)
                job.status = "done"
            except BaseException as exc:  # noqa: BLE001 - surfaced, not swallowed
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
            finally:
                router.unregister()
                job.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        threading.Thread(target=target, daemon=True).start()


STORE = JobStore()
