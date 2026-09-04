"""Fold a job's event list into the state a progress region draws.

Deliberately a **pure function over a list of dicts**, with no Textual import
anywhere in this module. Three reasons, in order of how much they cost when
ignored:

* It is the part most likely to be wrong, and the part a widget test would
  exercise worst — asserting on rendered text through a pilot to find out
  whether attempt 2 counted is a hard way to learn it.
* A second view (the web front end, a `--json` status) folds the same events
  the same way, and a fold living inside a widget is a fold that gets rewritten
  rather than reused.
* It is the boundary where "parse the log" would otherwise creep back in. Every
  field here comes from an emit; if something is missing the answer is a new
  event, never a regex over `job.lines`.

Unknown event kinds are ignored rather than raising. The channel is append-only
and additive by design, so an older reader meeting a newer producer degrades to
a less detailed view instead of a crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: A pass that has not started yet, one that is running, one that finished.
PENDING, RUNNING, DONE, FAILED = "pending", "running", "done", "failed"


@dataclass
class PassState:
    name: str
    state: str = PENDING
    files: list[str] = field(default_factory=list)


@dataclass
class Progress:
    """What a view needs, and nothing a view would have to compute again."""

    name: str = ""
    slug: str = ""
    target: str = ""
    archetype: str = ""
    passes: list[PassState] = field(default_factory=list)
    verify_attempt: int = 0
    verify_of: int = 0
    verify_state: str = ""
    stage: str = ""
    repairs: int = 0
    rejected: int = 0
    finished: bool = False
    ok: bool = False
    attempts: int = 0
    project_dir: str = ""
    run_hint: str = ""

    @property
    def done_passes(self) -> int:
        return sum(1 for p in self.passes if p.state in (DONE, FAILED))

    @property
    def gave_up(self) -> bool:
        """Distinct from `not ok`. A job still running is not `ok` either, and a
        view that conflates the two says "failed" the whole way through."""
        return self.finished and not self.ok


def fold(events: list[dict]) -> Progress:
    """Every event, in order, applied to one `Progress`."""
    p = Progress()
    for event in events:
        kind = event.get("kind", "")
        if kind == "spec":
            p.name = str(event.get("name", ""))
            p.slug = str(event.get("slug", ""))
            p.target = str(event.get("target", ""))
            p.archetype = str(event.get("archetype", ""))
        elif kind == "plan":
            # Named before any of them runs, so the list is complete from the
            # first frame and fills in rather than growing.
            p.passes = [PassState(name=str(n)) for n in event.get("passes", [])]
        elif kind in ("pass_started", "pass_done", "pass_failed"):
            _apply_pass(p, kind, event)
        elif kind == "verify_started":
            p.verify_attempt = int(event.get("attempt", 0))
            p.verify_of = int(event.get("of", 0))
            p.verify_state = RUNNING
        elif kind == "verify_passed":
            p.verify_state = DONE
            p.stage = ""
        elif kind == "verify_failed":
            p.verify_state = FAILED
            p.stage = str(event.get("stage", ""))
        elif kind == "repair_done":
            p.repairs += 1
        elif kind == "repair_rejected":
            p.rejected += 1
        elif kind == "exhausted":
            p.stage = str(event.get("stage", "")) or p.stage
        elif kind == "finished":
            p.finished = True
            p.ok = bool(event.get("ok"))
            p.attempts = int(event.get("attempts", 0))
            p.project_dir = str(event.get("project_dir", ""))
            p.run_hint = str(event.get("run_hint", ""))
    return p


def _apply_pass(p: Progress, kind: str, event: dict) -> None:
    """Match on `name`, not on `index`.

    An index is a position in a list this fold may not have — a job whose
    `plan` event predates this reader, or a partial event list — and a
    position-based write into a short list is either an IndexError or a
    silent write to the wrong pass. The name is what the event is *about*.
    """
    name = str(event.get("name", ""))
    found = next((s for s in p.passes if s.name == name), None)
    if found is None:
        # No plan seen: keep the shape rather than dropping the pass.
        found = PassState(name=name)
        p.passes.append(found)
    if kind == "pass_started":
        found.state = RUNNING
    elif kind == "pass_done":
        found.state = DONE
        found.files = [str(f) for f in event.get("files", [])]
    else:
        found.state = FAILED


#: How each state reads in one column of a fixed-width list.
MARKS = {PENDING: "·", RUNNING: "▸", DONE: "✓", FAILED: "✗"}


def lines(p: Progress) -> list[str]:
    """The progress region as text. One place, so both a widget and a plain
    terminal fallback render the same thing."""
    out: list[str] = []
    if p.name:
        shape = " / ".join(x for x in (p.target, p.archetype) if x)
        out.append(f"{p.name}  ({shape})" if shape else p.name)
    if p.passes:
        out.append(f"passes  {p.done_passes}/{len(p.passes)}")
        for state in p.passes:
            files = f"  {', '.join(state.files)}" if state.files else ""
            out.append(f"  {MARKS.get(state.state, '·')} {state.name}{files}")
    if p.verify_attempt:
        verdict = {RUNNING: "running", DONE: "green", FAILED: f"red at {p.stage}"}.get(p.verify_state, "")
        out.append(f"verify  attempt {p.verify_attempt} of {p.verify_of}: {verdict}")
    if p.repairs:
        note = f", {p.rejected} rejected" if p.rejected else ""
        out.append(f"repair  {p.repairs} applied{note}")
    if p.finished:
        out.append("")
        out.append(f"green in {p.attempts} attempt(s)" if p.ok else f"red at {p.stage or 'unknown'} — see RUNBOOK.md")
        if p.project_dir:
            out.append(p.run_hint.format(directory=p.project_dir) if p.run_hint else p.project_dir)
    return out
