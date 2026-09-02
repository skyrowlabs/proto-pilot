"""Orchestration: run the passes, then drive the tree to green.

The pass order is the design, not an accident:

    schema -> smoke -> seed -> routes -> ui

Tests come second, before any of the code they test, so they describe what was
asked for rather than what got built; the routes pass is then handed them as
its target. UI comes last because it is the pass most dependent on real
source -- a template referencing a context key no route passes is the single
most common way a generated app 500s.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from protopilot.llm import LLM
from protopilot.passes import PassContext, PassResult, intake
from protopilot.passes import models as schema_pass
from protopilot.passes import repair, routes, run_pass, seed, smoke, ui
from protopilot.spec import MODEL_OWNED_EXCLUSIONS, Screen, Spec
from protopilot.verify import Verifies, VerifyResult

CODE_PASSES = (schema_pass, smoke, seed, routes, ui)
SMOKE_PATH = "tests/test_smoke.py"

Log = Callable[[str], None]

#: Identity. The slug is the database name and the port is the tab the user has
#: open, so neither is the model's to revise on an amend.
IDENTITY = ("slug", "port")

#: What survives an amend unchanged, and why it is DERIVED rather than listed.
#:
#: `MODEL_OWNED_EXCLUSIONS` is exactly the set of fields the amend schema does
#: not contain, because they have an owner that is not intake. A field the
#: model was never shown cannot come back in its response -- so on an amend it
#: has to come from the spec that already exists, or it silently reverts to a
#: default.
#:
#: It silently did. Before this was here, `proto add` on a `turn-based-game`
#: project reset it to `crud` and dropped the theme, the answers and the board
#: dimensions, then regenerated a tracking app over a game's entities. Nothing
#: failed; the tree just quietly became a different app.
#:
#: Derived, so the next field added to the exclusions is carried without
#: anybody remembering this list exists. That is the whole reason to compute it
#: rather than write it down.
CARRIED_THROUGH_AMEND = IDENTITY + MODEL_OWNED_EXCLUSIONS


class PassFailed(RuntimeError):
    """A pass did not return. Carries which one, so the CLI can name it."""

    def __init__(self, pass_name: str, reason: str) -> None:
        super().__init__(f"pass {pass_name!r} failed: {reason}")
        self.pass_name = pass_name
        self.reason = reason


@dataclass
class Outcome:
    ok: bool
    attempts: int
    result: VerifyResult | None
    history: list[VerifyResult] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)


def _run_intake(idea: str, llm: LLM, ctx: PassContext, *, label: str = "") -> dict:
    """The intake call, offline or not. One place, so the two front ends cannot
    drift on which branch they take."""
    if llm.offline:
        return intake.offline(idea, ctx)
    system, user = intake.build(idea, ctx)
    return llm.structured(system=system, user=user, schema=intake.SCHEMA, label=label or intake.NAME)


def spec_from_idea(
    idea: str,
    llm: LLM,
    *,
    archetype: str,
    port: int,
    direction: str = "",
    theme=None,
    answers: dict[str, str] | None = None,
) -> Spec:
    """An idea and a classification -> a spec that is fully decided.

    **The only implementation.** `proto new` and `proto serve` are two callers
    of this, which is a rule the web module's docstring already claimed and
    this function is what makes true: the same seven fields were being assigned
    in two places, agreeing only because one person wrote both. Adding
    `PassContext.archetype` needed an edit in each, and nothing would have
    failed had only one been made.

    Everything set here is set AFTER validation and never by the model. Intake
    is not shown these fields (`MODEL_OWNED_EXCLUSIONS`) precisely so it cannot
    return a confident second opinion that overwrites the human's.
    """
    from protopilot import __version__, archetypes

    ctx = PassContext(project_dir=Path("."), change=direction, archetype=archetype)
    spec = Spec.model_validate(_run_intake(idea, llm, ctx))

    spec.port = port
    spec.direction = direction or spec.direction
    spec.protopilot_version = __version__
    spec.archetype = archetype
    spec.theme = theme if (theme is not None and not theme.is_empty()) else None
    spec.answers = dict(answers or {})
    # Screens are the contract the smoke tests and the routes are both
    # generated from, and the rule belongs to the archetype -- so they are
    # resolved AFTER `spec.archetype` is set, never before. Model-proposed
    # `custom` pages survive on top; its guesses at the rest do not.
    spec.screens = [Screen(**s) for s in archetypes.screens_for(spec, spec.screens)]
    return spec


def amend_spec(previous: Spec, change: str, llm: LLM) -> Spec:
    """An existing spec and a change request -> the updated spec.

    The other half of the same rule, and the half that was actually broken.
    An amend response cannot contain the model-owned fields, so every one of
    them has to be carried across from the spec that already exists --
    `CARRIED_THROUGH_AMEND` is that set, derived rather than listed.

    Screens are re-resolved rather than taken from the response for the same
    reason as in `spec_from_idea`: the rule is the archetype's, and the
    archetype has just been carried forward rather than re-decided.
    """
    from protopilot import __version__, archetypes

    system, user = intake.build_amend(previous, change)
    updated = Spec.model_validate(llm.structured(system=system, user=user, schema=intake.SCHEMA, label="amend"))

    for name in CARRIED_THROUGH_AMEND:
        setattr(updated, name, getattr(previous, name))
    updated.protopilot_version = __version__
    updated.screens = [Screen(**s) for s in archetypes.screens_for(updated, updated.screens)]
    return updated


def generate(
    spec: Spec,
    ctx: PassContext,
    llm: LLM,
    log: Log = print,
    hide_tests: bool = False,
) -> list[PassResult]:
    """Run the five passes in order.

    `hide_tests` is presentation only. The smoke pass still runs, still runs
    second, and the routes pass is still handed its output as the target --
    hiding the suite from a demo audience must not change what gets built, or
    the thing being demoed is not the thing that ships.
    """
    results = []
    for module in CODE_PASSES:
        log(f"  pass {module.NAME}...")
        try:
            result = run_pass(module, spec, ctx, llm)
        except Exception as exc:
            # Name the pass and leave a runbook before re-raising, so the
            # caller reports a stage rather than a stack trace.
            write_generation_runbook(ctx.project_dir, module.NAME, str(exc), [r.name for r in results])
            raise PassFailed(module.NAME, str(exc)) from exc
        shown = [f for f in result.files if not (hide_tests and is_test_path(f))]
        if shown:
            log(f"    {len(shown)} file(s): {', '.join(str(f) for f in shown)}")
        results.append(result)
    return results


def is_test_path(path) -> bool:
    """A generated test file, by either of the two ways it can look."""
    p = Path(str(path))
    return "tests" in p.parts or p.name.startswith("test_")


def _test_count(project_dir: Path) -> int:
    path = project_dir / SMOKE_PATH
    return len(re.findall(r"^def test_", path.read_text(), re.M)) if path.exists() else 0


def drive_to_green(
    spec: Spec,
    ctx: PassContext,
    llm: LLM,
    verifier: Verifies,
    attempts: int = 3,
    log: Log = print,
) -> Outcome:
    """Verify, and on failure repair and verify again, up to `attempts` times.

    The loop is bounded and has a floor. Three attempts is not a tuned number;
    it is the point past which the failures observed stop being typos and
    start being the model disagreeing with itself, which more attempts do not
    fix. Past it the tree is handed back with a RUNBOOK rather than silently
    failing -- a prototype whose broken shape you know beats a mystery.
    """
    history: list[VerifyResult] = []
    repairs: list[str] = []

    for attempt in range(1, attempts + 2):
        log(f"  verify (attempt {attempt})...")
        result = verifier.verify()
        history.append(result)
        if result.ok:
            log(f"    {result.summary}")
            return Outcome(True, attempt, result, history, repairs)

        log(f"    failed at {result.stage}: {result.summary}")
        if attempt > attempts:
            break

        before = _test_count(ctx.project_dir)
        original = (ctx.project_dir / SMOKE_PATH).read_text() if before else ""

        ctx.failure = result.report()
        log("  pass repair...")
        try:
            patch = run_pass(repair, spec, ctx, llm)
        except Exception as exc:  # noqa: BLE001 -- a failed repair is an outcome
            log(f"    repair pass failed: {exc}")
            break
        if not patch.files:
            log(f"    repair produced no changes: {patch.notes}")
            break
        log(f"    patched {', '.join(str(f) for f in patch.files)}")
        repairs.append(f"attempt {attempt} ({result.stage}): {patch.notes}")

        # A repair is not allowed to make the suite pass by shrinking it.
        # This is the one guardrail the prompt alone cannot enforce, and the
        # failure mode it prevents -- green because there is nothing left to
        # fail -- is the only one that would go unnoticed.
        after = _test_count(ctx.project_dir)
        if before and after < before:
            (ctx.project_dir / SMOKE_PATH).write_text(original)
            log(f"    rejected: repair cut the smoke suite from {before} to " f"{after} tests; reverted {SMOKE_PATH}")
            repairs[-1] += "  [test deletion rejected and reverted]"

    return Outcome(False, len(history), history[-1] if history else None, history, repairs)


RUNBOOK = """\
# Runbook

