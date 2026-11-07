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

Dreaming is the exception, because dreams are extras. A plan keeps going when its
dreaming fails, and `dreams.md` says so. `dream_round`, `promote` and `drop` work on a
plan that is already green, and change nothing unless the result is green too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from protopilot.llm import LLM, OfflineLLM
from protopilot.plan import baseline, dreaming, render, verify
from protopilot.plan.lenses import LENSES, Lens
from protopilot.plan.model import DEFAULT_DEPTH, Depth, Dream, Plan, plan_path
from protopilot.plan.passes import (
    collect,
    connect,
    consider,
    evaluate,
    outline,
)
from protopilot.plan.passes import promote as promote_pass
from protopilot.plan.passes import propose, repair, run_pass, scope, start

#: Every model call a run makes, in order; the review sits after `BEFORE_REVIEW`.
PLAN_PASSES = (scope, outline, connect, consider, start)
DREAM_PASSES = (collect, evaluate, propose)
PASSES = (*PLAN_PASSES, *DREAM_PASSES)
BEFORE_REVIEW = (scope, outline)
RENDER = "render"
#: A model's error can be a page of text, and it lands in `dreams.md`.
MOST_FAILURE_CHARS = 300


class PlanRefused(Exception):
    """The target cannot take a plan; the message says why, for a person."""


class DreamFailed(Exception):
    """A dream pass stopped; the message says which, and why, in one line."""


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


def _passes(dream: bool) -> tuple:
    return PASSES if dream else PLAN_PASSES


def _names(dream: bool = True) -> list[str]:
    return [*(module.NAME for module in _passes(dream)), RENDER]


def _model_pass(job, module, plan: Plan, llm: LLM, names: list[str]) -> Plan:
    return _pass(job, module.NAME, names, lambda: (run_pass(module, plan, llm), []))


def call_estimate(llm: LLM, dream: bool = True) -> str:
    """The model calls this run makes, counted from the passes it runs, for the checkpoint."""
    excluded = "Research does not run in this build, so these numbers exclude it."
    if llm.offline:
        return f"Estimated model calls: 0, because this run is offline. {excluded}"
    passes = _passes(dream)
    ahead = [module.NAME for module in passes if module not in BEFORE_REVIEW]
    repairs = f"plus 0 to {repair.ATTEMPTS} repair calls, only if verification finds something repair can fix"
    still = f"{len(ahead)} still to come ({', '.join(ahead)})"
    return f"Estimated model calls: {len(passes)} in all, {still}, {repairs}. {excluded}"


def scoped(job, llm: LLM, depth: Depth | None = None, dream: bool = True) -> Plan:
    """The plan's scope, with any questions still open. Writes no files."""
    job.event("plan", passes=_names(dream))
    plan = scope.seed(job.idea, job.direction, None if llm.offline else depth or DEFAULT_DEPTH)
    return _model_pass(job, scope, plan, llm, _names(dream))


def outlined(job, llm: LLM, plan: Plan, dream: bool = True) -> Plan:
    """The topics, ready to review. Writes no files; the summary is the checkpoint's."""
    plan = _model_pass(job, outline, plan, llm, _names(dream))
    plan = outline.with_assumptions(plan) if llm.offline else plan
    estimate = call_estimate(llm, dream)
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


def _dream_pass(job, module, plan: Plan, llm: LLM, names: list[str], **options: object) -> Plan:
    """One dream pass; `DreamFailed` is the only way it stops, however it went wrong."""
    try:
        return _pass(job, module.NAME, names, lambda: (run_pass(module, plan, llm, **options), []))
    except Exception as exc:  # noqa: BLE001 -- a failed dream is an outcome
        said = baseline.clean(str(exc))[:MOST_FAILURE_CHARS]
        raise DreamFailed(f"the {module.NAME} pass stopped: {said}.") from exc


