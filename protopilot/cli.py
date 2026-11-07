"""The command line.

proto new "an app for tracking camping gear across trips"
proto add "let people mark items as packed"
proto plan "start a community tool library"
proto dream | dream promote d1 | dream drop d2 --why "..."
proto up | down | logs | test | spec | doctor
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click

from protopilot import __version__
from protopilot import build as builder
from protopilot import containers, registry
from protopilot.llm import ClaudeCodeLLM, ClaudeLLM, LLMError, build_llm
from protopilot.passes import PassContext, clarify
from protopilot.plan.lenses import LENS_SLUGS
from protopilot.plan.model import DEFAULT_DEPTH, TOPIC_COUNTS
from protopilot.render import render_skeleton
from protopilot.runner import SubprocessRunner, docker_available
from protopilot.spec import SPEC_DIR, SPEC_FILENAME, Spec, Theme

if TYPE_CHECKING:
    from protopilot.plan.model import Depth

PORT_RANGE = range(8080, 8180)
FOLLOW_INTERVAL = 0.02
PLAN_REVIEW_PROMPT = "Write this plan? Enter accepts, or: add TITLE | drop N | rename N TITLE | quit"


def _echo(message: str) -> None:
    click.echo(message)


def free_port(preferred: int | None = None) -> int:
    """First port nothing is listening on.

    Prototypes accumulate; the third one colliding with the first is the most
    predictable way for a generated app to look broken on arrival.
    """
    candidates = [preferred, *PORT_RANGE] if preferred else list(PORT_RANGE)
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise click.ClickException(f"no free port in {PORT_RANGE.start}-{PORT_RANGE.stop}")


def _classify(llm, idea: str, direction: str, override: str | None) -> tuple[str, "Theme | None"]:
    """Which shape this is, and how it should look.

    One cheap call before intake, and the only place `proto new` spends tokens
    on something other than generating. `--archetype` skips it entirely: an
    explicit answer should not cost a request, and it is also the escape hatch
    for a classifier that gets it wrong.

    A failure here is not fatal. The default archetype produces something usable
    for any idea, so a classifier that could not be reached costs a worse guess
    rather than the whole generation -- which is the same floor every other
    stage in this tool has.
    """
    from protopilot import archetypes

    if override:
        if override not in archetypes.names():
            raise click.ClickException(
                f"unknown archetype {override!r}; this build has: {', '.join(archetypes.names())}"
            )
        return override, None
    if llm.offline:
        return archetypes.DEFAULT, None

    _echo("classifying...")
    system, user = clarify.build(idea, direction)
    try:
        result = llm.structured(system=system, user=user, schema=clarify.schema(), label=clarify.NAME)
    except LLMError as exc:
        _echo(f"  could not classify ({exc}); falling back to {archetypes.DEFAULT}")
        return archetypes.DEFAULT, None

    if result.get("heads_up"):
        _echo(f"  heads up: {result['heads_up']}")
    theme = Theme(**result["theme"]) if result.get("theme") else None
    return clarify.chosen_archetype(result), (theme if theme and not theme.is_empty() else None)


def _parse_answers(archetype_name: str, given: tuple[str, ...]) -> dict[str, str]:
    """`--answer id=value`, checked against the archetype's own question ids.

    Refused rather than accepted-and-ignored: an id nobody reads is an answer
    the user believes they gave, and silently dropping it is the failure that
    looks exactly like success.
    """
    known = clarify.fixed_ids(archetype_name)
    out: dict[str, str] = {}
    for item in given:
        key, sep, value = item.partition("=")
        if not sep:
            raise click.ClickException(f"--answer expects ID=VALUE, got {item!r}")
        key = key.strip()
        if key not in known:
            listed = ", ".join(sorted(known)) or "none"
            raise click.ClickException(
                f"{key!r} is not a question the {archetype_name!r} archetype asks; it asks: {listed}"
            )
        out[key] = value.strip()
    return out


def _project(directory: str | None) -> Path:
    path = Path(directory or ".").resolve()
    if not (path / SPEC_DIR / SPEC_FILENAME).exists():
        raise click.ClickException(f"{path} is not a proto-pilot project (no {SPEC_DIR}/{SPEC_FILENAME})")
    return path


def _verifier(project_dir: Path, spec: Spec):
    """The verifier for this spec's target.

    Asked for rather than constructed: `Verifier` needs Docker, a port and a
    health wait, and a terminal target needs none of the three. `Verifies` is
    already a Protocol, so `drive_to_green` never learns which one it got.
    """
    from protopilot import targets

    return targets.for_spec(spec).verifier(project_dir, spec, SubprocessRunner())


def _port_is_ours(project_dir: Path, port: int) -> bool:
    """Whether starting on `port` is safe: it is free, or we already hold it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            pass
    return containers.publishes_port(SubprocessRunner(), str(project_dir.resolve()), port)


