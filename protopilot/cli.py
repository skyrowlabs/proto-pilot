"""The command line.

proto plan "start a community tool library"
proto dream | dream promote d1 | dream drop d2 --why "..."
proto answer 1
proto research scope --deeper
proto topic add "Insurance" --why "..." | topic drop scope --why "..." | topic rename scope "The boundary"
proto ls | rm | prune | doctor
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click

from protopilot import __version__, registry
from protopilot.llm import ClaudeCodeLLM, ClaudeLLM, LLMError, build_llm
from protopilot.plan.lenses import LENS_SLUGS
from protopilot.plan.model import DEFAULT_DEPTH, TOPIC_COUNTS

if TYPE_CHECKING:
    from protopilot.plan.model import Depth

FOLLOW_INTERVAL = 0.02
PLAN_REVIEW_PROMPT = "Write this plan? Enter accepts, or: add TITLE | drop N | rename N TITLE | quit"

#: Said once by `proto ls` when it lists a row an older version wrote for a prototype.
OLD_ROWS = "proto.pilot no longer runs prototypes. Their folders are untouched, and `proto prune` forgets them."
#: Said by `proto rm` on an older version's prototype, which it will not delete.
OLD_PROTOTYPE = (
    "{path} is a prototype from an older proto.pilot, and this version removes plans only. "
    "If it was a web prototype, run `docker compose down -v` there; then delete the folder by hand."
)


def _echo(message: str) -> None:
    click.echo(message)


@click.group()
@click.version_option(__version__, prog_name="proto-pilot")
def main() -> None:
    """Turn an idea and a little direction into a plan you can work from."""


def _follow(job, shown: int = 0) -> None:
    """Print a job's log from line `shown` as it grows, until the job has finished."""
    while True:
        # Read before draining: `finished_at` is set last, so nothing logged is missed.
        finished = bool(job.finished_at)
        lines = job.lines[shown:]
        for line in lines:
            _echo(line)
        shown += len(lines)
        if finished:
            return
        time.sleep(FOLLOW_INTERVAL)


def _stdin_is_terminal() -> bool:
    return bool(sys.stdin and sys.stdin.isatty())


def _plan_step(job, target: Path, work, after=None):
    """One half of a plan on its job, followed to the end; returns what `work` returned."""
    from protopilot.jobs import STORE
    from protopilot.plan import pipeline

    produced: list = []
    refused: list[str] = []

    def run(j) -> None:
        try:
            produced.append(work(j))
        except pipeline.PlanRefused as exc:
            refused.append(str(exc))
            raise

    shown = len(job.lines)
    job.finished_at = ""  # the halves share a job, and `_follow` waits on this
    STORE.run(job, run)
    _follow(job, shown)
    if refused:
        raise click.ClickException(refused[0])  # it says all there is, and what to do next
    if job.status != "done":
        raise click.ClickException(f"{job.error}\n  {(after or pipeline.after_failure)(target)}")
    return produced[0]


def _ask_questions(plan):
    """Scope's questions, one prompt each; Enter leaves one open for `PLAN.md` to list."""
    from protopilot.plan.passes import scope

    answers = {}
    for question in plan.questions:
        answers[question] = click.prompt(f"{question} (Enter leaves it open)", default="", show_default=False)
    return scope.answered(plan, answers)


def _review_edit(plan, line: str):
    """One line of the review, applied; a bad one raises `ValueError` with the reason."""
    from protopilot.plan.passes import outline

    verb, _, rest = line.partition(" ")
    rest = rest.strip()
    if verb == "add":
        if not rest:
            raise ValueError("add needs a title: add TITLE")
        outline.addable(plan, rest)
        return outline.add(plan, rest, click.prompt("Why does it matter?", default="", show_default=False))
    if verb == "drop":
        return outline.drop(plan, rest)
    if verb == "rename":
        which, _, title = rest.partition(" ")
        return outline.rename(plan, which, title)
    raise ValueError(f"not a review command: {verb!r}")


def _review_outline(plan):
    """The checkpoint: edit until a person accepts."""
    while True:
        line = click.prompt(PLAN_REVIEW_PROMPT, default="", show_default=False).strip()
        if line.lower() in ("", "y", "yes"):
            return plan
        if line.lower() in ("n", "no", "quit"):
            raise click.Abort()
        try:
            plan = _review_edit(plan, line)
        except ValueError as exc:
            _echo(f"  {exc}")
            continue
        _echo(plan.summary())