def _skipped(job, module, plan: Plan, names: list[str]) -> Plan:
    """A pass with nothing to read costs no call, and still reaches the end of the list."""
    job.log(f"    {module.NAME} has nothing to read, so no call was made")
    return _pass(job, module.NAME, names, lambda: (plan, []))


def _dreamed(job, plan: Plan, llm: LLM, names: list[str], lenses: tuple[Lens, ...], per_lens: int) -> Plan:
    """One round, whole or not at all: new dreams join `plan`'s pool, or `DreamFailed` is raised."""
    collected = _dream_pass(job, collect, plan, llm, names, lenses=lenses, per_lens=per_lens)
    pool, notes = dreaming.admit(collected, plan, lenses)
    for module, waiting in ((evaluate, evaluate.fresh), (propose, propose.shortlist)):
        pool = _dream_pass(job, module, pool, llm, names) if waiting(pool) else _skipped(job, module, pool, names)
    pool, more = dreaming.settle(pool, plan)
    for note in [*notes, *more]:
        job.log(f"    {note}")
    added = len(pool.dreams) - len(plan.dreams)
    job.log(f"    {added} new dream(s) in a pool of {len(pool.dreams)}")
    job.event("dreamed", added=added, pool=len(pool.dreams))
    return pool


def _dreamed_or_noted(job, plan: Plan, llm: LLM, names: list[str]) -> Plan:
    """A plan's own dreaming: whatever goes wrong here is written down, and the plan goes on."""
    try:
        dreamt = _dreamed(job, plan, llm, names, LENSES, dreaming.PLAN_PER_LENS)
        if dreamt.dreams:
            return dreamt
        reason = "no dream came through it whole."
    except DreamFailed as exc:
        reason = str(exc)
    job.log(f"    dreaming failed: {reason}")
    job.event("dream_failed", error=reason)
    return plan.revised(dream_failure=reason)


def build(job, tree: Path, plan: Plan, llm: LLM, dream: bool = True) -> verify.PlanVerdict:
    """Everything after the review, whether a person approved it or nobody was asked."""
    tree = Path(tree)
    _refuse_if_taken(job, tree)
    job.project_dir = str(tree)
    names = _names(dream)

    for module in (connect, consider, start):
        plan = _model_pass(job, module, plan, llm, names)
    if dream:
        plan = _dreamed_or_noted(job, plan, llm, names)
    checked = repaired(job, plan, llm)
    # Again, because those passes take minutes. What is left is the instant between
    # here and the save's rename, in which another run's plan would still be replaced.
    _refuse_if_taken(job, tree)
    return _hand_back(job, tree, names, checked, save=True)


def _finish(job, tree: Path, plan: Plan, result: verify.PlanVerdict, attempts: int) -> None:
    if not plan.researched:
        job.log("Not researched: nothing here was checked against a source.")
    if result.ok:
        job.log(result.summary)
    if plan.dream_failure:
        job.log(f"Dreaming failed, and this plan does not depend on it: {plan.dream_failure} {render.RETRY}")
    if result.ok:
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


def run_plan(
    job, tree: Path, llm: LLM | None = None, depth: Depth | None = None, dream: bool = True
) -> verify.PlanVerdict:
    """Every half with nobody asked, or a re-render of the plan already in `tree`."""
    tree = Path(tree)
    if existing_plan(tree, job.idea, job.direction) is not None:
        return rerender(job, tree)
    llm = llm or OfflineLLM()
    return build(job, tree, outlined(job, llm, scoped(job, llm, depth, dream), dream), llm, dream)