PORT_LINE = re.compile(r'^(\s*-\s*")(\d+)(:8000"\s*)$', re.M)


def set_port(project_dir: Path, spec: Spec, port: int) -> None:
    """Move a prototype to another host port, permanently.

    Both halves or neither: the port lives in `compose.yml` (what docker
    binds) and in `spec.json` (what every command prints and what `free_port`
    avoids). Updating one leaves a prototype that runs somewhere other than
    where it says it does.
    """
    compose = project_dir / "compose.yml"
    text = compose.read_text()
    updated, count = PORT_LINE.subn(rf"\g<1>{port}\g<3>", text)
    if count != 1:
        raise click.ClickException(
            f"{compose} does not have exactly one host port mapping ({count} found); " "edit it by hand"
        )
    compose.write_text(updated)
    spec.port = port
    spec.save(project_dir)


def _down_all(purge: bool) -> None:
    """Stop every prototype on this machine.

    Registered trees only, and only those still on disk. Resources whose tree
    is gone are `proto gc`'s job -- stopping them here would half-clean them
    and leave the volume, which is the state that is hardest to notice.
    """
    alive = [e for e in registry.load() if e.exists]
    if not alive:
        _echo("nothing to stop")
        return
    args = ["down", "-v"] if purge else ["down"]
    stopped = 0
    for entry in alive:
        code = _compose(Path(entry.path), *args)
        stopped += code == 0
        _echo(f"  {'stopped' if code == 0 else 'FAILED '} {entry.slug}")
    _echo(f"\n  {stopped}/{len(alive)} stopped" + ("; data dropped" if purge else "; data kept"))


def _compose(project_dir: Path, *args: str) -> int:
    """Every `docker compose` this CLI runs goes through here.

    Which makes it the one place to refuse for a tree that has no containers.
    `up`, `down`, `reset`, `logs` and `test` are all Docker verbs, and a
    terminal prototype has no image to build, nothing to detach and no log
    stream to follow -- so a compose command against one fails with an error
    about a missing `compose.yml` that reads as a broken generation.

    The condition is a fact about the TREE rather than a flag on the target,
    deliberately: `proto up` is run inside somebody's prototype, and asking the
    directory what it is beats asking a registry what it should have been.
    """
    if not (project_dir / "compose.yml").exists():
        from protopilot import targets

        spec = Spec.load(project_dir)
        hint = targets.for_spec(spec).RUN_HINT.format(directory=project_dir)
        raise click.ClickException(
            f"the {spec.target!r} target does not run in Docker; there is nothing here to "
            f"`docker compose {args[0] if args else '...'}`.\n"
            f"  Run it with `{hint}`, or read this tree's README."
        )
    return subprocess.call(["docker", "compose", *args], cwd=str(project_dir))  # noqa: S603


@click.group()
@click.version_option(__version__, prog_name="proto-pilot")
def main() -> None:
    """Turn an idea and a little direction into a plan you can work from."""


