"""One plan, start to finish, on the job seam.

Emits typed events (`plan`, `pass_started`, `pass_done`, `pass_failed`,
`finished`) that `protopilot.progress` folds. Standard library and proto.pilot's
own modules only, so any caller can run a plan without a view installed.

Three halves, so a caller can stop between them:
`scoped`, then its questions, `outlined`, then the review, then `build`. They run
on one job and share one event list. Only research reaches disk before every pass
has worked: the reviewed outline and each topic's transcript, under
`.protopilot/research/`, so a run that stops resumes there and asks no topic twice.
`existing_plan` treats any plan.json as finished, and only a whole one is written.

`repaired` verifies before the render, against pages drawn in memory, so repair
only ever edits data. `_hand_back` writes, then reads the tree and checks again. A
plan still red is handed back with a RUNBOOK, `finished` says `ok=False`, and the
CLI exits 1. A failed pass is a different thing: a
pass that returns nothing a plan can hold leaves no tree at all.

Dreaming is the exception, because dreams are extras. A plan keeps going when its
dreaming fails, and `dreams.md` says so. `dream_round`, `promote` and `drop` work on a
plan that is already green, and change nothing unless the result is green too.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from protopilot import registry
from protopilot.llm import (
    LLM,
    LLMError,
    OfflineLLM,
    Researched,
    ResearchFailed,
    ResearchUnavailable,
    research_result,
)
from protopilot.plan import baseline, dreaming, ledger, render, verify
from protopilot.plan.lenses import LENSES, Lens
from protopilot.plan.model import DEFAULT_DEPTH, Brief, Depth, Dream, Plan, Topic, TopicResearch, plan_path
from protopilot.plan.passes import (
    PlanPassError,
    collect,
    connect,
    consider,
    evaluate,
    misshapen,
    outline,
)
from protopilot.plan.passes import promote as promote_pass
from protopilot.plan.passes import propose, repair, research, run_pass, scope, start

#: Every model call a run makes, in order; the review sits after `BEFORE_REVIEW`. Research,
#: one call per topic, runs between the review and `connect`, so links rest on findings.
PLAN_PASSES = (scope, outline, connect, consider, start)
DREAM_PASSES = (collect, evaluate, propose)
PASSES = (*PLAN_PASSES, *DREAM_PASSES)
BEFORE_REVIEW = (scope, outline)
#: As measured once, on one topic, 2026-11-06 (docs/implementations/spec/plan-prototypes.md, Phase 1).
MINUTES_PER_TOPIC = 2
REPORTED_USD_PER_TOPIC = 0.4
RENDER = "render"
T = TypeVar("T")
#: A model's error can be a page of text, and it lands in `dreams.md`.
MOST_FAILURE_CHARS = 300
#: A research call refused by a slip is asked once more; a second refusal fails the topic (#56).
RESEARCH_ATTEMPTS = 2


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


def _same_ask(plan: Plan, idea: str, direction: str, brief: Brief | None) -> bool:
    asked = (baseline.clean(idea), baseline.clean(direction), brief or Brief())
    return asked == (plan.idea, plan.direction, plan.brief)


def _brief(job) -> Brief:
    """The brief a job was created with: the job holds it as plain data, which the plan validates."""
    return Brief.model_validate(getattr(job, "brief", None) or {})


def _steer(plan: Plan) -> str:
    steer = f" with direction {plan.direction!r}" if plan.direction else " with no direction"
    return f"{steer} and a brief of its own" if plan.brief else steer


def resumable(tree: Path, idea: str, direction: str = "", brief: Brief | None = None) -> Plan | None:
    """The reviewed outline a stopped run left in `tree`, None if it left none, refused if it is another plan's."""
    tree = Path(tree)
    if plan_path(tree).exists():
        return None
    try:
        draft = ledger.draft(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{ledger.research_dir(tree) / ledger.DRAFT_FILE} cannot be read: {exc}") from exc
    if draft is not None and not _same_ask(draft, idea, direction, brief):
        raise PlanRefused(
            f"{tree} holds research in progress for {draft.idea!r}{_steer(draft)}. "
            "Pick another --dir, or rerun with that same idea, direction and brief to resume it."
        )
    return draft


def existing_plan(tree: Path, idea: str, direction: str = "", brief: Brief | None = None) -> Plan | None:
    """The plan to re-render from `tree`, None if `tree` is free or resumable, refused otherwise.

    A plan for anything but this idea, direction and brief is refused: exiting 0 on it
    would hand back somebody else's plan as the answer to what was asked.
    """
    tree = Path(tree)
    if not tree.exists():
        return None
    if not plan_path(tree).exists():
        if resumable(tree, idea, direction, brief) is not None:
            return None
        raise PlanRefused(f"{tree} already exists and holds no plan; refusing to overwrite it")
    try:
        plan = Plan.load(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{plan_path(tree)} cannot be read as a plan: {exc}") from exc
    if not _same_ask(plan, idea, direction, brief):
        raise PlanRefused(
            f"{tree} already holds a plan for {plan.idea!r}{_steer(plan)}. "
            "Pick another --dir, or rerun with that same idea, direction and brief to re-render it."
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


def _names(dream: bool = True, researching: bool = True) -> list[str]:
    names = [module.NAME for module in _passes(dream)]
    if researching:
        names.insert(names.index(connect.NAME), research.NAME)
    return [*names, RENDER]


def _model_pass(job, module, plan: Plan, llm: LLM, names: list[str]) -> Plan:
    return _pass(job, module.NAME, names, lambda: (run_pass(module, plan, llm), []))


def research_refusal(llm: LLM) -> str:
    """Why `llm` cannot research, or an empty string. Offline is no refusal: the twin runs."""
    if llm.offline:
        return ""
    if not callable(getattr(llm, "research", None)):
        return "this backend has no research call"
    return str(getattr(llm, "research_refusal", ""))


def _research_line(llm: LLM, researching: bool, topics: int) -> str:
    if not researching:
        return "Research is off for this run, so the plan is stamped Not researched."
    if llm.offline:
        return "Research does not run offline, so the plan is stamped Not researched."
    refusal = research_refusal(llm)
    if refusal:
        return f"Research will not run ({refusal.rstrip('.')}), so the plan is stamped Not researched."
    minutes, usd = MINUTES_PER_TOPIC * topics, REPORTED_USD_PER_TOPIC * topics
    return (
        f"Research is {topics} of those calls, one per topic: about {MINUTES_PER_TOPIC} minutes and "
        f"${REPORTED_USD_PER_TOPIC:.2f} reported cost each as measured once, so about {minutes} minutes and "
        f"${usd:.2f} here. The reported cost is what the run would be priced at, not a subscription charge."
    )


def call_estimate(llm: LLM, dream: bool = True, researching: bool = True, topics: int = 0) -> str:
    """The model calls this run makes, counted from the passes it runs, for the checkpoint."""
    said = _research_line(llm, researching, topics)
    if llm.offline:
        return f"Estimated model calls: 0, because this run is offline. {said}"
    passes = _passes(dream)
    calls = topics if researching and not research_refusal(llm) else 0
    ahead = [module.NAME for module in passes if module not in BEFORE_REVIEW]
    ahead = [research.NAME, *ahead] if calls else ahead
    repairs = f"plus 0 to {repair.ATTEMPTS} repair calls, only if verification finds something repair can fix"
    still = f"{len(passes) - len(BEFORE_REVIEW) + calls} still to come ({', '.join(ahead)})"
    return f"Estimated model calls: {len(passes) + calls} in all, {still}, {repairs}. {said}"


def scoped(job, llm: LLM, depth: Depth | None = None, dream: bool = True, researching: bool = True) -> Plan:
    """The plan's scope, with any questions still open. Writes no files."""
    names = _names(dream, researching)
    job.event("plan", passes=names)
    plan = scope.seed(job.idea, job.direction, None if llm.offline else depth or DEFAULT_DEPTH, _brief(job))
    return _model_pass(job, scope, plan, llm, names)


def outlined(job, llm: LLM, plan: Plan, dream: bool = True, researching: bool = True) -> Plan:
    """The topics, ready to review. Writes no files; the summary is the checkpoint's."""
    plan = _model_pass(job, outline, plan, llm, _names(dream, researching))
    plan = outline.with_assumptions(plan) if llm.offline else plan
    estimate = call_estimate(llm, dream, researching, len(plan.topics))
    job.log(plan.summary())
    job.log(estimate)
    job.event("outline", topics=[t.slug for t in plan.topics], depth=plan.depth, estimate=estimate)
    return plan


def _short(exc: BaseException) -> str:
    return baseline.clean(str(exc))[:MOST_FAILURE_CHARS].rstrip(" .") or type(exc).__name__


def _asked(job, plan: Plan, llm, tree: Path, topic: Topic, label: str) -> Researched:
    """The research call, asked once more after a slip. Every stream not used is kept, never read as evidence."""
    system, user = research.build(plan, topic)
    for attempt in range(1, RESEARCH_ATTEMPTS + 1):
        try:
            return llm.research(system=system, user=user, schema=research.schema(plan), label=label)
        except ResearchFailed as exc:
            kept = ledger.write_refused(tree, topic.slug, exc.transcript) if exc.transcript else ""
            if attempt == RESEARCH_ATTEMPTS or not exc.retry:
                raise ResearchFailed(str(exc), exc.transcript, retry=False, kept=kept) from exc
            where = f"; its stream is kept at {kept}" if kept else ""
            job.log(f"    {topic.slug}: {_short(exc)}{where}; asking once more")
    raise AssertionError("unreachable")


def _research_topic(job, plan: Plan, llm, tree: Path, topic: Topic) -> Plan:
    """One topic researched, or recorded as failed. A transcript already on disk is replayed, not paid for again."""
    label = f"{research.NAME} {topic.slug}"
    stored = ledger.read_transcript(tree, topic.slug)
    started = time.monotonic()
    try:
        if stored is None:
            got = _asked(job, plan, llm, tree, topic, label)
            transcript, data = got.transcript, got.data
        else:
            transcript, data = stored, research_result(stored, label)
        fault = misshapen(research.schema(plan), data)
        if fault:
            raise PlanPassError(f"pass {label!r} returned output that cannot be used: {fault}")
        after, record = research.apply(plan, topic.slug, data, ledger.fetches(transcript))
    except ResearchUnavailable:
        raise
    except (LLMError, PlanPassError, ValueError) as exc:
        failure = _short(exc)
        if isinstance(exc, ResearchFailed) and exc.kept:
            failure = f"{failure}; its stream is kept at {exc.kept}"
        job.log(f"    {topic.slug}: research failed, and the topic goes on unresearched: {failure}")
        job.event("research_failed", topic=topic.slug, error=failure)
        record = TopicResearch(topic=topic.slug, state="failed", failure=failure)
        return plan.revised(research=[*plan.research, record])
    name = (
        ledger.write_transcript(tree, topic.slug, transcript) if stored is None else ledger.transcript_name(topic.slug)
    )
    record = record.model_copy(update={"transcript": name, "sha256": ledger.digest(transcript)})
    usable = sum(fetch.usable for fetch in record.fetches)
    cited = sum(not finding.assumption for t in after.topics if t.slug == topic.slug for finding in t.findings)
    how = "replayed from its transcript" if stored is not None else f"{time.monotonic() - started:.0f}s"
    job.log(f"    {topic.slug}: {cited} cited finding(s), {usable} of {len(record.fetches)} fetch(es) usable ({how})")
    job.event("researched", topic=topic.slug, state=record.state, cited=cited, fetched=usable)
    return after.revised(research=[*after.research, record])


def _researched(job, plan: Plan, llm: LLM, tree: Path, names: list[str]) -> Plan:
    """Every topic in turn, each saved as it lands; a topic that fails costs only itself."""

    def work() -> tuple[Plan, list[str]]:
        if llm.offline:
            job.log("    offline, so nothing is read and nothing is researched")
            return research.offline(plan), []
        refusal = research_refusal(llm)
        if refusal:
            job.log(f"    research did not run: {refusal}")
            return plan.revised(research_failure=refusal), []
        ledger.save_draft(tree, plan)
        current = plan
        for topic in plan.topics:
            try:
                current = _research_topic(job, current, llm, tree, topic)
            except ResearchUnavailable as exc:
                job.log(f"    research did not run: {exc}")
                return current.revised(research_failure=str(exc)), []
        files = [f"{ledger.RESEARCH_DIR}/{record.transcript}" for record in current.research if record.transcript]
        return current, files

    return _pass(job, research.NAME, names, work)


def _refuse_if_taken(job, tree: Path) -> None:
    if existing_plan(tree, job.idea, job.direction, _brief(job)) is not None:
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


def _repair_once(job, llm: LLM, checked: Checked, entry: Plan, rejection: str, held: Plan | None) -> str | None:
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
        after = run_pass(repair, plan, llm, repair.failure(result, rejection, held))
    except (LLMError, PlanPassError) as exc:
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
    reason = repair.rejected(entry, after) or (repair.unsettled(held, after) if held else "")
    reason = reason or repair.worsened(result, after)
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


def repaired(job, plan: Plan, llm: LLM, held: Plan | None = None) -> Checked:
    """Verify, and on red repair and verify again, up to `repair.ATTEMPTS` times, then stop.

    `held` is the plan before a promotion, whose links and steps a repair may not move.
    """
    checked = Checked(plan, _verified(job, plan, 1, repair.ATTEMPTS), 1, [])
    rejection: str | None = ""
    while not checked.verdict.ok and checked.attempts <= repair.ATTEMPTS and rejection is not None:
        rejection = _repair_once(job, llm, checked, plan, rejection, held)
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
        if save:
            ledger.forget_draft(tree)
        return None, [*saved, *_drawn(plan, tree, runbook(checked.verdict))]

    _pass(job, RENDER, names, written)
    # The ledger as its transcripts on disk tell it, so a fetch typed into plan.json earns nothing.
    landed = verify.verdict(ledger.reconciled(plan, tree), render.read(tree))
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


def _guarded(name: str, work: Callable[[], T]) -> T:
    """`work`, with a backend's failure or bad output as `DreamFailed`. A bug here stays a bug."""
    try:
        return work()
    except (LLMError, PlanPassError) as exc:
        said = baseline.clean(str(exc))[:MOST_FAILURE_CHARS].rstrip(" .") or type(exc).__name__
        raise DreamFailed(f"the {name} pass stopped: {said}.") from exc


def _dream_pass(job, module, plan: Plan, llm: LLM, names: list[str], **options: object) -> Plan:
    return _guarded(
        module.NAME, lambda: _pass(job, module.NAME, names, lambda: (run_pass(module, plan, llm, **options), []))
    )


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
    judged = pool
    pool, more = _guarded("settling", lambda: dreaming.settle(judged, plan))
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


def build(job, tree: Path, plan: Plan, llm: LLM, dream: bool = True, researching: bool = True) -> verify.PlanVerdict:
    """Everything after the review, whether a person approved it or nobody was asked."""
    tree = Path(tree)
    _refuse_if_taken(job, tree)
    job.project_dir = str(tree)
    names = _names(dream, researching)

    if researching:
        plan = _researched(job, plan, llm, tree, names)
    for module in (connect, consider, start):
        plan = _model_pass(job, module, plan, llm, names)
    if dream:
        plan = _dreamed_or_noted(job, plan, llm, names)
    checked = repaired(job, plan, llm)
    # Again, because those passes take minutes. What is left is the instant between
    # here and the save's rename, in which another run's plan would still be replaced.
    _refuse_if_taken(job, tree)
    try:
        return _hand_back(job, tree, names, checked, save=True)
    finally:
        _register(checked.plan, tree)  # a page blocked after the save still hands the tree back


def _register(plan: Plan, tree: Path) -> None:
    """List a landed plan, red or green, so `proto ls` and `proto rm` can find it; a listed one keeps its date."""
    if not plan_path(tree).exists():
        return
    resolved = str(tree.resolve())
    if any(e.path == resolved and e.kind == registry.PLAN for e in registry.load()):
        return
    registry.record(slug=plan.slug, name=plan.title, path=tree, idea=plan.idea)


def _research_account(plan: Plan) -> list[str]:
    """The run's last word on research, topic by topic where it differs."""
    if not plan.researched:
        why = [f"Research did not run: {plan.research_failure}"] if plan.research_failure else []
        return ["Not researched: nothing here was checked against a source.", *why]
    done = [t.title for t in plan.topics if render.topic_research(plan, t)[0]]
    left = [t.title for t in plan.topics if not render.topic_research(plan, t)[0]]
    said = (
        f"Researched {len(done)} of {len(plan.topics)} topics, citing {len(plan.sources)} source(s) fetched this run."
    )
    return [said, *([f"Not researched: {', '.join(left)}."] if left else [])]


def _finish(job, tree: Path, plan: Plan, result: verify.PlanVerdict, attempts: int) -> None:
    for line in _research_account(plan):
        job.log(line)
    if result.ok:
        job.log(result.summary)
    if plan.dream_failure:
        job.log(f"Dreaming failed, and this plan does not depend on it: {plan.dream_failure} {render.RETRY}")
    if result.ok:
        job.log(f"\nPlan at {tree}. Start with {render.PLAN_FILE}.")
    else:
        job.log(f"Not verified: red at {result.stage} after {attempts} check(s).")
        job.log(f"\nThe tree is at {tree}, and what is still wrong is written down in {render.RUNBOOK_FILE}.")
    job.event("finished", ok=result.ok, attempts=attempts, project_dir=str(tree))


#: The numbered lines under a runbook's "What was tried", as `verify.runbook` writes them.
TRIED = re.compile(r"## What was tried\n\n(.*?)\n\n## ", re.DOTALL)
RERENDER_TRIED = "A re-render calls no model, so no repair ran."


def _tried_before(tree: Path) -> list[str]:
    """What the runbook this tool last wrote says was tried, so a re-render keeps the history."""
    path = tree / render.RUNBOOK_FILE
    if not render.is_ours(path):
        return []
    found = TRIED.search(path.read_text(encoding="utf-8", errors="replace"))
    lines = [re.sub(r"^\d+\. ", "", line) for line in found.group(1).splitlines()] if found else []
    return [line for line in lines if line and line != "No repair ran."]


def rerender(job, tree: Path) -> verify.PlanVerdict:
    """Verify the plan already in `tree` and draw it again. No model, so no repair: plan.json may be hand-edited.

    The ledger is read from the transcripts on disk, so a hand edit cannot make a source fetched.
    """
    tree = Path(tree)
    job.project_dir = str(tree)
    job.log(f"{tree} already holds this plan; checking it and drawing it again, with no model call.")
    job.event("plan", passes=[RENDER])
    plan = ledger.reconciled(Plan.load(tree), tree)
    result = _verified(job, plan, 1, 1)
    earlier = _tried_before(tree)
    tried = [] if result.ok else [*earlier, *([] if earlier[-1:] == [RERENDER_TRIED] else [RERENDER_TRIED])]
    if not result.ok:
        job.event("exhausted", attempts=1, stage=result.stage)
    try:
        return _hand_back(job, tree, [RENDER], Checked(plan, result, 1, tried), save=False)
    finally:
        _register(plan, tree)  # a plan made before plans were listed joins the list here


def resume_refusal(
    tree: Path, draft: Plan, llm: LLM | None, researching: bool = True, depth: Depth | None = None
) -> str:
    """Why this run may not resume `draft`, or an empty string. A resume that skipped research would delete it.

    With no `llm`, only what needs no backend is judged, so a caller can refuse before building one.
    """
    if not researching:
        return f"{tree} holds research in progress. Rerun without --no-research to resume it, or pick another --dir."
    if depth and depth != draft.depth:
        return (
            f"{tree} holds research in progress at depth {draft.depth}, and a resumed run keeps it. "
            "Drop --depth, or pick another --dir."
        )
    if llm is None:
        return ""
    if llm.offline:
        return f"{tree} holds research in progress, and offline cannot research. Resume with a model backend."
    refusal = research_refusal(llm)
    return f"{tree} holds research in progress, and this backend cannot resume it: {refusal}" if refusal else ""


def resume(
    job,
    tree: Path,
    draft: Plan,
    llm: LLM,
    dream: bool = True,
    researching: bool = True,
    depth: Depth | None = None,
) -> verify.PlanVerdict:
    """Pick up a run that stopped after its review: topics with a transcript are replayed, the rest researched."""
    tree = Path(tree)
    refusal = resume_refusal(tree, draft, llm, researching, depth)
    if refusal:
        raise PlanRefused(refusal)
    done = [t.slug for t in draft.topics if ledger.read_transcript(tree, t.slug) is not None]
    job.log(f"{tree} holds a reviewed outline; resuming, with {len(done)} of {len(draft.topics)} topics researched.")
    job.event("plan", passes=_names(dream))
    return build(job, tree, draft, llm, dream)


def run_plan(
    job, tree: Path, llm: LLM | None = None, depth: Depth | None = None, dream: bool = True, researching: bool = True
) -> verify.PlanVerdict:
    """Every half with nobody asked, a resumed run, or a re-render of the plan already in `tree`."""
    tree = Path(tree)
    if existing_plan(tree, job.idea, job.direction, _brief(job)) is not None:
        return rerender(job, tree)
    llm = llm or OfflineLLM()
    draft = resumable(tree, job.idea, job.direction, _brief(job))
    if draft is not None:
        return resume(job, tree, draft, llm, dream, researching, depth)
    plan = outlined(job, llm, scoped(job, llm, depth, dream, researching), dream, researching)
    return build(job, tree, plan, llm, dream, researching)


def _refuse_if_blocked(plan: Plan, tree: Path) -> None:
    blocked = ", ".join(str(path) for path in render.blocked(plan, tree))
    if blocked:
        raise PlanRefused(f"Nothing was changed, because a page needs this name: {blocked}. Move it, then rerun.")


def _held(tree: Path) -> Plan:
    """The plan in `tree`, refused unless green: a dream extends a plan that holds, so fix that first.

    It is the plan as its transcripts tell it, so a verb that saves never writes back a forged state.
    """
    if not plan_path(tree).exists():
        raise PlanRefused(f"{tree} holds no plan. `proto plan` makes one; a dream needs a plan to extend.")
    try:
        plan = Plan.load(tree)
    except (OSError, ValueError) as exc:
        raise PlanRefused(f"{plan_path(tree)} cannot be read as a plan: {exc}") from exc
    plan = ledger.reconciled(plan, tree)
    result = verify.verdict(plan, render.render(plan))
    if not result.ok:
        raise PlanRefused(
            f"{tree} holds a plan that fails its checks, so nothing was changed and no model was called. "
            f"Red at {result.stage}: {result.summary} Mend {plan_path(tree)}, then rerun."
        )
    _refuse_if_blocked(plan, tree)
    return plan


def _found(plan: Plan, dream_id: str) -> Dream:
    try:
        return dreaming.find(plan, dream_id)
    except ValueError as exc:
        raise PlanRefused(str(exc)) from exc


def _put_back(tree: Path, before: Plan, saved: bytes) -> str:
    """The tree as `before` drew it, and a true account of how far that got."""
    try:
        plan_path(tree).write_bytes(saved)
        render.write(before, tree)
    except (OSError, render.PageBlocked):
        return f"{plan_path(tree)} and the pages may disagree, and a rerun may repeat it. Check them first"
    return "the tree is back as it was"


def _land(job, tree: Path, before: Plan, checked: Checked, names: list[str]) -> verify.PlanVerdict:
    """Hand back a change to a held plan, which must be green. Red, or raced, leaves the tree as it was."""
    if not checked.verdict.ok:
        tried = "".join(f"\n  {line}" for line in checked.tried)
        raise PlanRefused(
            f"Nothing was changed, because the result failed its checks.\n{checked.verdict.report()}{tried}"
        )
    try:
        moved = ledger.reconciled(Plan.load(tree), tree) != before
    except (OSError, ValueError):
        moved = True
    if moved:
        raise PlanRefused(f"{plan_path(tree)} changed while this ran, so this result was not written. Rerun it.")
    _refuse_if_blocked(checked.plan, tree)
    drawn = render.render(before)
    edited = sorted(name for name, page in render.read(tree).items() if name in drawn and page != drawn[name])
    if edited:
        job.log(f"  {', '.join(edited)} differed from plan.json and are drawn over: plan.json is the truth")
    saved = plan_path(tree).read_bytes()
    try:
        return _hand_back(job, tree, names, checked, save=True)
    except (OSError, PlanRefused) as exc:
        raise PlanRefused(f"This result could not be drawn, so {_put_back(tree, before, saved)}: {exc}") from exc


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
    added = len(grown.dreams) > len(plan.dreams)
    ran_empty = "" if grown.dreams else "a round ran, and no dream came through it whole."
    note = "" if added else plan.dream_failure or ran_empty
    return _land(job, tree, plan, _once(job, grown.revised(dream_failure=note)), names)


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
    except (LLMError, PlanPassError, ValueError) as exc:
        raise PlanRefused(f"Dream {dream_id} was not promoted, and nothing was changed: {exc}") from exc
    verdict = _land(job, tree, plan, repaired(job, fitted, llm, plan), names)
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


def after_dream_failure(tree: Path) -> str:
    """What an unexpected stop left, for the dream verbs, whose rerun is not `proto plan`'s."""
    return (
        f"Something unexpected stopped this, so {tree} may hold it in part. Read {render.DREAMS_FILE} before "
        "rerunning: `proto dream` calls the model and adds a round, and a verb that landed will say so."
    )


def after_failure(tree: Path) -> str:
    """What a failed run left in `tree`, and what running the command again does."""
    if not plan_path(tree).exists() and (ledger.research_dir(tree) / ledger.DRAFT_FILE).is_file():
        return (
            f"{tree} keeps the reviewed outline and the research done so far. Rerun the same command to "
            "resume: no topic already researched is asked again."
        )
    if plan_path(tree).exists():
        return (
            f"{tree} holds the whole plan but maybe not every page. Any page there may be out of date. "
            "Rerun to check it and draw it again, with no model call."
        )
    if tree.exists():
        return f"{tree} exists and holds no plan, so a rerun would be refused. Remove it, or pick another --dir."
    return f"Nothing was written to {tree}. Rerunning starts over from scope, and any review edits are lost."
