"""The command line.

    proto new "an app for tracking camping gear across trips"
    proto add "let people mark items as packed"
    proto up | down | logs | test | spec | doctor
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import click

from protopilot import __version__, build as builder
from protopilot.baseline import standard_screens
from protopilot.llm import ClaudeCodeLLM, ClaudeLLM, LLMError, build_llm
from protopilot import registry
from protopilot.passes import PassContext, intake
from protopilot.render import render_skeleton
from protopilot.runner import SubprocessRunner, docker_available
from protopilot.spec import SPEC_DIR, SPEC_FILENAME, Screen, Spec, checkable_paths
from protopilot.verify import Verifier

PORT_RANGE = range(8080, 8180)


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


def _project(directory: str | None) -> Path:
    path = Path(directory or ".").resolve()
    if not (path / SPEC_DIR / SPEC_FILENAME).exists():
        raise click.ClickException(
            f"{path} is not a proto-pilot project (no {SPEC_DIR}/{SPEC_FILENAME})"
        )
    return path


def _verifier(project_dir: Path, spec: Spec) -> Verifier:
    return Verifier(
        project_dir, spec.port, SubprocessRunner(), screens=checkable_paths(spec)
    )


def _compose(project_dir: Path, *args: str) -> int:
    return subprocess.call(["docker", "compose", *args], cwd=str(project_dir))  # noqa: S603


@click.group()
@click.version_option(__version__, prog_name="proto-pilot")
def main() -> None:
    """Turn an idea and a little direction into a running prototype."""


@main.command()
@click.argument("idea")
@click.option("--dir", "directory", default=None, help="Target directory (default: ./<slug>).")
@click.option("--direction", default="", help="Extra steer: look, feel, emphasis.")
@click.option("--port", type=int, default=None, help="Host port (default: first free from 8080).")
@click.option("--attempts", type=int, default=3, show_default=True, help="Repair attempts before handing back a RUNBOOK.")
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
    llm = build_llm(offline=offline, backend=backend)

    if not no_verify:
        ok, why = docker_available(SubprocessRunner())
        if not ok:
            # Said now rather than after the generation passes, because after
            # is when the tokens have already been spent.
            raise click.ClickException(
                f"{why}. Start Docker, or pass --no-verify to generate without booting."
            )

    _echo("intake...")
    ctx = PassContext(project_dir=Path("."), change=direction)
    try:
        if llm.offline:
            data = intake.offline(idea, ctx)
        else:
            system, user = intake.build(idea, ctx)
            data = llm.structured(
                system=system, user=user, schema=intake.SCHEMA, label=intake.NAME
            )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    spec = Spec.model_validate(data)
    spec.port = free_port(port)
    spec.direction = direction or spec.direction
    spec.protopilot_version = __version__
    if not spec.screens:
        # Screens are the contract the smoke tests and the routes are both
        # generated from, so an empty list is not something to pass along.
        spec.screens = [Screen(**s) for s in standard_screens(spec)]

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
        raise click.ClickException(
            f"{exc}\n  part-built tree and a RUNBOOK are at {target}"
        ) from exc

    registry.record(
        slug=spec.slug, name=spec.name, path=target, port=spec.port, idea=idea
    )

    if not no_git:
        _git_init(target)

    if no_verify:
        _echo(f"\nGenerated (not verified). `cd {target} && make up`")
        return

    _finish(spec, ctx, llm, target, attempts)


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
        raise click.ClickException(
            "`add` needs the model: the baseline generator cannot read a change request."
        )

    # A change request can add or retype a column, and there are no
    # migrations -- so the old volume is dropped rather than silently kept and
    # left disagreeing with the models it is about to be read through.
    _compose(target, "down", "-v")

    _echo("amending spec...")
    system, user = intake.build_amend(spec, change)
    try:
        data = llm.structured(
            system=system, user=user, schema=intake.SCHEMA, label="amend"
        )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    updated = Spec.model_validate(data)
    # Identity is not the model's to change: the slug is the database name and
    # the port is what the user has open in a tab.
    updated.slug, updated.port = spec.slug, spec.port
    updated.protopilot_version = __version__

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
    outcome = builder.drive_to_green(
        spec, ctx, llm, _verifier(target, spec), attempts=attempts, log=_echo
    )
    if outcome.ok:
        runbook = target / "RUNBOOK.md"
        if runbook.exists():
            runbook.unlink()  # a stale runbook reads as a live problem
        _echo(f"\n  {spec.name} is up:  http://localhost:{spec.port}")
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
    click.echo(
        (target / SPEC_DIR / SPEC_FILENAME).read_text() if as_json else spec.summary()
    )


@main.command()
@click.option("--dir", "directory", default=None)
def up(directory: str | None) -> None:
    """Start the app."""
    target = _project(directory)
    spec = Spec.load(target)
    code = _compose(target, "up", "-d", "--build")
    if code == 0:
        _echo(f"http://localhost:{spec.port}")
    sys.exit(code)


@main.command()
@click.option("--dir", "directory", default=None)
@click.option("--purge", is_flag=True, help="Also delete saved data (the database volume).")
def down(directory: str | None, purge: bool) -> None:
    """Stop the app. Saved data survives unless --purge."""
    target = _project(directory)
    args = ["down", "-v"] if purge else ["down"]
    code = _compose(target, *args)
    if code == 0:
        _echo("stopped; data kept (`proto down --purge` to drop it)" if not purge
              else "stopped; data dropped")
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


@main.command()
@click.option("--port", type=int, default=7000, show_default=True)
@click.option("--workspace", default=None, help="Where prototypes are generated (default: ./prototypes).")
@click.option("--backend", type=click.Choice(["api", "claude-code", "offline"]), default=None)
@click.option("--demo/--no-demo", default=True, show_default=True,
              help="Hide test files in the UI (they are still generated and run).")
def serve(port: int, workspace: str | None, backend: str | None, demo: bool) -> None:
    """Run the web front end."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise click.ClickException('the front end needs extras: pip install -e ".[web]"') from exc

    if backend in ("claude-code", "subscription"):
        # Fail here rather than three passes into a generation.
        from protopilot.llm import ClaudeCodeLLM

        try:
            ClaudeCodeLLM().check()
        except LLMError as exc:
            raise click.ClickException(
                f"{exc}\n     set PROTOPILOT_CLAUDE_BIN to a working `claude` binary"
            ) from exc

    from protopilot.web.app import create_app

    root = Path(workspace).resolve() if workspace else Path.cwd() / "prototypes"
    _echo(f"workspace: {root}")
    _echo(f"http://localhost:{port}" + ("  (demo mode: tests hidden)" if demo else ""))
    uvicorn.run(create_app(root, backend=backend, demo=demo), host="127.0.0.1", port=port,
                log_level="warning")


@main.command(name="ls")
def list_projects() -> None:
    """List every prototype generated on this machine."""
    entries = registry.prune()
    if not entries:
        _echo("no prototypes yet -- `proto new \"an idea\"`")
        return
    width = max(len(e.slug) for e in entries)
    for entry in entries:
        _echo(f"  {entry.slug:<{width}}  :{entry.port}  {entry.path}")
    _echo(f"\n  {len(entries)} prototype(s)")


@main.command(name="rm")
@click.option("--dir", "directory", default=None)
@click.option("--yes", "-y", is_flag=True)
def remove_project(directory: str | None, yes: bool) -> None:
    """Delete this prototype: containers, data and the tree."""
    target = _project(directory)
    spec = Spec.load(target)
    if not yes and not click.confirm(
        f"Delete {spec.name} and everything in {target}?", default=False
    ):
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
    ok = True

    docker_ok, why = docker_available(SubprocessRunner())
    _echo(f"{'ok  ' if docker_ok else 'FAIL'} docker: {why}")
    ok &= docker_ok

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