@main.command()
@click.argument("idea")
@click.option("--dir", "directory", default=None, help="Target directory (default: ./<slug>).")
@click.option("--direction", default="", help="Extra steer: look, feel, emphasis.")
@click.option(
    "--archetype",
    "archetype_name",
    default=None,
    help="What shape this is. Skips the classifier call entirely; `proto archetypes` lists them.",
)
@click.option(
    "--target",
    "target_name",
    default=None,
    help="What medium to build it in; `proto targets` lists them.",
)
@click.option(
    "--answer",
    "answers",
    multiple=True,
    metavar="ID=VALUE",
    help="Answer a fixed question without being asked. Repeatable.",
)
@click.option("--port", type=int, default=None, help="Host port (default: first free from 8080).")
@click.option(
    "--attempts", type=int, default=3, show_default=True, help="Repair attempts before handing back a RUNBOOK."
)
@click.option("--offline", is_flag=True, help="Deterministic baseline generator; no API calls.")
@click.option(
    "--backend",
    type=click.Choice(["api", "claude-code", "offline"]),
    default=None,
    help="api bills API credit; claude-code bills a Claude subscription.",
)
@click.option("--no-verify", is_flag=True, help="Generate but do not boot or test.")
@click.option("--no-git", is_flag=True, help="Do not git init the generated tree.")
@click.option("--yes", "-y", is_flag=True, help="Skip the spec review checkpoint.")
@click.option("--demo", is_flag=True, help="Hide test files from the output.")
def new(
    idea: str,
    directory: str | None,
    direction: str,
    archetype_name: str | None,
    target_name: str | None,
    answers: tuple[str, ...],
    port: int | None,
    attempts: int,
    offline: bool,
    backend: str | None,
    no_verify: bool,
    no_git: bool,
    yes: bool,
    demo: bool,
) -> None:
    """Generate a new prototype from IDEA."""
    from protopilot import targets

    llm = build_llm(offline=offline, backend=backend)

    # `targets.DEFAULT` rather than `Spec.target`'s field default: the two are
    # equal today and they answer different questions. This one is "what is a
    # NEW spec born with", and it is the one Phase 6 of
    # `docs/implementations/spec/terminal-target.md` moves.
    chosen_target = target_name or targets.DEFAULT
    if chosen_target not in targets.names():
        raise click.ClickException(str(targets.MissingTarget(chosen_target, targets.names())))

    if not no_verify:
        # The TARGET's question, not this function's. `docker_available` is the
        # right check for a tree with a `compose.yml` in it and is meaningless
        # for one process and a SQLite file -- and a CLI that asked it anyway
        # would refuse to build a terminal app on a machine with no daemon, for
        # a dependency that target does not have.
        ok, why = targets.get(chosen_target).preflight(SubprocessRunner())
        if not ok:
            # Said now rather than after the generation passes, because after
            # is when the tokens have already been spent.
            raise click.ClickException(f"{why}. Start Docker, or pass --no-verify to generate without booting.")

    chosen, theme = _classify(llm, idea, direction, archetype_name)

    _echo("intake...")
    try:
        spec = builder.spec_from_idea(
            idea,
            llm,
            archetype=chosen,
            target=chosen_target,
            port=free_port(port),
            direction=direction,
            theme=theme,
            answers=_parse_answers(chosen, answers),
        )
    except targets.UnsupportedPair as exc:
        # Named, both halves, before a token is spent. The user changes one of
        # the two and neither is guessable from a message naming only one.
        raise click.ClickException(str(exc)) from exc
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    target = Path(directory).resolve() if directory else Path.cwd() / spec.slug

    _echo("")
    _echo(spec.summary())
    _echo(f"\n  -> {target}")
    _echo("")
    if not yes and not click.confirm("Generate this?", default=True):
        raise click.Abort()

    if target.exists() and any(target.iterdir()):
        raise click.ClickException(f"{target} exists and is not empty")

    _echo("rendering skeleton...")
    written = render_skeleton(spec, target)
    _echo(f"  {len(written)} skeleton files")
    spec.save(target)

    ctx = PassContext(project_dir=target, change=direction)
    try:
        builder.generate(spec, ctx, llm, log=_echo, hide_tests=demo)
    except (LLMError, builder.PassFailed) as exc:
        raise click.ClickException(f"{exc}\n  part-built tree and a RUNBOOK are at {target}") from exc

    registry.record(slug=spec.slug, name=spec.name, path=target, port=spec.port, idea=idea)

    if not no_git:
        _git_init(target)

    if no_verify:
        hint = targets.get(chosen_target).RUN_HINT.format(directory=target)
        _echo(f"\nGenerated (not verified). `{hint}`")
        return

    _finish(spec, ctx, llm, target, attempts)


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
    """The checkpoint: edit until a person accepts, as `proto new`'s `[Y/n]` accepts a spec."""
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
        sys.exit(1)  # the tree is handed back, as `proto new`'s floor hands one back


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


