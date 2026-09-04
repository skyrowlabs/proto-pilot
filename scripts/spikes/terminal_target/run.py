#!/usr/bin/env python3
"""One spec, one target, one measured generation run.

This is Phase 1 of `docs/TODO/terminal-target.md`: a go/no-go on whether the
model writes a Textual + SQLite terminal app as reliably as it writes today's
FastAPI web app. It builds none of the `target` axis the rest of that plan
describes, on purpose -- a gate that had to build the thing it is gating cannot
say no.

    python scripts/spikes/terminal_target/run.py --list
    python scripts/spikes/terminal_target/run.py --target tui --spec field_notes
    python scripts/spikes/terminal_target/run.py --target web --spec field_notes

What it records, per run, in `record.json`:

- **repair attempts to green**, from the same three-attempt loop with the same
  floor as the product's
- **wall clock**, per pass and in total, and the model's own `duration_api_ms`
- **tokens**, when the backend surfaces them, and an explicit
  `usage_available: false` when it does not
- **what the failures were**, not how many. Every failing stage's error text is
  kept, because the question the headline number hides is whether failures
  cluster -- a recurring mistake, which is a prompt or a skeleton fix -- or
  scatter, which is a competence ceiling and is not cheap

The record is rewritten after every pass and every verify attempt. These runs
are tens of minutes long; a harness that only writes at the end loses the whole
thing to one timeout.

## The one asymmetry, stated rather than hidden

The **web** half runs the real pipeline: `build.generate`, `build.drive_to_green`
and `verify.Verifier`, the same functions `proto new` calls, with the same
prompts and the same repair loop. Only intake is skipped, and it is skipped for
both targets -- the spec is an input to this measurement, not part of it.

The **terminal** half cannot, because the pipeline it would run does not exist
yet; that is what the plan is asking about. Its driver here mirrors the product
loop function for function (`_run_pass` for `passes.run_pass`, `_drive_to_green`
for `build.drive_to_green`) and reuses `build.SMOKE_PATH` and
`build._test_count` outright so the shrink guard is literally the same code.
What it cannot borrow is `drive_to_green` itself, which names the web repair
module at module scope, and `files.write_all`, whose allowlist is the web
tree's five paths.

So the comparison is: identical spec, identical loop shape, identical accounting
-- and one side is running the real code while the other is running a mirror of
it. A divergence in the mirror would bias the number, which is why the mirror is
30 lines rather than 300, and why every place it differs is commented where it
differs.

## Read the README before quoting a number from this

`README.md` beside this file carries the one thing that changes how the output
should be read: the `claude-code` backend arrives with its full tool set, so a
pass can go away and test its own work, and the cost of a hard pass shows up in
the wall clock rather than in the repair count the plan asks for. It also
carries the wrapper that turns that off, and which way to run the six.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from protopilot import build  # noqa: E402
from protopilot.cli import free_port  # noqa: E402
from protopilot.files import GeneratedFile  # noqa: E402
from protopilot.llm import ClaudeCodeLLM, build_llm  # noqa: E402
from protopilot.passes import PassContext, run_pass  # noqa: E402
from protopilot.render import render, render_skeleton  # noqa: E402
from protopilot.runner import SubprocessRunner, docker_available  # noqa: E402
from protopilot.spec import Spec, checkable_paths  # noqa: E402
from protopilot.verify import Verifier, VerifyResult  # noqa: E402
from scripts.output import detail, die, emit, fail, item, ok, step, warn  # noqa: E402
from scripts.paths import PROJECT_ROOT, TMP_DIR  # noqa: E402
from scripts.spikes.terminal_target import brief, writer  # noqa: E402
from scripts.spikes.terminal_target.metering import MeteredLLM, MeteredRunner  # noqa: E402
from scripts.spikes.terminal_target.tui_verify import TuiVerifier  # noqa: E402

HERE = Path(__file__).resolve().parent
SPECS_DIR = HERE / "specs"
TUI_SKELETON = HERE / "skeleton"
DEFAULT_OUT = TMP_DIR / "spikes" / "terminal-target"

TARGETS = ("web", "tui")


# ── specs ────────────────────────────────────────────────────────────────────


def spec_names() -> List[str]:
    return sorted(p.stem for p in SPECS_DIR.glob("*.json"))


def load_spec(name: str) -> Spec:
    path = SPECS_DIR / f"{name}.json"
    if not path.exists():
        die(f"no spec {name!r}; this spike has: {', '.join(spec_names())}")
    return Spec.model_validate_json(path.read_text(encoding="utf-8"))


# ── the terminal driver: a mirror of the product loop, and only a mirror ─────


def render_tui_skeleton(spec: Spec, target: Path) -> List[Path]:
    """The spike's fixed terminal tree, copied byte for byte with tokens filled.

    Substitutions are a subset of `render.substitutions` -- no PORT, no
    PROJECT, no PROJECT_PATH, because there is no container to label and no
    port to publish. That subset is itself part of the finding.
    """
    values = {"APP_NAME": spec.name, "APP_SLUG": spec.slug, "APP_PURPOSE": spec.purpose}
    written: List[Path] = []
    for src in sorted(TUI_SKELETON.rglob("*")):
        rel = src.relative_to(TUI_SKELETON)
        if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
            continue
        dest = target / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(src.read_text(encoding="utf-8"), values))
        written.append(rel)
    return written


def _run_pass(pass_, spec: Spec, ctx: PassContext, llm) -> tuple:
    """`passes.run_pass`, with the terminal allowlist. Returns (files, notes).

    The prompts are not returned: `metering.MeteredLLM` sees every call and
    saves them, which is the only place that can also see the repair calls the
    web target's loop makes inside itself.
    """
    system, user = pass_.build(spec, ctx)
    data = llm.structured(system=system, user=user, schema=pass_.SCHEMA, label=pass_.NAME)
    files = [GeneratedFile(path=f["path"], content=f["content"]) for f in data["files"]]
    written = writer.write_all(ctx.project_dir, files, pass_.NAME)
    notes = data.get("notes", "")
    ctx.notes[pass_.NAME] = notes
    return written, notes


class RecordingVerifier:
    """A `Verifies` that times each attempt and writes it down as it finishes.

    Both halves wrap their verifier in this, and that is the point: the web
    half's loop is `build.drive_to_green`, which hands back its history only
    once it has stopped, and the verify phase is the long half of a web run.
    Recording from inside the wrapper is what makes a killed run still have
    said something. `Verifies` is a Protocol, so this is a legal substitute
    without inheriting anything.
    """

    def __init__(self, inner, record) -> None:
        self.inner = inner
        self.record = record
        self.attempt = 0

    def verify(self) -> VerifyResult:
        self.attempt += 1
        started = time.monotonic()
        result = self.inner.verify()
        self.record.add_verify(self.attempt, result, time.monotonic() - started)
        return result


def _drive_to_green(spec: Spec, ctx: PassContext, llm, verifier, attempts: int, record) -> build.Outcome:
    """`build.drive_to_green`, mirrored. Same bound, same floor, same guard.

    The differences from the original, all forced and all here: it calls the
    terminal repair prompt and the terminal write guard, and it reports through
    the record instead of a log callback. The three-attempt bound, the
    shrink-guard revert and the `Outcome` it returns are the original's.
    """
    history: List[VerifyResult] = []
    repairs: List[str] = []

    for attempt in range(1, attempts + 2):
        step(f"verify (attempt {attempt})...")
        result = verifier.verify()
        history.append(result)
        if result.ok:
            ok(result.summary)
            return build.Outcome(True, attempt, result, history, repairs)

        fail(f"failed at {result.stage}: {result.summary}")
        if attempt > attempts:
            break

        before = build._test_count(ctx.project_dir)
        original = (ctx.project_dir / build.SMOKE_PATH).read_text() if before else ""

        ctx.failure = result.report()
        step("pass repair...")
        try:
            written, notes = _run_pass(brief.REPAIR, spec, ctx, llm)
        except Exception as exc:  # noqa: BLE001 -- a failed repair is an outcome
            fail(f"repair pass failed: {exc}")
            record.add_pass_failure("repair", str(exc))
            break
        record.add_pass("repair", [str(p) for p in written], notes)
        if not written:
            fail(f"repair produced no changes: {notes}")
            break
        repairs.append(f"attempt {attempt} ({result.stage}): {notes}")

        after = build._test_count(ctx.project_dir)
        if before and after < before:
            (ctx.project_dir / build.SMOKE_PATH).write_text(original)
            warn(f"rejected: repair cut the smoke suite from {before} to {after} tests; reverted")
            repairs[-1] += "  [test deletion rejected and reverted]"

    return build.Outcome(False, len(history), history[-1] if history else None, history, repairs)


# ── the record ───────────────────────────────────────────────────────────────


class Record:
    """The run's own JSON, rewritten after every event.

    Every mutation ends in a `flush()`. That is the whole design: a run that
    dies at pass four still leaves three passes' worth of measurement, and a
    measurement that only exists in a process that was killed is not one.
    """

    def __init__(self, path: Path, meta: Dict[str, Any]) -> None:
        self.path = path
        self.data: Dict[str, Any] = {
            **meta,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "green": None,
            "attempts": None,
            "passes": [],
            "verifies": [],
            "calls": [],
            "totals": {},
            "failures": [],
            "error": None,
        }
        self.started = time.monotonic()
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["elapsed_seconds"] = round(time.monotonic() - self.started, 1)
        self.path.write_text(json.dumps(self.data, indent=2, default=str) + "\n", encoding="utf-8")

    # -- events --------------------------------------------------------

    def add_call(self, call, system: str = "", user: str = "") -> None:
        """One model call, with the prompt it was made from, kept as sent."""
        self.data["calls"].append(call.as_dict())
        if system or user:
            n = len(self.data["calls"])
            path = self.path.parent / "prompts" / f"{n:02d}-{call.label}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# SYSTEM\n\n{system}\n\n# USER\n\n{user}\n", encoding="utf-8")
        self.flush()

    def add_pass(self, name: str, files: List[str], notes: str) -> None:
        self.data["passes"].append({"pass": name, "ok": True, "files": files, "notes": notes})
        self.flush()

    def add_pass_failure(self, name: str, error: str) -> None:
        self.data["passes"].append({"pass": name, "ok": False, "error": error})
        self.data["failures"].append({"kind": "pass", "stage": name, "error": error[:8000]})
        self.flush()

    def add_verify(self, attempt: int, result: VerifyResult, seconds: float) -> None:
        self.data["verifies"].append(
            {
                "attempt": attempt,
                "ok": result.ok,
                "stage": result.stage,
                "summary": result.summary,
                "seconds": round(seconds, 1),
            }
        )
        if not result.ok:
            # The full text, not a summary of it. Whether the failures cluster
            # or scatter is answerable only from what they actually said, and
            # it is not answerable later if this was truncated to a headline.
            self.data["failures"].append(
                {
                    "kind": "verify",
                    "attempt": attempt,
                    "stage": result.stage,
                    "summary": result.summary,
                    "output": result.output[-12000:],
                    "logs": result.logs[-6000:],
                }
            )
            path = self.path.parent / "stages" / f"attempt-{attempt}-{result.stage}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result.report(), encoding="utf-8")
        self.flush()

    def finish(
        self,
        *,
        green: Optional[bool],
        attempts: Optional[int],
        totals: dict,
        repairs: Optional[List[str]] = None,
        error: str = "",
    ) -> None:
        self.data.update(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "green": green,
                "attempts": attempts,
                "totals": totals,
                "repairs": repairs or [],
                "error": error or None,
            }
        )
        self.flush()
        jsonl = self.path.parent.parent / "runs.jsonl"
        summary = {k: self.data[k] for k in ("run_id", "target", "spec", "green", "attempts", "elapsed_seconds")}
        summary["totals"] = totals
        summary["stages_failed"] = [f.get("stage") for f in self.data["failures"]]
        with jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, default=str) + "\n")


# ── the two runs ─────────────────────────────────────────────────────────────


def run_web(spec: Spec, tree: Path, llm, record: Record, attempts: int, verify: bool) -> Optional[build.Outcome]:
    """The real pipeline. Nothing here re-implements a pass or the loop."""
    # `proto new` resolves the port at intake and the spec files carry a fixed
    # one, so without this a second prototype still running on 8082 fails the
    # health stage and the run is recorded as a target failure.
    spec.port = free_port(spec.port)
    render_skeleton(spec, tree)
    spec.save(tree)
    ctx = PassContext(project_dir=tree, change=spec.direction)

    for module in build.CODE_PASSES:
        step(f"pass {module.NAME}...")
        try:
            result = run_pass(module, spec, ctx, llm)
        except Exception as exc:  # noqa: BLE001
            record.add_pass_failure(module.NAME, str(exc))
            raise
        record.add_pass(module.NAME, [str(p) for p in result.files], result.notes)
        detail(f"{len(result.files)} file(s)")

    if not verify:
        return None

    verifier = Verifier(
        project_dir=tree,
        port=spec.port,
        runner=SubprocessRunner(),
        screens=checkable_paths(spec),
    )
    outcome = build.drive_to_green(
        spec, ctx, llm, RecordingVerifier(verifier, record), attempts=attempts, log=lambda m: detail(m.strip())
    )
    try:
        verifier.down()
    except Exception as exc:  # noqa: BLE001 -- teardown must not lose a record
        warn(f"could not tear the stack down: {exc}")
    return outcome


def run_tui(
    spec: Spec, tree: Path, llm, record: Record, attempts: int, verify: bool, only: List[str]
) -> Optional[build.Outcome]:
    render_tui_skeleton(spec, tree)
    spec.save(tree)
    ctx = PassContext(project_dir=tree, change=spec.direction)

    for pass_ in brief.CODE_PASSES:
        if only and pass_.NAME not in only:
            continue
        step(f"pass {pass_.NAME}...")
        try:
            written, notes = _run_pass(pass_, spec, ctx, llm)
        except Exception as exc:  # noqa: BLE001
            record.add_pass_failure(pass_.NAME, str(exc))
            raise
        record.add_pass(pass_.NAME, [str(p) for p in written], notes)
        detail(f"{len(written)} file(s): {', '.join(str(p) for p in written)}")

    if not verify:
        return None

    verifier = TuiVerifier(project_dir=tree, runner=SubprocessRunner())
    return _drive_to_green(spec, ctx, llm, RecordingVerifier(verifier, record), attempts, record)


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 of docs/TODO/terminal-target.md, one run at a time.")
    parser.add_argument("--target", choices=TARGETS, help="web runs the real pipeline; tui runs the spike driver")
    parser.add_argument("--spec", help=f"one of: {', '.join(spec_names()) or '(none)'}")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="where records and trees are kept")
    parser.add_argument("--attempts", type=int, default=3, help="repair attempts before the floor")
    parser.add_argument("--backend", default=None, help="api | claude-code | offline (default: $PROTOPILOT_LLM)")
    parser.add_argument("--passes", default="", help="comma-separated pass names; tui only, for smoke-testing")
    parser.add_argument("--no-verify", action="store_true", help="generate but do not boot")
    parser.add_argument("--list", action="store_true", help="list the specs and stop")
    parser.add_argument("--json", action="store_true", help="print the record on stdout when the run ends")
    args = parser.parse_args()

    if args.list:
        for name in spec_names():
            spec = load_spec(name)
            emit_line = f"{name:<16} archetype={spec.archetype:<16} entities={len(spec.entities)}"
            item(f"{emit_line}  {spec.purpose}")
        return 0

    if not args.target or not args.spec:
        die("--target and --spec are both required (or --list)")

    spec = load_spec(args.spec)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{args.target}-{args.spec}-{stamp}"
    run_dir = Path(args.out) / run_id
    tree = run_dir / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)

    if args.target == "web" and not args.no_verify:
        available, why = docker_available(SubprocessRunner())
        if not available:
            die(f"{why} -- the web half of this comparison is the real pipeline, which needs Docker")

    runner = MeteredRunner()
    inner = build_llm(backend=args.backend)
    if isinstance(inner, ClaudeCodeLLM):
        # Rebuilt through the public constructor rather than having its runner
        # swapped afterwards: `runner` is a real parameter of this backend, and
        # reaching in to replace `_runner` would be a private attribute this
        # spike is not entitled to. Every other setting is carried across.
        inner = ClaudeCodeLLM(
            model=inner.model, effort=inner.effort, runner=runner, binary=inner.binary, timeout=inner.timeout
        )
    else:
        warn(f"{type(inner).__name__} exposes no usage; token counts will be recorded as unavailable")
    llm = MeteredLLM(inner=inner, runner=runner)

    record = Record(
        run_dir / "record.json",
        {
            "run_id": run_id,
            "target": args.target,
            "spec": args.spec,
            "archetype": spec.archetype,
            "backend": type(inner).__name__,
            "model": getattr(inner, "model", None),
            "attempts_allowed": args.attempts,
            "commit": _commit(),
            "tree": str(tree),
        },
    )
    llm.on_call = record.add_call

    step(f"{run_id} -> {run_dir}")
    outcome: Optional[build.Outcome] = None
    error = ""
    try:
        only = [p.strip() for p in args.passes.split(",") if p.strip()]
        if args.target == "web":
            if only:
                die("--passes is tui only; the web half runs the real pipeline unmodified")
            outcome = run_web(spec, tree, llm, record, args.attempts, not args.no_verify)
        else:
            outcome = run_tui(spec, tree, llm, record, args.attempts, not args.no_verify, only)
    except Exception as exc:  # noqa: BLE001 -- an aborted run is a result
        error = f"{type(exc).__name__}: {exc}"
        fail(error)

    # `green: null` is not `green: false`. A generation that was never booted
    # has not failed, and a record that says it did would make an un-verified
    # run indistinguishable from a broken one the moment anybody counted rows.
    record.finish(
        green=outcome.ok if outcome else None,
        attempts=outcome.attempts if outcome else None,
        totals=llm.totals(),
        repairs=outcome.repairs if outcome else [],
        error=error,
    )

    if args.json:
        emit(record.data)

    totals = llm.totals()
    if outcome and outcome.ok:
        ok(f"{run_id}: green in {outcome.attempts} verify attempt(s)")
    elif outcome is None and not error:
        warn(f"{run_id}: generated, not verified")
    else:
        fail(f"{run_id}: not green")
        for failure in record.data["failures"]:
            item(f"{failure.get('kind')} / {failure.get('stage')}: {failure.get('summary', failure.get('error', ''))}")
    detail(f"{totals['calls']} model call(s), {totals['seconds']}s of model time")
    if totals.get("usage_available"):
        detail(
            f"tokens in/out {totals['input_tokens']}/{totals['output_tokens']}, "
            f"cache read {totals['cache_read_input_tokens']}, "
            f"api-equivalent ${totals.get('cost_usd_equivalent')}"
        )
    else:
        warn("this backend surfaced no token usage; the record says so rather than guessing")
    detail(f"record: {record.path}")
    return 0 if ((outcome and outcome.ok) or (outcome is None and not error)) else 1


def _commit() -> str:
    result = SubprocessRunner().run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "--short", "HEAD"], timeout=10)
    return result.stdout.strip() if result.ok else "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
