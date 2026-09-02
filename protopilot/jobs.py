"""Generations, as background jobs.

A generation takes minutes, which is fine at a terminal where you watch it
scroll and unbearable over HTTP where something is waiting on a response. So
the web front end never calls `generate` directly: it starts a job, gets an
id back immediately, and polls.

In-process and in-memory on purpose. This is a single-user tool driving a
local Docker daemon; a job queue with a broker would be more machinery than
the thing it schedules.
"""

from __future__ import annotations

import io
import threading
import uuid
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


@dataclass
class Job:
    id: str
    idea: str
    direction: str = ""
    status: str = "pending"  # pending | running | done | failed
    lines: list[str] = field(default_factory=list)
    error: str = ""
    project_dir: str = ""
    port: int | None = None
    url: str = ""
    started_at: str = ""
    finished_at: str = ""
    # Whatever this job produced, for jobs that answer rather than build
    # (the clarify pass). Kept generic so a new job kind needs no new field.
    result: dict = field(default_factory=dict)
    # What the journey collected between clarify and generate. Named fields
    # rather than more of `result`, because these three are read by the
    # generation step by name and a typo in a dict key would be silent.
    archetype: str = ""
    answers: dict = field(default_factory=dict)
    theme: dict = field(default_factory=dict)

    def log(self, message: str) -> None:
        for line in str(message).splitlines() or [""]:
            self.lines.append(line)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "idea": self.idea,
            "direction": self.direction,
            "status": self.status,
            "lines": list(self.lines),
            "error": self.error,
            "project_dir": self.project_dir,
            "port": self.port,
            "url": self.url,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
        }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, idea: str, direction: str = "") -> Job:
        job = Job(id=uuid.uuid4().hex[:12], idea=idea, direction=direction)
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

        def target() -> None:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            buffer = io.StringIO()
            try:
                with redirect_stdout(buffer):
                    work(job)
                job.status = "done"
            except BaseException as exc:  # noqa: BLE001 - surfaced, not swallowed
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
            finally:
                # Anything the work printed rather than logged still belongs
                # in the transcript; a silent failure is the worst outcome.
                captured = buffer.getvalue().strip()
                if captured:
                    job.log(captured)
                job.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        threading.Thread(target=target, daemon=True).start()


STORE = JobStore()