@main.command()
@click.argument("change")
@click.option("--dir", "directory", default=None, help="Project directory (default: cwd).")
@click.option("--attempts", type=int, default=3, show_default=True)
@click.option("--offline", is_flag=True)
@click.option(
    "--backend",
    type=click.Choice(["api", "claude-code", "offline"]),
    default=None,
    help="api bills API credit; claude-code bills a Claude subscription.",
)
@click.option("--no-verify", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def add(
    change: str,
    directory: str | None,
    attempts: int,
    offline: bool,
    backend: str | None,
    no_verify: bool,
    yes: bool,
) -> None:
    """Apply CHANGE to an existing prototype and re-verify it."""
    target = _project(directory)
    spec = Spec.load(target)
    llm = build_llm(offline=offline, backend=backend)
    if llm.offline:
        raise click.ClickException("`add` needs the model: the baseline generator cannot read a change request.")

    # A change request can add or retype a column, and there are no
    # migrations -- so the old volume is dropped rather than silently kept and
    # left disagreeing with the models it is about to be read through.
    _compose(target, "down", "-v")

    _echo("amending spec...")
    try:
        updated = builder.amend_spec(spec, change, llm)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    _echo("")
    _echo(updated.summary())
    _echo("")
    if not yes and not click.confirm("Apply this?", default=True):
        raise click.Abort()

    updated.save(target)
    ctx = PassContext(project_dir=target, change=change)
    try:
        builder.generate(updated, ctx, llm, log=_echo)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    if no_verify:
        _echo("\nRegenerated (not verified).")
        return
    _finish(updated, ctx, llm, target, attempts)


def _finish(spec: Spec, ctx: PassContext, llm, target: Path, attempts: int) -> None:
    from protopilot import targets

    outcome = builder.drive_to_green(spec, ctx, llm, _verifier(target, spec), attempts=attempts, log=_echo)
    if outcome.ok:
        runbook = target / "RUNBOOK.md"
        if runbook.exists():
            runbook.unlink()  # a stale runbook reads as a live problem
        # The target's sentence, not this function's. It used to be a hardcoded
        # `http://localhost:{port}`, which is the last thing a person reads and
        # is a link to nothing for a prototype that does not listen.
        handoff = targets.for_spec(spec).HANDOFF.format(
            name=spec.name, slug=spec.slug, port=spec.port, directory=target
        )
        _echo(f"\n  {handoff}")
        _echo(f"  {target}")
        return

    path = builder.write_runbook(target, spec, outcome)
    _echo(
        f"\n  Could not get to green in {attempts} attempt(s). The tree is at\n"
        f"  {target}, and what is broken is written down in {path.name}."
    )
    sys.exit(1)


def _git_init(target: Path) -> None:
    """First commit is the pristine generation, so `git diff` shows the user
    their own edits rather than the whole app."""
    try:
        for argv in (
            ["git", "init", "-q"],
            ["git", "add", "-A"],
            ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "generated by proto-pilot"],
        ):
            subprocess.run(argv, cwd=str(target), check=True, capture_output=True)  # noqa: S603
    except (subprocess.CalledProcessError, FileNotFoundError):
        _echo("  (git init skipped)")


