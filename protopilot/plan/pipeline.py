"""One plan, start to finish, on the job seam.

Speaks the vocabulary `generation.build` does (`plan`, `pass_started`,
`pass_done`, `pass_failed`, `finished`), so a view that folds a generation's
events folds this one too. Standard library and proto.pilot's own modules only,
for the reason `generation.py` gives.

Three halves, as `generation` has two, so a front end can stop between them:
`scoped`, then its questions, `outlined`, then the review, then `build`. They run
on one job and share one event list. Nothing reaches disk until every pass has
worked, so a failed pass leaves no tree: `existing_plan` treats any plan.json as
finished, and only a whole one is ever written.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from protopilot.llm import LLM, OfflineLLM
from protopilot.plan import baseline, render
from protopilot.plan.model import DEFAULT_DEPTH, Depth, Plan, plan_path
from protopilot.plan.passes import connect, consider, outline, run_pass, scope, start

#: Every model call a run makes, in order; the review sits after `BEFORE_REVIEW`.
PASSES = (scope, outline, connect, consider, start)
BEFORE_REVIEW = (scope, outline)
RENDER = "render"


class PlanRefused(Exception):
    """The target cannot take a plan; the message says why, for a person."""


def existing_plan(tree: Path, idea: str, direction: str = "") -> Plan | None:
    """The plan to re-render from `tree`, None if `tree` is free, refused otherwise.

    A plan for anything but this idea and direction is refused: exiting 0 on it
    would hand back somebody else's plan as the answer to what was asked.
    """
    tree = Path(tree)
    if not tree.exists():
        return None
    if not plan_path(tree).exists():
        raise PlanRefused(f"{tree} already exists and holds no plan; refusing to overwrite it")
    try:
        plan = Plan.load(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{plan_path(tree)} cannot be read as a plan: {exc}") from exc
    if (baseline.clean(idea), baseline.clean(direction)) != (plan.idea, plan.direction):
        steer = f" with direction {plan.direction!r}" if plan.direction else " with no direction"
        raise PlanRefused(
            f"{tree} already holds a plan for {plan.idea!r}{steer}. "
            "Pick another --dir, or rerun with that same idea and direction to re-render it."
        )
    return plan


def _pass(job, name: str, names: list[str], work: Callable[[], tuple[object, list[str]]]):
    """One step and its events. `work` returns its result, and the files it wrote."""
    index, of = names.index(name) + 1, len(names)
    job.log(f"  pass {name}...")
    job.event("pass_started", name=name, index=index, of=of)
    try:
        result, files = work()
    except Exception as exc:
        job.event("pass_failed", name=name, index=index, of=of, error=str(exc))
        raise
    if files:
        job.log(f"    {len(files)} file(s): {', '.join(files)}")
    job.event("pass_done", name=name, index=index, of=of, files=files)
    return result


def _names() -> list[str]:
    return [*(module.NAME for module in PASSES), RENDER]


def _model_pass(job, module, plan: Plan, llm: LLM) -> Plan:
    return _pass(job, module.NAME, _names(), lambda: (run_pass(module, plan, llm), []))


def call_estimate(llm: LLM) -> str:
    """The model calls this run makes, counted from `PASSES`, for the checkpoint."""
    excluded = "Research does not run in this build, so these numbers exclude it."
    if llm.offline:
        return f"Estimated model calls: 0, because this run is offline. {excluded}"
    ahead = [module.NAME for module in PASSES if module not in BEFORE_REVIEW]
    return f"Estimated model calls: {len(PASSES)} in all, {len(ahead)} still to come ({', '.join(ahead)}). {excluded}"


def scoped(job, llm: LLM, depth: Depth | None = None) -> Plan:
    """The plan's scope, with any questions still open. Writes no files."""
    job.event("plan", passes=_names())
    plan = scope.seed(job.idea, job.direction, None if llm.offline else depth or DEFAULT_DEPTH)
    return _model_pass(job, scope, plan, llm)


def outlined(job, llm: LLM, plan: Plan) -> Plan:
    """The topics, ready to review. Writes no files; the summary is the checkpoint's."""
    plan = _model_pass(job, outline, plan, llm)
    plan = outline.with_assumptions(plan) if llm.offline else plan
    estimate = call_estimate(llm)
    job.log(plan.summary())
    job.log(estimate)
    job.event("outline", topics=[t.slug for t in plan.topics], depth=plan.depth, estimate=estimate)
    return plan


def _refuse_if_taken(job, tree: Path) -> None:
    if existing_plan(tree, job.idea, job.direction) is not None:
        raise PlanRefused(f"{tree} gained a plan while this one was being made; leaving it alone")


def build(job, tree: Path, plan: Plan, llm: LLM) -> None:
    """Everything after the review, whether a person approved it or nobody was asked."""
    tree = Path(tree)
    _refuse_if_taken(job, tree)
    job.project_dir = str(tree)

    for module in (connect, consider, start):
        plan = _model_pass(job, module, plan, llm)
    # Again, because those passes take minutes. What is left is the instant between
    # here and the save's rename, in which another run's plan would still be replaced.
    _refuse_if_taken(job, tree)

    def written() -> tuple[None, list[str]]:
        saved = plan.save(tree)
        return None, [str(saved.relative_to(tree)), *render.write(plan, tree)]

    _pass(job, RENDER, _names(), written)
    _finish(job, tree, plan)


def _finish(job, tree: Path, plan: Plan) -> None:
    if not plan.researched:
        job.log("Not researched: nothing here was checked against a source.")
    job.log(f"\nPlan at {tree}. Start with {render.PLAN_FILE}.")
    job.event("finished", ok=True, attempts=0, project_dir=str(tree), run_hint="")


def rerender(job, tree: Path) -> None:
    """Draw the plan already in `tree` again. No pass runs, so no model is called."""
    tree = Path(tree)
    job.project_dir = str(tree)
    job.log(f"{tree} already holds this plan; drawing it again, with no model call.")
    job.event("plan", passes=[RENDER])
    plan = Plan.load(tree)
    _pass(job, RENDER, [RENDER], lambda: (None, render.write(plan, tree)))
    _finish(job, tree, plan)


def run_plan(job, tree: Path, llm: LLM | None = None, depth: Depth | None = None) -> None:
    """Every half with nobody asked, or a re-render of the plan already in `tree`."""
    tree = Path(tree)
    if existing_plan(tree, job.idea, job.direction) is not None:
        rerender(job, tree)
        return
    llm = llm or OfflineLLM()
    build(job, tree, outlined(job, llm, scoped(job, llm, depth)), llm)


def after_failure(tree: Path) -> str:
    """What a failed run left in `tree`, and what running the command again does."""
    if plan_path(tree).exists():
        return f"{tree} holds the whole plan but maybe not every page. Rerun to draw it again, with no model call."
    if tree.exists():
        return f"{tree} exists and holds no plan, so a rerun would be refused. Remove it, or pick another --dir."
    return f"Nothing was written to {tree}. Rerunning starts over from scope, and any review edits are lost."