proto-pilot could not get this prototype to green in {attempts} attempt(s), so it
handed the tree over as it stands rather than failing silently. Everything
below is what it knows.

## Where it stops

Stage: **{stage}**

{summary}

## Last output

```
{output}
```

## Container logs

```
{logs}
```

## What was tried

{repairs}

## Carrying on by hand

```bash
docker compose up -d --build        # bring it up
docker compose logs -f app          # watch it
docker compose exec -T app pytest -q   # the failing suite
```

Generated files -- rewritten whole by the next `proto add`, so fix them here
only if you are done generating:

{generated}

The rest of the tree is the fixed proto-pilot skeleton and is very unlikely to be
the problem.
"""


GENERATION_RUNBOOK = """\
# Runbook

proto-pilot did not finish generating this prototype. The tree is handed over
part-built rather than deleted, because a half-generated tree whose shape you
know beats a directory that vanished.

## Where it stops

Pass: **{pass_name}**

{reason}

## What exists

Passes that completed before it:

{done}

Everything else in the tree is the fixed proto-pilot skeleton.

## Carrying on

The passes are ordered and each one reads the previous pass's real source, so
a tree that stops here cannot be booted as it stands. Re-run generation:

```bash
proto new "<the same idea>" --dir <a fresh directory>
```

If the cause was transient -- a timeout, a rate limit, an empty credit
balance -- the same command will usually just work. If the pass keeps failing
at the same place, `--offline` generates a plain CRUD version of the same spec
so at least the shape is there.
"""


def write_generation_runbook(project_dir: Path, pass_name: str, reason: str, done: list[str]) -> Path:
    """The floor for a pass that never returned.

    `drive_to_green` has had a floor since the beginning; generation did not,
    so a pass that timed out or ran out of credit left a part-built tree and a
    stack trace. Same promise, applied one stage earlier.
    """
    listed = "\n".join(f"- {name}" for name in done) or "- none"
    path = project_dir / "RUNBOOK.md"
    path.write_text(
        GENERATION_RUNBOOK.format(pass_name=pass_name, reason=reason.strip() or "(no reason given)", done=listed)
    )
    return path


def write_runbook(project_dir: Path, spec: Spec, outcome: Outcome) -> Path:
    result = outcome.result
    generated = "\n".join(
        f"- `{p}`"
        for p in ["app/models.py", "app/seed.py", "app/routes.py", SMOKE_PATH]
        + sorted(
            f"app/templates/{q.name}"
            for q in (project_dir / "app" / "templates").glob("*.html")
            if q.name != "base.html"
        )
    )
    repairs = (
        "\n".join(f"{i}. {r}" for i, r in enumerate(outcome.repairs, 1))
        or "Nothing -- the first verify failed and no repair was attempted."
    )
    path = project_dir / "RUNBOOK.md"
    path.write_text(
        RUNBOOK.format(
            attempts=outcome.attempts,
            stage=result.stage if result else "unknown",
            summary=result.summary if result else "no verify result was produced",
            output=(result.output if result else "").strip()[-4000:] or "(none)",
            logs=(result.logs if result else "").strip()[-4000:] or "(none)",
            repairs=repairs,
            generated=generated,
        )
    )
    return path