def _held(tree: Path) -> Plan:
    """The plan in `tree`, refused unless green: a dream extends a plan that holds, so fix that first."""
    if not plan_path(tree).exists():
        raise PlanRefused(f"{tree} holds no plan. `proto plan` makes one; a dream needs a plan to extend.")
    try:
        plan = Plan.load(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{plan_path(tree)} cannot be read as a plan: {exc}") from exc
    result = verify.verdict(plan, render.render(plan))
    if not result.ok:
        raise PlanRefused(
            f"{tree} holds a plan that fails its checks, so nothing was changed and no model was called. "
            f"Red at {result.stage}: {result.summary} Mend {plan_path(tree)}, then rerun."
        )
    return plan


def _found(plan: Plan, dream_id: str) -> Dream:
    try:
        return dreaming.find(plan, dream_id)
    except ValueError as exc:
        raise PlanRefused(str(exc)) from exc


def _land(job, tree: Path, before: Plan, checked: Checked, names: list[str]) -> verify.PlanVerdict:
    """Hand back a change to a held plan, which must be green. Red, or raced, leaves the tree as it was."""
    if not checked.verdict.ok:
        tried = "".join(f"\n  {line}" for line in checked.tried)
        raise PlanRefused(
            f"Nothing was changed, because the result failed its checks.\n{checked.verdict.report()}{tried}"
        )
    if Plan.load(tree) != before:
        raise PlanRefused(f"{plan_path(tree)} changed while this ran, so this result was not written. Rerun it.")
    drawn = render.render(before)
    edited = sorted(name for name, page in render.read(tree).items() if name in drawn and page != drawn[name])
    if edited:
        job.log(f"  {', '.join(edited)} differed from plan.json and are drawn over: plan.json is the truth")
    return _hand_back(job, tree, names, checked, save=True)


def _once(job, plan: Plan) -> Checked:
    return Checked(plan, _verified(job, plan, 1, 1), 1, [])


def dream_round(
    job, tree: Path, llm: LLM, lenses: tuple[Lens, ...] = LENSES, per_lens: int = dreaming.ROUND_PER_LENS
) -> verify.PlanVerdict:
    """Another round into the pool of the plan in `tree`. A failed round leaves the tree as it was."""
    tree = Path(tree)
    job.project_dir = str(tree)
    plan = _held(tree)
    names = [*(module.NAME for module in DREAM_PASSES), RENDER]
    job.event("plan", passes=names)
    try:
        grown = _dreamed(job, plan, llm, names, lenses, per_lens)
    except DreamFailed as exc:
        raise PlanRefused(f"Dreaming failed, and nothing was changed: {exc} Rerun to try again.") from exc
    return _land(job, tree, plan, _once(job, grown.revised(dream_failure="")), names)


def promote(job, tree: Path, dream_id: str, llm: LLM) -> verify.PlanVerdict:
    """A person's promotion: the dream as a topic, connected and considered, or nothing at all."""
    tree = Path(tree)
    job.project_dir = str(tree)
    plan = _held(tree)
    dream = _found(plan, dream_id)
    names = [promote_pass.NAME, RENDER]
    job.event("plan", passes=names)
    try:
        grown = dreaming.promoted(plan, dream)
        fitted = _model_pass(job, promote_pass, grown, llm, names)
    except Exception as exc:  # noqa: BLE001 -- the plan on disk is good, and stays
        raise PlanRefused(f"Dream {dream_id} was not promoted, and nothing was changed: {exc}") from exc
    verdict = _land(job, tree, plan, repaired(job, fitted, llm), names)
    if verdict.ok:
        job.log(f"Dream {dream_id} is now a topic, and it is not researched: a person chose it, nothing checked it.")
    return verdict


def drop(job, tree: Path, dream_id: str, why: str) -> verify.PlanVerdict:
    """A person's ruling on a dream. Calls no model, and the dream stays so no round offers it again."""
    tree = Path(tree)
    job.project_dir = str(tree)
    plan = _held(tree)
    dream = _found(plan, dream_id)
    job.event("plan", passes=[RENDER])
    try:
        ruled = dreaming.dropped(plan, dream, why)
    except ValueError as exc:
        raise PlanRefused(str(exc)) from exc
    return _land(job, tree, plan, _once(job, ruled), [RENDER])


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