@main.command(name="spec")
@click.option("--dir", "directory", default=None)
@click.option("--json", "as_json", is_flag=True, help="Print the raw spec.")
def show_spec(directory: str | None, as_json: bool) -> None:
    """Show this project's spec."""
    target = _project(directory)
    spec = Spec.load(target)
    click.echo((target / SPEC_DIR / SPEC_FILENAME).read_text() if as_json else spec.summary())


@main.command()
@click.option("--dir", "directory", default=None)
@click.option("--port", type=int, default=None, help="Move this prototype to another host port, permanently.")
def up(directory: str | None, port: int | None) -> None:
    """Start the app."""
    target = _project(directory)
    spec = Spec.load(target)

    if port is not None and port != spec.port:
        set_port(target, spec, port)
        spec = Spec.load(target)
        _echo(f"port set to {spec.port}")
    elif not _port_is_ours(target, spec.port):
        # `free_port` runs at generation, and the answer is then frozen into
        # compose.yml -- so two prototypes generated months apart can hold the
        # same port, and the second `up` fails with a docker bind error that
        # names neither prototype. Said here instead, with the fix.
        suggestion = free_port()
        raise click.ClickException(
            f"port {spec.port} is already in use by something else.\n"
            f"  `proto up --port {suggestion}` moves this prototype and remembers it."
        )

    code = _compose(target, "up", "-d", "--build")
    if code == 0:
        _echo(f"http://localhost:{spec.port}")
    sys.exit(code)


@main.command()
@click.option("--dir", "directory", default=None)
@click.option("--purge", is_flag=True, help="Also delete saved data (the database volume).")
@click.option("--all", "every", is_flag=True, help="Every prototype on this machine, not just this one.")
def down(directory: str | None, purge: bool, every: bool) -> None:
    """Stop the app. Saved data survives unless --purge."""
    if every:
        _down_all(purge)
        return
    target = _project(directory)
    args = ["down", "-v"] if purge else ["down"]
    code = _compose(target, *args)
    if code == 0:
        _echo("stopped; data kept (`proto down --purge` to drop it)" if not purge else "stopped; data dropped")
    sys.exit(code)


@main.command()
@click.option("--dir", "directory", default=None)
@click.option("--yes", "-y", is_flag=True)
def reset(directory: str | None, yes: bool) -> None:
    """Drop saved data and start clean.

    There are no migrations here, so a schema change against an old volume is
    a stale database rather than an error. This is the escape hatch.
    """
    target = _project(directory)
    if not yes and not click.confirm(f"Delete all saved data in {target.name}?", default=False):
        raise click.Abort()
    _compose(target, "down", "-v")
    code = _compose(target, "up", "-d", "--build")
    if code == 0:
        _echo(f"clean; http://localhost:{Spec.load(target).port}")
    sys.exit(code)


