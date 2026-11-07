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

`repaired` verifies before the render, against pages drawn in memory, so repair
only ever edits data. `_hand_back` writes, then reads the tree and checks again. A
plan still red is handed back with a RUNBOOK, `finished` says `ok=False`, and the
CLI exits 1, as `proto new`'s floor does. A failed pass is a different thing: a
pass that returns nothing a plan can hold leaves no tree at all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from protopilot.llm import LLM, OfflineLLM
from protopilot.plan import baseline, render, verify
from protopilot.plan.model import DEFAULT_DEPTH, Depth, Plan, plan_path
from protopilot.plan.passes import connect, consider, outline, repair, run_pass, scope, start

#: Every model call a run makes, in order; the review sits after `BEFORE_REVIEW`.
PASSES = (scope, outline, connect, consider, start)
BEFORE_REVIEW = (scope, outline)
RENDER = "render"


class PlanRefused(Exception):
    """The target cannot take a plan; the message says why, for a person."""


@dataclass
class Checked:
    """Where verification left a plan: the verdict, the checks it took, and what repair tried."""

    plan: Plan
    verdict: verify.PlanVerdict
    attempts: int
    tried: list[str]


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
    repairs = f"plus 0 to {repair.ATTEMPTS} repair calls, only if verification finds something repair can fix"
    still = f"{len(ahead)} still to come ({', '.join(ahead)})"
    return f"Estimated model calls: {len(PASSES)} in all, {still}, {repairs}. {excluded}"


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


def _drawn(plan: Plan, tree: Path, runbook: str) -> list[str]:
    try:
        return render.write(plan, tree, runbook)
    except render.PageBlocked as exc:
        raise PlanRefused(str(exc)) from exc


def _verified(job, plan: Plan, attempt: int, of: int) -> verify.PlanVerdict:
    """One verification against the pages this plan draws. Green is `_hand_back`'s to say, once they land."""
    job.log(f"  verify (attempt {attempt})...")
    job.event("verify_started", attempt=attempt, of=of)
    result = verify.verdict(plan, render.render(plan))
    if result.ok:
        job.log("    nothing failed yet; the written tree is checked next")
    else:
        job.log(f"    failed at {result.stage}: {result.summary}")
        job.event("verify_failed", attempt=attempt, stage=result.stage, summary=result.summary)
    return result


def _repair_once(job, llm: LLM, checked: Checked, entry: Plan, rejection: str) -> str | None:
    """One repair, folded into `checked`. Returns why it was thrown away, "" if it landed, None to stop."""
    plan, result, attempt = checked.plan, checked.verdict, checked.attempts
    fixable = repair.fixable(result)
    if not fixable:
        out_of_reach = ", ".join(result.named(verify.FAILED))
        job.log(f"    repair cannot reach {out_of_reach}")
        checked.tried.append(f"attempt {attempt} ({result.stage}): repair cannot reach {out_of_reach}, so none ran")
        return None
    label = f"attempt {attempt} ({', '.join(check.name for check in fixable)})"
    job.log("  pass repair...")
    job.event("repair_started", attempt=attempt, stage=fixable[0].name)
    try:
        after = run_pass(repair, plan, llm, repair.failure(result, rejection))
    except Exception as exc:  # noqa: BLE001 -- a failed repair is an outcome
        job.log(f"    repair pass failed: {exc}")
        job.event("repair_failed", attempt=attempt, error=str(exc))
        checked.tried.append(f"{label}: the repair pass failed: {exc}")
        return None
    change = repair.changes(plan, after)
    if not change:
        retry = "remove this directory and run the command with a model backend"
        notes = (
            f"offline mode cannot repair; to have a model try, {retry}" if llm.offline else "the repair changed nothing"
        )
        job.log(f"    repair produced no changes: {notes}")
        job.event("repair_empty", attempt=attempt, notes=notes)
        checked.tried.append(f"{label}: {notes}")
        return None
    reason = repair.rejected(entry, after) or repair.worsened(result, after)
    if reason:
        job.log(f"    rejected: {reason}")
        job.event("repair_rejected", attempt=attempt, reason=reason)
        checked.tried.append(f"{label}: rejected, because {reason}")
        return reason
    job.log(f"    {change}")
    job.event("repair_done", attempt=attempt, files=[], notes=change)
    checked.tried.append(f"{label}: {change}")
    checked.plan = after
    return ""


def repaired(job, plan: Plan, llm: LLM) -> Checked:
    """Verify, and on red repair and verify again, up to `repair.ATTEMPTS` times, then stop."""
    checked = Checked(plan, _verified(job, plan, 1, repair.ATTEMPTS), 1, [])
    rejection: str | None = ""
    while not checked.verdict.ok and checked.attempts <= repair.ATTEMPTS and rejection is not None:
        rejection = _repair_once(job, llm, checked, plan, rejection)
        if rejection is not None:
            checked.attempts += 1
            checked.verdict = _verified(job, checked.plan, checked.attempts, repair.ATTEMPTS)
    if not checked.verdict.ok:
        job.event("exhausted", attempts=checked.attempts, stage=checked.verdict.stage)
    return checked


