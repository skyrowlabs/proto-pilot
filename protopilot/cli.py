"""The command line.

proto new "an app for tracking camping gear across trips"
proto add "let people mark items as packed"
proto up | down | logs | test | spec | doctor
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
from pathlib import Path

import click

from protopilot import __version__
from protopilot import build as builder
from protopilot import containers, registry
from protopilot.archetypes import crud
from protopilot.llm import ClaudeCodeLLM, ClaudeLLM, LLMError, build_llm
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
        raise click.ClickException(f"{path} is not a proto-pilot project (no {SPEC_DIR}/{SPEC_FILENAME})")
    return path


def _verifier(project_dir: Path, spec: Spec) -> Verifier:
    return Verifier(project_dir, spec.port, SubprocessRunner(), screens=checkable_paths(spec))


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
            raise click.ClickException(f"{why}. Start Docker, or pass --no-verify to generate without booting.")

    _echo("intake...")
    ctx = PassContext(project_dir=Path("."), change=direction)
    try:
        if llm.offline:
            data = intake.offline(idea, ctx)
        else:
            system, user = intake.build(idea, ctx)
            data = llm.structured(system=system, user=user, schema=intake.SCHEMA, label=intake.NAME)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc

    spec = Spec.model_validate(data)
    spec.port = free_port(port)
    spec.direction = direction or spec.direction
    spec.protopilot_version = __version__
    if not spec.screens:
        # Screens are the contract the smoke tests and the routes are both
        # generated from, so an empty list is not something to pass along.
        spec.screens = [Screen(**s) for s in crud.screens(spec)]

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
        raise click.ClickException("`add` needs the model: the baseline generator cannot read a change request.")

    # A change request can add or retype a column, and there are no
    # migrations -- so the old volume is dropped rather than silently kept and
    # left disagreeing with the models it is about to be read through.
    _compose(target, "down", "-v")

    _echo("amending spec...")
    system, user = intake.build_amend(spec, change)
    try:
        data = llm.structured(system=system, user=user, schema=intake.SCHEMA, label="amend")
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
    outcome = builder.drive_to_green(spec, ctx, llm, _verifier(target, spec), attempts=attempts, log=_echo)
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

    if backend in ("claude-code", "subscription"):
        # Fail here rather than three passes into a generation.
        from protopilot.llm import ClaudeCodeLLM

        try:
            ClaudeCodeLLM().check()
        except LLMError as exc:
            raise click.ClickException(f"{exc}\n     set PROTOPILOT_CLAUDE_BIN to a working `claude` binary") from exc

    from protopilot.web.app import create_app

    root = Path(workspace).resolve() if workspace else Path.cwd() / "prototypes"
    _echo(f"workspace: {root}")
    _echo(f"http://localhost:{port}" + ("  (demo mode: tests hidden)" if demo else ""))
    uvicorn.run(create_app(root, backend=backend, demo=demo), host="127.0.0.1", port=port, log_level="warning")


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