@main.command(name="plan")
@click.argument("idea")
@click.option("--dir", "directory", default=None, help="Target directory (default: ./<slug>).")
@click.option("--direction", default="", help="Extra steer: scope, emphasis, constraints.")
@click.option(
    "--depth",
    type=click.Choice(list(TOPIC_COUNTS)),
    default=None,
    help=(
        f"Topic count, and research effort: how many findings and pages each topic gets (default: {DEFAULT_DEPTH}). "
        "Needs the model."
    ),
)
@click.option("--offline", is_flag=True, help="Deterministic baseline; no API calls.")
@click.option(
    "--backend",
    type=click.Choice(["api", "claude-code", "offline"]),
    default=None,
    help="api bills API credit; claude-code bills a Claude subscription.",
)
@click.option("--yes", "-y", is_flag=True, help="Skip scope's questions and the outline review.")
@click.option("--no-dream", is_flag=True, help="Skip dreaming; `proto dream` can start the pool later.")
@click.option(
    "--no-research",
    is_flag=True,
    help="Skip research, which takes minutes a topic; the plan is stamped Not researched.",
)
def plan_command(
    idea: str,
    directory: str | None,
    direction: str,
    depth: str | None,
    offline: bool,
    backend: str | None,
    yes: bool,
    no_dream: bool,
    no_research: bool,
) -> None:
    """Turn IDEA into an organised set of text plans, research each topic on the web, and dream a little.

    Research runs on the claude-code backend, one call per topic, and a run that stops
    during it resumes when rerun. Offline, or with --no-research, the plan is stamped
    Not researched.
    """
    from protopilot.jobs import STORE
    from protopilot.plan import baseline, pipeline

    if not baseline.clean(idea):
        raise click.ClickException("`proto plan` needs an idea; it was given an empty one")

    target = Path(directory).resolve() if directory else Path.cwd() / baseline.slug_for(idea)
    try:
        existing = pipeline.existing_plan(target, idea, direction)
        draft = None if existing else pipeline.resumable(target, idea, direction)
    except pipeline.PlanRefused as exc:
        raise click.ClickException(str(exc)) from exc

    if existing is not None:
        if depth and depth != existing.depth:
            raise click.ClickException(
                f"{target} already holds this plan at depth {existing.depth or 'none (offline baseline)'}, "
                "and a re-render cannot change that. Drop --depth, or pick another --dir."
            )
        result = _plan_step(STORE.create(idea, direction), target, lambda j: pipeline.rerender(j, target))
        sys.exit(0 if result.ok else 1)

    if draft is not None:
        _resume(target, draft, depth, offline, backend, not no_dream, not no_research)
        return

    if not yes and not _stdin_is_terminal():
        # `click.prompt` would abort on EOF, and wait forever on a pipe nobody writes to.
        raise click.ClickException(
            "`proto plan` reviews the outline at a prompt, and stdin is not a terminal. "
            "Pass --yes to accept the outline as written. No model was called."
        )
    try:
        llm = build_llm(offline=offline, backend=backend)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    if llm.offline and depth:
        raise click.ClickException(
            "--depth needs the model, and the backend for this run is offline, which always writes "
            "the same six topics. Drop --depth, or choose a backend that calls the model."
        )
    researching = not no_research
    _refuse_unresearchable(llm, researching)

    job = STORE.create(idea, direction)
    dream = not no_dream
    plan = _plan_step(job, target, lambda j: pipeline.scoped(j, llm, cast("Depth | None", depth), dream, researching))
    if not yes:
        plan = _ask_questions(plan)
    plan = _plan_step(job, target, lambda j: pipeline.outlined(j, llm, plan, dream, researching))
    _echo(f"\n  -> {target}\n")
    if not yes:
        plan = _review_outline(plan)
    result = _plan_step(job, target, lambda j: pipeline.build(j, target, plan, llm, dream, researching))
    if not result.ok:
        sys.exit(1)  # the tree is handed back with a RUNBOOK, and the exit code says it is red


def _refuse_unresearchable(llm, researching: bool) -> None:
    """A backend that cannot research is refused before any call, rather than billed for a stamped plan."""
    # Only a backend that says it cannot is refused here. One with no research call at all is
    # labelled by the pipeline instead, and runs unresearched.
    refusal = str(getattr(llm, "research_refusal", "")) if researching and not llm.offline else ""
    if refusal:
        raise click.ClickException(f"{refusal} No model was called.")