def _hand_back(job, tree: Path, names: list[str], checked: Checked, save: bool) -> verify.PlanVerdict:
    """Write the plan, whatever colour it is, then judge what landed, which is the run's verdict."""
    plan = checked.plan

    def runbook(result: verify.PlanVerdict) -> str:
        return "" if result.ok else verify.runbook(result, checked.attempts, checked.tried)

    def written() -> tuple[None, list[str]]:
        saved = [str(plan.save(tree).relative_to(tree))] if save else []
        return None, [*saved, *_drawn(plan, tree, runbook(checked.verdict))]

    _pass(job, RENDER, names, written)
    landed = verify.verdict(plan, render.read(tree))
    if checked.verdict.ok and not landed.ok:
        job.log(f"    the written tree failed at {landed.stage}: {landed.summary}")
        job.event("verify_failed", attempt=checked.attempts, stage=landed.stage, summary=landed.summary)
        job.event("exhausted", attempts=checked.attempts, stage=landed.stage)
        _drawn(plan, tree, runbook(landed))
    # Either verdict red is red: the drawn one wrote the runbook, so green here would sit on top of it.
    final = checked.verdict if landed.ok else landed
    if final.ok:
        job.log("    no check failed")
        job.event(
            "verify_passed", attempt=checked.attempts, summary=final.summary, no_subject=final.named(verify.NO_SUBJECT)
        )
    _finish(job, tree, plan, final, checked.attempts)
    return final


def build(job, tree: Path, plan: Plan, llm: LLM) -> verify.PlanVerdict:
    """Everything after the review, whether a person approved it or nobody was asked."""
    tree = Path(tree)
    _refuse_if_taken(job, tree)
    job.project_dir = str(tree)

    for module in (connect, consider, start):
        plan = _model_pass(job, module, plan, llm)
    checked = repaired(job, plan, llm)
    # Again, because those passes take minutes. What is left is the instant between
    # here and the save's rename, in which another run's plan would still be replaced.
    _refuse_if_taken(job, tree)
    return _hand_back(job, tree, _names(), checked, save=True)


def _finish(job, tree: Path, plan: Plan, result: verify.PlanVerdict, attempts: int) -> None:
    if not plan.researched:
        job.log("Not researched: nothing here was checked against a source.")
    if result.ok:
        job.log(result.summary)
        job.log(f"\nPlan at {tree}. Start with {render.PLAN_FILE}.")
    else:
        job.log(f"Not verified: red at {result.stage} after {attempts} check(s).")
        job.log(f"\nThe tree is at {tree}, and what is still wrong is written down in {render.RUNBOOK_FILE}.")
    job.event("finished", ok=result.ok, attempts=attempts, project_dir=str(tree), run_hint="")


def rerender(job, tree: Path) -> verify.PlanVerdict:
    """Verify the plan already in `tree` and draw it again. No model, so no repair: plan.json may be hand-edited."""
    tree = Path(tree)
    job.project_dir = str(tree)
    job.log(f"{tree} already holds this plan; checking it and drawing it again, with no model call.")
    job.event("plan", passes=[RENDER])
    plan = Plan.load(tree)
    result = _verified(job, plan, 1, 1)
    tried = [] if result.ok else ["A re-render calls no model, so no repair ran."]
    if not result.ok:
        job.event("exhausted", attempts=1, stage=result.stage)
    return _hand_back(job, tree, [RENDER], Checked(plan, result, 1, tried), save=False)


def run_plan(job, tree: Path, llm: LLM | None = None, depth: Depth | None = None) -> verify.PlanVerdict:
    """Every half with nobody asked, or a re-render of the plan already in `tree`."""
    tree = Path(tree)
    if existing_plan(tree, job.idea, job.direction) is not None:
        return rerender(job, tree)
    llm = llm or OfflineLLM()
    return build(job, tree, outlined(job, llm, scoped(job, llm, depth)), llm)


def after_failure(tree: Path) -> str:
    """What a failed run left in `tree`, and what running the command again does."""
    if plan_path(tree).exists():
        return (
            f"{tree} holds the whole plan but maybe not every page. Any page there may be out of date. "
            "Rerun to check it and draw it again, with no model call."
        )
    if tree.exists():
        return f"{tree} exists and holds no plan, so a rerun would be refused. Remove it, or pick another --dir."
    return f"Nothing was written to {tree}. Rerunning starts over from scope, and any review edits are lost."
