"""One plan, start to finish, on the job seam.

Speaks the vocabulary `generation.build` does (`plan`, `pass_started`,
`pass_done`, `pass_failed`, `finished`), so a view that folds a generation's
events folds this one too. Standard library and proto.pilot's own modules only,
for the reason `generation.py` gives.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from protopilot.plan import baseline, render
from protopilot.plan.model import Plan, plan_path


class PlanRefused(Exception):
    """The target cannot take a plan; the message says why, for a person."""


def existing_plan(tree: Path) -> Plan | None:
    """The plan `tree` already holds, None if `tree` is free, refused otherwise."""
    tree = Path(tree)
    if not tree.exists():
        return None
    if not plan_path(tree).exists():
        raise PlanRefused(f"{tree} already exists and holds no plan; refusing to overwrite it")
    try:
        return Plan.load(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{plan_path(tree)} cannot be read as a plan: {exc}") from exc


def _pass(job, name: str, index: int, of: int, work: Callable[[], list[str]]) -> None:
    job.log(f"  pass {name}...")
    job.event("pass_started", name=name, index=index, of=of)
    try:
        files = work()
    except Exception as exc:
        job.event("pass_failed", name=name, index=index, of=of, error=str(exc))
        raise
    job.log(f"    {len(files)} file(s): {', '.join(files)}")
    job.event("pass_done", name=name, index=index, of=of, files=files)


def _build(job, tree: Path) -> list[str]:
    plan = baseline.build_plan(job.idea, job.direction)
    return [str(plan.save(tree).relative_to(tree))]


def _warn_if_ignored(job, plan: Plan, tree: Path) -> None:
    """An idea that will not be planned is said out loud, never dropped."""
    direction = baseline.clean(job.direction)
    if baseline.clean(job.idea) != plan.idea or (direction and direction != plan.direction):
        job.log(f"{tree} already holds a plan for {plan.idea!r}; re-rendering that, and ignoring what was asked now")


def run_plan(job, tree: Path) -> None:
    """Build the offline plan into `tree`, or re-render the plan already there.

    plan.json lands first, so a render that dies leaves a tree that re-renders.
    """
    tree = Path(tree)
    existing = existing_plan(tree)
    job.project_dir = str(tree)
    if existing is not None:
        _warn_if_ignored(job, existing, tree)

    steps: list[tuple[str, Callable[[], list[str]]]] = [("render", lambda: render.write(Plan.load(tree), tree))]
    if existing is None:
        steps.insert(0, ("baseline", lambda: _build(job, tree)))

    job.event("plan", passes=[name for name, _ in steps])
    for index, (name, work) in enumerate(steps, start=1):
        _pass(job, name, index, len(steps), work)

    job.log(f"\nPlan at {tree}. Start with {render.PLAN_FILE}.")
    job.event("finished", ok=True, attempts=0, project_dir=str(tree), run_hint="")
