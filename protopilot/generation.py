"""One generation, start to finish, with no front end attached.

This is the sequence `proto new` runs, in the same order and through the same
functions, arranged so that something other than a terminal can drive it. It
lived in `protopilot/web/app.py` until the console needed it, which is the
moment it stopped being the web front end's private helper.

**Moving it was not tidying.** `protopilot/web/app.py` imports FastAPI at module
scope, so a second front end importing `run_generation` from there would have
required the `dev` extra to run — quietly, since the suite installs that extra
and would have stayed green while a plain `pip install -e .` install of the
console could not generate anything. `protopilot/jobs.py` was already careful
about this and was measured to be standalone; a runner reachable only through
FastAPI would have thrown that away one import along.

So: standard library, plus proto.pilot's own modules, and nothing else.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from protopilot import archetypes
from protopilot import build as builder
from protopilot import registry, targets
from protopilot.llm import build_llm
from protopilot.passes import PassContext
from protopilot.render import render_skeleton
from protopilot.runner import SubprocessRunner
from protopilot.spec import Theme


def assemble(job, backend: str | None = None, target: str | None = None):
    """Intake, and nothing else. Returns the spec; **writes no files.**

    The first half of a generation, split out so a front end can put a review
    checkpoint between the two. `proto new` has always had one — a `[Y/n]` after
    the spec summary — and the console needs the same decision at the same
    point, which is only possible if the point exists in the runner.

    Nothing here touches the disk, so declining after this costs nothing
    further. Not *nothing*: intake is one model call and it has already been
    made by the time there is a spec to show. What the checkpoint saves is the
    five generation passes and the verify loop, which is the expensive part and
    the whole reason the checkpoint is before them rather than after.
    """
    from protopilot.cli import free_port

    llm = build_llm(backend=backend)
    chosen = job.archetype or archetypes.DEFAULT

    job.log("intake...")
    spec = builder.spec_from_idea(
        job.idea,
        llm,
        archetype=chosen,
        target=target or targets.DEFAULT,
        port=free_port(),
        direction=job.direction,
        theme=Theme(**job.theme) if job.theme else None,
        answers=dict(job.answers),
    )
    job.log(spec.summary())
    job.event("spec", name=spec.name, slug=spec.slug, target=spec.target, archetype=chosen)
    return spec


def build(
    job,
    workspace: Path,
    spec,
    backend: str | None = None,
    demo: bool = True,
    attempts: int = 3,
    verifier_factory=None,
) -> None:
    """Everything after the spec is settled: skeleton, passes, verify, record.

    Takes the spec rather than an idea, so this half is identical whether a
    human approved it at a checkpoint or nobody was asked.
    """
    llm = build_llm(backend=backend)
    log = job.log

    tree = Path(workspace) / spec.slug
    if tree.exists():
        shutil.rmtree(tree)

    render_skeleton(spec, tree)
    spec.save(tree)
    job.project_dir = str(tree)
    job.port = spec.port

    ctx = PassContext(project_dir=tree, change=job.direction)
    builder.generate(spec, ctx, llm, log=log, hide_tests=demo, emit=job.event)

    log("verify...")
    make_verifier = verifier_factory or (lambda: targets.for_spec(spec).verifier(tree, spec, SubprocessRunner()))
    # Held rather than passed inline, so what it learned can be asked for
    # afterwards. The terminal verifier boots the generated app under
    # `App.run_test` and keeps the composited screen it painted -- which is a
    # picture of the thing that was just built, already paid for, and otherwise
    # thrown away the moment the verdict is returned.
    verifier = make_verifier()
    outcome = builder.drive_to_green(spec, ctx, llm, verifier, attempts=attempts, log=log, emit=job.event)

    # `getattr`, because this is the terminal verifier's and no other's. A
    # target whose verifier has no screen to show simply emits nothing, rather
    # than every target growing a field so that one of them can be asked.
    screen = (getattr(verifier, "last_probe", None) or {}).get("buffer", "")
    if screen:
        job.event("preview", screen=screen, target=spec.target)

    registry.record(slug=spec.slug, name=spec.name, path=tree, port=spec.port, idea=job.idea)
    # A URL for a target that has one. `job.url` used to be set unconditionally,
    # which is harmless while the only caller pins `web` and wrong the moment
    # one does not: a link to a port nothing is listening on is worse than no
    # link, because it looks like the thing worked.
    job.url = f"http://localhost:{spec.port}" if targets.for_spec(spec).USES_PORT else ""
    if not outcome.ok:
        # Handed back anyway, with the stage named -- the same floor the CLI has.
        stage = outcome.result.stage if outcome.result else "unknown"
        log(f"red at {stage}; the tree is at {tree}")
    job.event(
        "finished",
        ok=outcome.ok,
        attempts=outcome.attempts,
        project_dir=str(tree),
        run_hint=targets.for_spec(spec).RUN_HINT,
    )


def run_generation(
    job,
    workspace: Path,
    target: str | None = None,
    backend: str | None = None,
    demo: bool = True,
    attempts: int = 3,
    verifier_factory=None,
) -> None:
    """Both halves, with nobody asked in between.

    What a front end calls when it has no review checkpoint of its own. The web
    front end does exactly this; the console calls `assemble` and `build`
    separately so it can put a screen between them.

    `target` is a parameter and not a constant, which is the one real
    difference from the version this replaced. The web front end pins `web`
    because what it hands back is a link you click and a terminal app has no
    link; the console has no such constraint and passes the user's choice. A
    caller that says nothing gets `targets.DEFAULT`, the same answer
    `proto new` gives.

    Both channels are wired throughout: `log` for the sentence a person reads,
    `emit` for the fields a view folds into a progress region.
    """
    spec = assemble(job, backend=backend, target=target)
    build(
        job,
        workspace,
        spec,
        backend=backend,
        demo=demo,
        attempts=attempts,
        verifier_factory=verifier_factory,
    )