def _preflight_backend(backend: str | None) -> None:
    """Fail now rather than partway into a generation.

    Resolved through `build_llm` rather than by re-reading the rule here: the
    choice is `--backend`, then `PROTOPILOT_LLM`, then the API, and a second
    copy of that would answer differently the day the rule changes. It also
    fixes what the hand-rolled version missed — `serve` only checked when
    `--backend claude-code` was passed explicitly, so an operator who set
    `PROTOPILOT_LLM=claude-code` in their shell (the ordinary way to do it) got
    no check at all.

    **Only the free check runs.** `ClaudeCodeLLM.check()` is a `--version`
    call on a subprocess and costs nothing. `ClaudeLLM.check()` deliberately
    spends one token, because a zero balance is invisible until a real request
    is made -- worth it in `proto doctor`, which is asked to find out, and not
    worth it on every launch of a front end.
    """
    from protopilot.llm import ClaudeCodeLLM

    llm = build_llm(backend=backend)
    if not isinstance(llm, ClaudeCodeLLM):
        return
    try:
        llm.check()
    except LLMError as exc:
        raise click.ClickException(f"{exc}\n     set PROTOPILOT_CLAUDE_BIN to a working `claude` binary") from exc


@main.command()
@click.option("--workspace", default=None, help="Where prototypes are generated (default: ./prototypes).")
@click.option("--backend", type=click.Choice(["api", "claude-code", "offline"]), default=None)
@click.option(
    "--demo/--no-demo",
    default=True,
    show_default=True,
    help="Hide test files in the UI (they are still generated and run).",
)
def console(workspace: str | None, backend: str | None, demo: bool) -> None:
    """Run the terminal front end: type an idea, watch it generate.

    The counterpart to `proto serve` for the default target. `serve` hands back
    a link you click, which a terminal app has no use for; this one hands back a
    tree and the command that runs it.

    `proto new` is untouched and stays the scriptable path -- a front end that
    is the only way in is a tool you cannot automate.
    """
    # Before the app takes over the terminal: a `ClickException` raised from
    # inside a running Textual app is painted over by the next frame and then
    # lost when the screen is torn down.
    _preflight_backend(backend)

    from protopilot.console import run as run_console

    root = Path(workspace).resolve() if workspace else Path.cwd() / "prototypes"
    run_console(root, backend=backend, demo=demo)