def _resume(target: Path, draft, depth: str | None, offline: bool, backend: str | None, dream: bool, researching: bool):
    """A run that stopped after its review, picked up where it stopped, with no question asked again."""
    from protopilot.jobs import STORE
    from protopilot.plan import pipeline

    # The pipeline holds the same guard, so no caller can land an unresearched plan over it.
    asked = cast("Depth | None", depth)
    refusal = pipeline.resume_refusal(target, draft, None, researching, asked)
    if refusal:
        raise click.ClickException(refusal)  # before any backend is built
    try:
        llm = build_llm(offline=offline, backend=backend)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    refusal = pipeline.resume_refusal(target, draft, llm, researching, asked)
    if refusal:
        raise click.ClickException(refusal)
    job = STORE.create(draft.idea, draft.direction)
    result = _plan_step(job, target, lambda j: pipeline.resume(j, target, draft, llm, dream, researching))
    if not result.ok:
        sys.exit(1)


DREAM_ROUND = "round"


class _DreamCommand(click.Group):
    """`proto dream [DIR]` and its verbs share a position, so a first word that is a verb is one.

    Anything else is a round, so a directory called `promote` is written `./promote`.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        first = args[0] if args else ""
        named = first in self.commands or first in ctx.help_option_names
        return super().parse_args(ctx, args if named else [DREAM_ROUND, *args])


def _dream_step(target: Path, work) -> None:
    """Run one pool change as its own job, and exit as a red plan exits."""
    from protopilot.jobs import STORE
    from protopilot.plan import pipeline

    if not _plan_step(STORE.create(str(target)), target, work, pipeline.after_dream_failure).ok:
        sys.exit(1)


def _dream_llm(offline: bool, backend: str | None):
    try:
        return build_llm(offline=offline, backend=backend)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc


def _dream_options(command):
    """The flags every dream verb that may call a model takes, spelt as `proto plan` spells them."""
    command = click.option("--offline", is_flag=True, help="Deterministic templates; no API calls.")(command)
    return click.option(
        "--backend",
        type=click.Choice(["api", "claude-code", "offline"]),
        default=None,
        help="api bills API credit; claude-code bills a Claude subscription.",
    )(command)


@main.group(name="dream", cls=_DreamCommand)
def dream_group() -> None:
    """Add to a plan's pool of dreams, or settle one.

    `proto dream [DIR]` runs another round, and takes `round`'s options. A directory named
    like a verb is written `./promote`.
    """


@dream_group.command(name=DREAM_ROUND)
@click.argument("directory", default=".", metavar="[DIR]")
@click.option(
    "--lens",
    "lenses",
    type=click.Choice(LENS_SLUGS),
    multiple=True,
    help="Dream through this lens only; repeat for more.",
)
@_dream_options
def dream_round_command(directory: str, lenses: tuple[str, ...], offline: bool, backend: str | None) -> None:
    """Run another round into the pool of the plan in DIR (default: cwd)."""
    from protopilot.plan import lenses as lens_data
    from protopilot.plan import pipeline

    llm = _dream_llm(offline, backend)
    target = Path(directory).resolve()
    _dream_step(target, lambda j: pipeline.dream_round(j, target, llm, lens_data.chosen(lenses)))


@dream_group.command(name="promote")
@click.argument("dream_id", metavar="ID")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
@_dream_options
def dream_promote_command(dream_id: str, directory: str, offline: bool, backend: str | None) -> None:
    """Turn dream ID into a topic, connected and verified. Nothing else can.

    Offline, the topic depends on the dream's anchor and has no risks, unknowns or
    decisions. Either way it is not researched.
    """
    from protopilot.plan import pipeline

    llm = _dream_llm(offline, backend)
    target = Path(directory).resolve()
    _dream_step(target, lambda j: pipeline.promote(j, target, dream_id, llm))


@dream_group.command(name="drop")
@click.argument("dream_id", metavar="ID")
@click.option("--why", required=True, help="What ruled it out; it stays beside the dream.")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
def dream_drop_command(dream_id: str, why: str, directory: str) -> None:
    """Rule out dream ID, so no later round offers it again. Calls no model."""
    from protopilot.plan import pipeline

    target = Path(directory).resolve()
    _dream_step(target, lambda j: pipeline.drop(j, target, dream_id, why))


def _revise_step(target: Path, work) -> None:
    """Run one change to a finished plan as its own job, and exit as a red plan exits."""
    from protopilot.jobs import STORE
    from protopilot.plan import pipeline

    if not _plan_step(STORE.create(str(target)), target, work, pipeline.after_revise_failure).ok:
        sys.exit(1)


@main.command(name="answer")
@click.argument("number", required=False, type=click.IntRange(min=1), metavar="[N]")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
def answer_command(number: int | None, directory: str) -> None:
    """Answer open question N of a plan, or each in turn. Calls no model.

    An answer becomes a constraint and the question leaves the list. Enter leaves a
    question open. Nothing else moves: no topic is outlined or researched again.
    """
    from protopilot.plan import baseline, pipeline

    target = Path(directory).resolve()
    try:
        questions = pipeline.open_questions(target)
    except pipeline.PlanRefused as exc:
        raise click.ClickException(str(exc)) from exc
    if not questions:
        _echo("This plan has no open question, so there is nothing to answer.")
        return
    if number and number > len(questions):
        raise click.ClickException(
            f"This plan has {len(questions)} open question(s), so there is no question {number}."
        )
    asked = [number] if number else range(1, len(questions) + 1)
    answers = {}
    for n in asked:
        prompt = f"{n}. {questions[n - 1]} (Enter leaves it open)"
        answers[questions[n - 1]] = click.prompt(prompt, default="", show_default=False)
    if not any(baseline.clean(said) for said in answers.values()):
        _echo("No answer was given, so nothing was changed.")
        return
    _revise_step(target, lambda j: pipeline.answer(j, target, answers))


@main.group(name="topic")
def topic_group() -> None:
    """Change the topics of a plan that is already made."""


@topic_group.command(name="rename")
@click.argument("slug", metavar="SLUG")
@click.argument("title", metavar="TITLE")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
def topic_rename_command(slug: str, title: str, directory: str) -> None:
    """Give topic SLUG the title TITLE. Calls no model.

    The slug is the topic's identity and does not change, so its file, links, steps,
    dreams and research stay where they are.
    """
    from protopilot.plan import pipeline

    target = Path(directory).resolve()
    _revise_step(target, lambda j: pipeline.rename_topic(j, target, slug, title))


@topic_group.command(name="drop")
@click.argument("slug", metavar="SLUG")
@click.option("--why", required=True, help="What ruled it out; it stays in the plan.")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
@_dream_options
def topic_drop_command(slug: str, why: str, directory: str, offline: bool, backend: str | None) -> None:
    """Rule out topic SLUG, with what pointed at it: its links, its step, its sources nothing else cites.

    A dream that extended it is set aside, never deleted, and the topic is remembered
    with the reason. A model is called only if the drop leaves no first step.
    """
    from protopilot.plan import pipeline

    target = Path(directory).resolve()
    _revise_step(
        target, lambda j: pipeline.drop_topic(j, target, slug, why, lambda: build_llm(offline=offline, backend=backend))
    )


@topic_group.command(name="add")
@click.argument("title", metavar="TITLE")
@click.option("--why", required=True, help="One line on why it matters to the idea.")
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
@_dream_options
def topic_add_command(title: str, why: str, directory: str, offline: bool, backend: str | None) -> None:
    """Add the topic TITLE to a plan, connected and verified.

    Offline, it is linked to nothing and has no risks, unknowns or decisions. Either
    way it is not researched.
    """
    from protopilot.plan import pipeline

    llm = _dream_llm(offline, backend)
    target = Path(directory).resolve()
    _revise_step(target, lambda j: pipeline.add_topic(j, target, title, why, llm))


@main.command(name="research")
@click.argument("slug", metavar="SLUG")
@click.option(
    "--deeper",
    is_flag=True,
    help="Give this one call the findings and pages of the next --depth up. The plan's depth is not changed.",
)
@click.option("--dir", "directory", default=".", help="Plan directory (default: cwd).")
@_dream_options
def research_command(slug: str, deeper: bool, directory: str, offline: bool, backend: str | None) -> None:
    """Research topic SLUG of a plan again, on the web, and replace what it found.

    One research call on the claude-code backend, then the topic's links and notes are
    fitted again; no other topic is written. Its earlier transcript stays beside the new
    one. It does not run offline, and a try that stopped after its call is replayed.
    """
    from protopilot.plan import pipeline

    llm = _dream_llm(offline, backend)
    if llm.offline:
        raise click.ClickException(
            "`proto research` reads the web, and offline reads nothing. Choose a backend that researches. "
            "Nothing was changed."
        )
    _refuse_unresearchable(llm, True)
    target = Path(directory).resolve()
    _revise_step(target, lambda j: pipeline.research_topic(j, target, slug, llm, deeper))


@main.command(name="ls")
def list_projects() -> None:
    """List every plan made on this machine.

    Read-only: a missing tree is reported as `gone`, and only `proto prune` forgets one.
    """
    entries = registry.load()
    if not entries:
        _echo('no plans yet -- `proto plan "an idea"` makes one')
        return

    width = max(len(e.slug) for e in entries)
    for entry in entries:
        _echo(f"  {entry.state:<5} {entry.kind:<4}  {entry.slug:<{width}}  {entry.path}")

    states = [e.state for e in entries]
    gone, old = states.count(registry.GONE), states.count(registry.OLD)
    _echo(f"\n  {len(entries) - gone - old} plan(s)")
    if gone:
        _echo(f"  {gone} whose plan is gone -- `proto prune` to forget them")
    if old:
        _echo(f"  {old} old: {OLD_ROWS}")


@main.command()
@click.option("--yes", "-y", is_flag=True)
def prune(yes: bool) -> None:
    """Forget entries whose plan is gone, and prototypes an older version made.

    Only the list is touched, never a folder.
    """
    forgettable = [e for e in registry.load() if not e.exists]
    if not forgettable:
        _echo("nothing to prune; every listed plan is still on disk")
        return
    for entry in forgettable:
        _echo(f"  {entry.state:<5} {entry.slug:<20} {entry.path}")
    states = [e.state for e in forgettable]
    gone, old = states.count(registry.GONE), states.count(registry.OLD)
    if not yes and not click.confirm(f"\nForget {len(forgettable)} entr(y/ies)?", default=True):
        raise click.Abort()
    registry.prune()
    _echo(f"forgot {len(forgettable)}: {gone} gone, {old} old")


@main.command(name="rm")
@click.option("--dir", "directory", default=None)
@click.option("--yes", "-y", is_flag=True)
def remove_project(directory: str | None, yes: bool) -> None:
    """Delete this plan: its folder, and its entry in the list."""
    target = Path(directory or ".").resolve()
    if registry.tree_kind(target) is None:
        if registry.holds_old_prototype(target):
            raise click.ClickException(OLD_PROTOTYPE.format(path=target))
        raise click.ClickException(f"{target} is not a plan (no {registry.PLAN_DIR}/plan.json); nothing was deleted")
    if not yes and not click.confirm(f"Delete {_plan_title(target)} and everything in {target}?", default=False):
        raise click.Abort()
    try:
        registry.delete(target)
    except registry.NotAProject as exc:
        raise click.ClickException(str(exc)) from exc
    _echo(f"deleted {target}")


def _plan_title(tree: Path) -> str:
    """A plan's title for a prompt; a plan.json that will not read is still ours, so its folder names it."""
    from protopilot.plan.model import Plan

    try:
        return Plan.load(tree).title
    except (OSError, ValueError):
        return tree.name


@main.command()
def doctor() -> None:
    """Check that proto-pilot can actually do its job here."""
    ok = True

    try:
        import anthropic  # noqa: F401

        _echo("ok   anthropic sdk: installed")
    except ImportError:
        _echo("FAIL anthropic sdk: not installed (`pip install anthropic`)")
        ok = False

    # Either backend is a complete answer, so this is not two failures -- it
    # is one question ("can this machine reach Claude at all") asked twice.
    reached = False
    for label, factory, hint in (
        ("api credit", ClaudeLLM, "set ANTHROPIC_API_KEY, or run `ant auth login` and buy credit"),
        ("subscription", ClaudeCodeLLM, "install the `claude` CLI and log in with your plan"),
    ):
        try:
            llm = factory()
            llm.check()
            _echo(f"ok   {label}: reachable (model {llm.model}, effort {llm.effort})")
            reached = True
        except Exception as exc:  # noqa: BLE001
            detail = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            _echo(f"--   {label}: {detail}")
            _echo(f"     {hint}")
    if not reached:
        _echo("FAIL no backend: neither API credit nor a subscription is usable here")
        ok = False

    _echo("")
    _echo("ready" if ok else "not ready -- `--offline` still works for a dry run")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