@main.command()
@click.option("--port", type=int, default=7000, show_default=True)
@click.option("--workspace", default=None, help="Where prototypes are generated (default: ./prototypes).")
@click.option("--backend", type=click.Choice(["api", "claude-code", "offline"]), default=None)
@click.option(
    "--demo/--no-demo",
    default=True,
    show_default=True,
    help="Hide test files in the UI (they are still generated and run).",
)
def serve(port: int, workspace: str | None, backend: str | None, demo: bool) -> None:
    """Run the web front end."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise click.ClickException('the front end needs extras: pip install -e ".[web]"') from exc

    _preflight_backend(backend)

    from protopilot.web.app import create_app

    root = Path(workspace).resolve() if workspace else Path.cwd() / "prototypes"
    _echo(f"workspace: {root}")
    _echo(f"http://localhost:{port}" + ("  (demo mode: tests hidden)" if demo else ""))
    uvicorn.run(create_app(root, backend=backend, demo=demo), host="127.0.0.1", port=port, log_level="warning")


@main.command(name="archetypes")
def list_archetypes() -> None:
    """What shapes this build can generate, and what each one asks you."""
    from protopilot import archetypes

    for name in archetypes.names():
        module = archetypes.get(name)
        default = "  (default)" if name == archetypes.DEFAULT else ""
        _echo(f"{name}{default}")
        _echo(f"  {module.LABEL}")
        _echo(f"  fits: {module.MATCHES}")
        for question in module.QUESTIONS:
            _echo(f"    --answer {question['id']}=...  {question['question']}")
        _echo("")


@main.command(name="targets")
def list_targets() -> None:
    """What media this build can generate into, and what each one can build."""
    from protopilot import targets

    for name in targets.names():
        module = targets.get(name)
        default = "  (default)" if name == targets.DEFAULT else ""
        _echo(f"{name}{default}")
        _echo(f"  {module.LABEL}")
        _echo(f"  builds: {', '.join(module.ARCHETYPES)}")
        _echo("")


@main.command(name="ls")
def list_projects() -> None:
    """List every prototype generated on this machine.

    Read-only. This used to call `prune()`, which deletes every entry whose
    directory has gone -- so looking at the list was enough to empty it, and
    that is exactly how the whole registry was lost when a scratch directory
    was wiped. A missing tree is now *reported* as missing; `proto prune`
    is the command that acts on it.
    """
    entries = registry.load()
    if not entries:
        _echo('no prototypes yet -- `proto new "an idea"`')
        return

    running = containers.running_paths(SubprocessRunner())
    width = max(len(e.slug) for e in entries)
    missing = 0
    for entry in entries:
        if not entry.exists:
            state, missing = "gone", missing + 1
        elif entry.path in running:
            state = "up"
        else:
            state = "down"
        _echo(f"  {state:<5} {entry.slug:<{width}}  :{entry.port}  {entry.path}")

    _echo(f"\n  {len(entries)} prototype(s)")
    if missing:
        _echo(f"  {missing} whose directory is gone -- `proto prune` to forget them,")
        _echo("  `proto gc` to collect the Docker resources they left behind")


@main.command()
@click.option("--yes", "-y", is_flag=True)
def prune(yes: bool) -> None:
    """Forget registry entries whose directory no longer exists.

    Only the index is touched. Containers and volumes those trees left behind
    are `proto gc`'s job, and running this first makes them harder to find --
    so `gc` is the one to reach for when both are true.
    """
    gone = [e for e in registry.load() if not e.exists]
    if not gone:
        _echo("nothing to prune; every registered tree is still on disk")
        return
    for entry in gone:
        _echo(f"  {entry.slug:<20} {entry.path}")
    if not yes and not click.confirm(f"\nForget {len(gone)} entr(y/ies)?", default=True):
        raise click.Abort()
    registry.prune()
    _echo(f"forgot {len(gone)}")


# What `gc` and the Docker resource labels mean for a target with no containers
# is an OPEN QUESTION, not a task, and it is written down as one in `NOTES.md`.
# Nothing here is dead: the web target orphans a container, a volume, a network
# and an image, and this is the only thing that finds them once the tree is
# gone. It is also not to be extended to the terminal target, whose whole tree
# is one process and one SQLite file -- a label vocabulary applied to a target
# with nothing to label reads as coverage and is not.
@main.command()
@click.option("--yes", "-y", is_flag=True)
@click.option("--dry-run", is_flag=True, help="List what would be removed and stop.")
def gc(yes: bool, dry_run: bool) -> None:
    """Collect Docker resources whose prototype tree is gone.

    `proto rm` cleans up after itself. Nothing else does: a tree removed with
    `rm -rf`, a wiped scratch directory, a `git clean` -- each leaves a
    container, a named volume, a network and an image with nothing on disk
    pointing at them, and they accumulate silently.

    This finds them by asking Docker, not the registry. Every generated
    `compose.yml` stamps the tree's absolute path onto each resource, so an
    orphan is still findable after the registry has been pruned, wiped, or
    never written.
    """
    runner = SubprocessRunner()
    ok, why = docker_available(runner)
    if not ok:
        raise click.ClickException(f"{why}; nothing to collect without a daemon")

    orphans = containers.find_orphans(runner)
    if not orphans:
        _echo("nothing to collect; every labelled resource has a tree behind it")
        return

    for orphan in orphans:
        _echo(f"  {orphan.describe()}")
    total = sum(o.total for o in orphans)
    if dry_run:
        _echo(f"\n  {total} resource(s) from {len(orphans)} tree(s); nothing removed")
        return
    if not yes and not click.confirm(
        f"\nRemove {total} resource(s) from {len(orphans)} deleted tree(s)?", default=False
    ):
        raise click.Abort()

    collected = 0
    for orphan in orphans:
        removed = containers.remove(runner, orphan.path)
        collected += sum(removed.values())
        still = orphan.total - sum(removed.values())
        note = f"  ({still} would not go -- still in use?)" if still else ""
        _echo(f"  collected {sum(removed.values())} from {orphan.path}{note}")
        # The registry entry goes too, but only once its resources have. The
        # other order loses the path that finds them.
        registry.forget(Path(orphan.path))
    _echo(f"\n  {collected} resource(s) collected")


@main.command(name="rm")
@click.option("--dir", "directory", default=None)
@click.option("--yes", "-y", is_flag=True)
def remove_project(directory: str | None, yes: bool) -> None:
    """Delete this prototype: containers, data and the tree."""
    target = _project(directory)
    spec = Spec.load(target)
    if not yes and not click.confirm(f"Delete {spec.name} and everything in {target}?", default=False):
        raise click.Abort()
    try:
        registry.delete(target)
    except registry.NotAProject as exc:
        raise click.ClickException(str(exc)) from exc
    _echo(f"deleted {target}")


@main.command(name="export")
@click.option("--dir", "directory", default=None)
@click.option("--to", "destination", default=None, help="Output path (default: ./<slug>.zip).")
@click.option("--with-tests/--without-tests", default=True, help="Include the test suite.")
def export_project(directory: str | None, destination: str | None, with_tests: bool) -> None:
    """Package this prototype as a zip you can hand to someone."""
    import zipfile

    target = _project(directory)
    spec = Spec.load(target)
    out = Path(destination) if destination else Path.cwd() / f"{spec.slug}.zip"
    skipped = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(target)
            parts = set(rel.parts)
            if parts & {"__pycache__", ".pytest_cache", ".git"}:
                continue
            if not with_tests and rel.parts and rel.parts[0] == "tests":
                skipped += 1
                continue
            zf.write(path, Path(spec.slug) / rel)
    note = f" ({skipped} test file(s) omitted)" if skipped else ""
    _echo(f"{out}{note}")


@main.command()
@click.option("--dir", "directory", default=None)
def logs(directory: str | None) -> None:
    """Follow the app logs."""
    sys.exit(_compose(_project(directory), "logs", "-f", "app"))


@main.command()
@click.option("--dir", "directory", default=None)
def test(directory: str | None) -> None:
    """Run the smoke tests inside the container."""
    sys.exit(_compose(_project(directory), "exec", "-T", "app", "pytest", "-q"))


@main.command()
def doctor() -> None:
    """Check that proto-pilot can actually do its job here."""
    from protopilot import targets

    ok = True

    # Per target, because "is this machine ready" stopped being one question
    # the day a second medium existed. A missing Docker daemon is fatal for the
    # web target and irrelevant to the terminal one, and reporting it as a flat
    # FAIL told somebody whose default target needs nothing that they could not
    # generate. Only the DEFAULT target's answer decides the exit code; the
    # rest are reported with what to type instead.
    runner = SubprocessRunner()
    for name in targets.names():
        ready, why = targets.get(name).preflight(runner)
        marker = "  (default)" if name == targets.DEFAULT else ""
        if ready:
            _echo(f"ok   target {name}{marker}: {why}")
        elif name == targets.DEFAULT:
            _echo(f"FAIL target {name}{marker}: {why}")
            ok = False
        else:
            _echo(f"--   target {name}: {why}")
            _echo(f"     `proto new` still works; it builds {targets.DEFAULT} unless you say otherwise")

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

    from protopilot import browser as browser_check

    why = browser_check.available()
    if why:
        _echo(f"--   browser: {why}")
        _echo("     screens will not be checked in a browser; canvas and script go unverified")
    else:
        _echo(f"ok   browser: {browser_check._executable() or 'playwright bundled chromium'}")

    port = None
    try:
        port = free_port()
        _echo(f"ok   ports: {port} is free")
    except click.ClickException as exc:
        _echo(f"FAIL ports: {exc}")
        ok = False

    _echo("")
    _echo("ready" if ok else "not ready -- `--offline --no-verify` still works for a dry run")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
