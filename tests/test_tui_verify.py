"""Verify, for the terminal target — which is where this target is better.

Phase 5 of `docs/TODO/terminal-target.md`, and the phase that plan calls "the
reason to be optimistic about the whole plan". Everything the web verifier is
built around — a daemon, a port, a `/healthz` race, an optional browser that
gets reported as skipped — has no counterpart here. What replaces the browser
stage is two strings: the app's rendered screen buffer, and the buffer of an
application with nothing in it.

Two things in this file are doing more work than the rest.

**The blank-screen check is demonstrated, not asserted.** The plan's acceptance
criterion is that a terminal app whose screen renders nothing *fails verify*,
shown by building one. So one is built — a `HomeScreen` whose `compose()`
yields nothing — and driven through the real verifier, which returns red at
`paint`. A test that merely asserted the comparison exists would pass against a
check that compares a buffer to itself.

**No seam here is a callable default argument.** `verify.Verifier` bound
`getter=http_get` in its signature, evaluated once at `def` time, so a verifier
built through `targets.web.verifier()` could not be reached by monkeypatching
`verify.http_get` — and the middle of that class had therefore never run under
a test. That is fixed, and `test_no_seam_is_welded_shut` is the structural gate
that stops either verifier growing another one.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import FakeRunner

from protopilot import verify as web_verify
from protopilot import verify_tui
from protopilot.build import PassContext, drive_to_green
from protopilot.build import generate as run_passes
from protopilot.build import write_runbook
from protopilot.llm import OfflineLLM
from protopilot.render import render_skeleton
from protopilot.runner import CommandResult
from protopilot.spec import Spec
from protopilot.targets import tui as tui_target
from protopilot.targets import web as web_target
from protopilot.verify_tui import STAGES, TuiVerifier

# Host-side: no key, no Docker daemon, no browser, no port, no network. That
# this entire file needs none of them is the claim Phase 5 is making.
pytestmark = [pytest.mark.unit]

pytest.importorskip("textual")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pytest_asyncio")


@pytest.fixture()
def tui_spec(spec) -> Spec:
    spec.target = "tui"
    return spec


@pytest.fixture()
def tree(tui_spec, tmp_path) -> Path:
    """A working terminal app, generated offline through the real pipeline."""
    render_skeleton(tui_spec, tmp_path)
    tui_spec.save(tmp_path)
    run_passes(tui_spec, PassContext(project_dir=tmp_path), OfflineLLM(), log=lambda _: None)
    return tmp_path


def built(project_dir: Path, spec: Spec, runner=None) -> TuiVerifier:
    """The factory's product, typed as the concrete class it actually is.

    `verifier()` is annotated `-> Verifies` on purpose: `drive_to_green` must
    never learn which implementation it got, and this target existing at all
    depends on that staying true. These tests are the exception — they are
    about the construction rather than the protocol — so the narrowing is
    deliberate, and it doubles as the assertion that the registry still hands
    back the terminal verifier rather than the Docker one.

    The same helper, for the same reason, as `tests/test_verifier_wiring.py`.
    """
    made = tui_target.verifier(project_dir, spec, runner)
    assert isinstance(made, TuiVerifier)
    return made


BLANK_HOME = '''\
"""A screen that renders nothing. The failure the plan wants demonstrated."""

from __future__ import annotations

from app.base import AppScreen
from textual.app import ComposeResult


class HomeScreen(AppScreen):
    def compose(self) -> ComposeResult:
        return iter(())
'''

BROKEN_IMPORT = "this is not python at all(\n"

RAISES_ON_MOUNT = """\
from __future__ import annotations

from app.base import AppScreen
from textual.app import ComposeResult
from textual.widgets import Static


class HomeScreen(AppScreen):
    def compose(self) -> ComposeResult:
        yield Static("never gets here")

    def on_mount(self) -> None:
        raise RuntimeError("the generated screen blew up on mount")
"""


def with_screens(tree: Path, source: str) -> Path:
    (tree / "app" / "screens.py").write_text(source)
    return tree


# ── the seams ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cls", [TuiVerifier, web_verify.Verifier])
def test_no_seam_is_welded_shut(cls):
    """No constructor default may be a callable.

    This is the general form of a specific defect. `Verifier.__init__` had
    `getter=http_get` as a default argument, which Python evaluates once at
    `def` time — so the attribute was bound to the function object that existed
    at import, and `monkeypatch.setattr(verify, "http_get", ...)` could not
    reach a verifier the factory had already built. The tests that drove the
    real factory all stopped at the build stage as a result, and coverage
    showed the line as covered because the assignment ran.

    Stated structurally rather than as a comment, because the next person
    adding a collaborator to either verifier will reach for the same shape.
    """
    welded = [
        name
        for name, parameter in inspect.signature(cls.__init__).parameters.items()
        if parameter.default is not inspect.Parameter.empty and callable(parameter.default)
    ]
    assert not welded, f"{cls.__name__} freezes {welded} at def time; take None and resolve in the body"


def test_the_web_getter_is_now_reachable_through_the_real_factory(spec, tmp_path, monkeypatch):
    """The defect above, on the class it was found in, through the path that
    could not reach it. `targets.web.verifier()` passes no getter, so before the
    fix this monkeypatch was invisible and `wait_healthy` hit a real socket."""
    calls: list[str] = []

    def fake_get(url: str, timeout: float) -> tuple[int, str]:
        calls.append(url)
        return 200, json.dumps({"ok": True})

    monkeypatch.setattr(web_verify, "http_get", fake_get)
    made = web_target.verifier(tmp_path, spec, FakeRunner())
    assert isinstance(made, web_verify.Verifier)
    healthy, _ = made.wait_healthy()

    assert healthy, "the injected getter never ran"
    assert calls == [f"http://localhost:{spec.port}/healthz"]


def test_the_factory_takes_the_runner_it_is_given(tui_spec, tmp_path):
    runner = FakeRunner()
    assert built(tmp_path, tui_spec, runner).runner is runner


def test_the_factory_falls_back_to_a_real_subprocess_runner(tui_spec, tmp_path, monkeypatch):
    """`runner or SubprocessRunner()`, resolved from the target module's
    namespace. Proven by watching the substitute get used rather than by
    looking at the type of the attribute."""
    runner = FakeRunner()
    monkeypatch.setattr(tui_target, "SubprocessRunner", lambda: runner)
    assert built(tmp_path, tui_spec).runner is runner


# ── what this target does NOT do ─────────────────────────────────────────


def test_the_verifier_never_reaches_for_docker(tree, tui_spec):
    """Asserted on the commands, not on the source. The whole argument for this
    target is that there is nothing to build, wait for, publish or orphan."""
    runner = FakeRunner()
    built(tree, tui_spec, runner).verify()

    assert runner.calls, "the verifier ran nothing at all"
    for call in runner.calls:
        assert "docker" not in call[0], f"a terminal verify shelled out to {call}"


def test_the_health_wait_and_the_port_are_gone_rather_than_dead(tui_spec, tmp_path):
    """The plan asks for this to be asserted rather than left implicit.

    A `wait_healthy` that existed and always returned True would pass every
    other test in this file and would be a stage nobody could see was doing
    nothing.
    """
    made = built(tmp_path, tui_spec)
    for absent in ("wait_healthy", "check_pages", "up", "down", "compose", "logs", "port"):
        assert not hasattr(made, absent), f"the terminal verifier still carries {absent}"
    assert "health" not in STAGES and "browser" not in STAGES and "build" not in STAGES


def test_the_stages_map_one_for_one_onto_the_web_ones():
    """Four stages, in the web order. A run whose failing stage depended on
    which target it was would make the two targets unaddable, which is the
    whole reason the web target stays green as a control."""
    assert STAGES == ("import", "boot", "tests", "paint")
    assert len(STAGES) == len(web_verify.STAGES) + 1, "paint is the browser stage's counterpart, plus one"


# ── the environment each attempt runs in ─────────────────────────────────


def test_every_attempt_gets_a_fresh_database(tree, tui_spec):
    """The one line that replaces `docker compose down -v`.

    There are no migrations here either, and `create_all` cannot alter an
    existing table — so a reused file would verify a repaired model against the
    schema it had before the repair, and the failure would be a column that
    the fix had already added.
    """
    made = built(tree, tui_spec, FakeRunner())
    databases = {made.env()["APP_DB"] for _ in range(3)}
    assert len(databases) == 3


def test_the_environment_is_put_back_afterwards(tree, tui_spec):
    """A leaked `APP_DB` points the NEXT run at a database that already has
    rows in it, and the seed guard then makes an unseeded app look green."""
    before = dict(os.environ)
    built(tree, tui_spec, FakeRunner()).check_import()
    assert dict(os.environ) == before


def test_the_tree_is_on_the_path_and_nothing_is_installed(tree, tui_spec):
    made = built(tree, tui_spec, FakeRunner())
    assert made.env()["PYTHONPATH"] == str(tree)
    assert made.env()["PYTHONDONTWRITEBYTECODE"] == "1"


# ── the stages, on trees built to fail at each one ───────────────────────


def test_a_tree_that_does_not_import_is_red_at_import(tree, tui_spec):
    result = built(with_screens(tree, BROKEN_IMPORT), tui_spec).verify()
    assert not result.ok and result.stage == "import"
    assert "SyntaxError" in result.output


def test_a_tree_that_raises_on_mount_is_red_at_boot(tree, tui_spec):
    result = built(with_screens(tree, RAISES_ON_MOUNT), tui_spec).verify()
    assert not result.ok and result.stage == "boot"
    assert "the generated screen blew up on mount" in result.output


def test_a_screen_that_renders_nothing_fails_verify(tree, tui_spec):
    """**The plan's acceptance criterion, demonstrated by generating one.**

    Not "the check exists" — an app is built whose home screen composes no
    widgets, and the real verifier is asked about it.

    It comes back red at `tests`, and that is a finding rather than a
    disappointment: `skeleton/tui/tests/test_boots.py` makes the same
    assertion one stage earlier, so a blank screen in a real tree is caught by
    the app's own suite before the paint stage ever sees it. Two guards, and
    this is the outer one. The next test removes it to reach the other.
    """
    blank = with_screens(tree, BLANK_HOME)

    result = built(blank, tui_spec).verify()

    assert not result.ok, "an app that renders an empty screen was handed back as green"
    assert result.stage in {"tests", "paint"}
    assert "empty screen" in result.output, "nothing in the report says the screen was blank"


def test_the_paint_stage_is_the_backstop_when_nothing_else_looks(tree, tui_spec):
    """The stage the plan actually asks for, reached by silencing the layer above.

    Every test in the tree is replaced with one that passes, so the smoke suite
    and the skeleton's boot check are both out of the way and the only thing
    left that could notice is the buffer comparison. If this went green the
    paint stage would be decoration, and the previous test would have been
    proving that `test_boots.py` works.
    """
    blank = with_screens(tree, BLANK_HOME)
    for path in (blank / "tests").glob("test_*.py"):
        path.write_text("def test_nothing() -> None:\n    assert True\n")

    result = built(blank, tui_spec).verify()

    assert not result.ok
    assert result.stage == "paint"
    assert "empty screen buffer" in result.summary


def test_the_blank_screen_report_shows_both_buffers(tree, tui_spec):
    """What the repair pass is given instead of a log tail. "It rendered
    nothing" is not actionable; the screen beside an empty one is."""
    blank = with_screens(tree, BLANK_HOME)
    for path in (blank / "tests").glob("test_*.py"):
        path.write_text("def test_nothing() -> None:\n    assert True\n")

    result = built(blank, tui_spec).verify()
    assert "rendered buffer" in result.output
    assert "an empty application renders" in result.output


def test_a_failing_smoke_suite_is_red_at_tests(tree, tui_spec):
    (tree / "tests" / "test_smoke.py").write_text(
        'def test_the_spec_promised_something_else() -> None:\n    assert False, "no packing list screen"\n'
    )
    result = built(tree, tui_spec).verify()
    assert not result.ok and result.stage == "tests"
    assert "no packing list screen" in result.output


def test_a_working_tree_is_green(tree, tui_spec):
    """The offline baseline, verified end to end by the real thing.

    No key, no Docker, no Playwright — which is the acceptance criterion this
    target exists to satisfy, and the reason this whole file runs in the unit
    suite rather than behind an environment gate.
    """
    result = built(tree, tui_spec).verify()
    assert result.ok, f"{result.stage}: {result.summary}\n{result.output}"
    assert result.stage == "tests"
    assert "HomeScreen" in result.summary


# ── the probe itself ─────────────────────────────────────────────────────


def test_the_probe_reports_json_on_the_last_line_of_stdout(tree):
    """Textual logs, and generated code prints. The payload is last and on a
    stream nothing else uses, or the verifier is parsing somebody's debugging."""
    (tree / "app" / "seed.py").write_text(
        (tree / "app" / "seed.py").read_text() + '\nprint("a stray print in generated code")\n'
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(verify_tui.PROBE)],
        cwd=str(tree),
        env={**os.environ, "PYTHONPATH": str(tree), "APP_DB": str(tree / "probe.sqlite3")},
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["ok"] and payload["painted"]
    assert payload["screen"] == "HomeScreen"
    assert payload["depth"] == 1, "the home screen is not the bottom of the stack"
    assert "Gear List" in payload["text"], "the probe cannot read what the app is showing"


def test_a_probe_that_will_not_parse_is_reported_as_the_command(tree, tui_spec):
    """The probe reports its own failures as JSON, so unparseable output means
    the process died before it could — a segfault, a timeout, a module-level
    `sys.exit()`. The report is then the whole command, not our parse error."""
    runner = FakeRunner([(["python", str(verify_tui.PROBE)], (1, "not json at all", "killed"))])
    payload = TuiVerifier(tree, runner=runner, python="python").boot()
    assert payload["ok"] is False
    assert "killed" in payload["traceback"] or "not json at all" in payload["traceback"]


# ── the loop around it ───────────────────────────────────────────────────


def test_the_repair_loop_accepts_what_the_factory_returns(tree, tui_spec):
    """`Verifies` is a Protocol, so nothing checks this at import time.

    The offline baseline cannot repair, so the loop stops after one verify and
    hands the tree back at the stage that was red — the same floor, the same
    three attempts, the same shape as the web target's.
    """
    broken = with_screens(tree, BROKEN_IMPORT)
    outcome = drive_to_green(
        tui_spec,
        PassContext(project_dir=broken),
        OfflineLLM(),
        built(broken, tui_spec),
        attempts=3,
        log=lambda _: None,
    )
    assert not outcome.ok
    assert outcome.result is not None and outcome.result.stage == "import"
    assert outcome.attempts == 1, "a baseline that cannot repair must not burn three attempts"


def test_the_runbook_does_not_tell_a_terminal_user_to_run_docker(tree, tui_spec):
    """The floor has to be true for the medium it is written in.

    A RUNBOOK is what somebody reads when nothing else worked, and one that
    confidently says `docker compose logs -f app` to a person holding a single
    Python process is worse than no RUNBOOK at all.
    """
    broken = with_screens(tree, BROKEN_IMPORT)
    outcome = drive_to_green(
        tui_spec,
        PassContext(project_dir=broken),
        OfflineLLM(),
        built(broken, tui_spec),
        attempts=1,
        log=lambda _: None,
    )
    body = write_runbook(broken, tui_spec, outcome).read_text()

    assert "docker" not in body.lower()
    assert "python -m app.main" in body
    assert "app/screens.py" in body, "the runbook does not list the files that were generated"
    assert "app/routes.py" not in body, "the runbook names a file this target has never had"


def test_the_web_runbook_is_unchanged_in_shape(spec, tmp_path):
    """The control. The runbook stopped being written in Docker for the
    terminal target and must not have stopped being written in Docker for the
    one that actually runs there."""
    render_skeleton(spec, tmp_path)
    run_passes(spec, PassContext(project_dir=tmp_path), OfflineLLM(), log=lambda _: None)
    outcome = drive_to_green(
        spec,
        PassContext(project_dir=tmp_path),
        OfflineLLM(),
        web_target.verifier(tmp_path, spec, FakeRunner([(["docker", "compose", "up"], (1, "", "no such image"))])),
        attempts=1,
        log=lambda _: None,
    )
    body = write_runbook(tmp_path, spec, outcome).read_text()

    assert "docker compose up -d --build" in body
    assert "Container logs" in body
    assert "app/routes.py" in body and "app/templates/index.html" in body


def test_the_cli_builds_the_terminal_verifier_through_the_target(tree, tui_spec):
    """`cli._verifier` asks the registry rather than naming a class. Without
    that, `proto add` on a terminal tree would try to boot Docker."""
    from protopilot import cli
    from protopilot.verify_tui import TuiVerifier as Concrete

    assert isinstance(cli._verifier(tree, tui_spec), Concrete)


def test_a_fake_runner_is_all_it_takes_to_drive_the_middle(tree, tui_spec):
    """The point of the seam, stated as a test.

    Every stage can be scripted without a subprocess, which is what makes the
    branches above testable at all. If this stops being true, the verifier has
    grown a collaborator it constructs for itself.
    """
    runner = FakeRunner(
        [
            (["python", "-c"], (0, "", "")),
            (["python", str(verify_tui.PROBE)], (0, json.dumps({"ok": True, "painted": True, "screen": "S"}), "")),
            (["python", "-m", "pytest"], (0, "3 passed", "")),
        ]
    )
    result = TuiVerifier(tree, runner=runner, python="python").verify()
    assert result.ok, result.output
    assert isinstance(runner.calls[0], list)


def test_a_command_result_is_what_the_stages_read(tree, tui_spec):
    """Guard on the fake as much as on the code: `FakeRunner` has to hand back
    the same type `SubprocessRunner` does, or every scripted test above is
    proving something about the fake."""
    runner = FakeRunner()
    assert isinstance(built(tree, tui_spec, runner).check_import(), CommandResult)


# ── the acceptance criterion, through the command a person types ─────────


def test_proto_new_target_tui_offline_produces_a_working_terminal_app(tmp_path, monkeypatch):
    """`proto new "<idea>" --target tui --offline`, verified, end to end.

    The plan's acceptance criterion in one test: a terminal app that starts,
    renders a non-empty screen and passes its own smoke suite — with no key, no
    Docker and no Playwright. Nothing here is faked below the CLI: the real
    click command runs the real passes, writes the real tree and drives the
    real verifier, and the only substitution is the registry path.

    The web target's preflight is forced to fail, so a CLI that asked the wrong
    target for permission would go red here rather than passing on a laptop
    that happens to have a daemon running.
    """
    from click.testing import CliRunner

    from protopilot.cli import main
    from protopilot.targets import web as web

    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))
    monkeypatch.setattr(web, "preflight", lambda runner: (False, "the docker daemon is not running"))

    out = tmp_path / "tree"
    result = CliRunner().invoke(
        main,
        ["new", "track camping gear across trips", "--dir", str(out), "--target", "tui", "--offline", "--no-git", "-y"],
    )

    assert result.exit_code == 0, result.output + repr(result.exception)
    assert "green" in result.output, result.output
    assert not (out / "RUNBOOK.md").exists(), "a green run left a runbook behind"
    assert (out / "app" / "screens.py").exists()
    assert not (out / "compose.yml").exists(), "a terminal tree has nothing to compose"
    assert "docker" not in result.output.lower()


def test_a_docker_command_against_a_terminal_tree_says_what_to_type_instead(tree, tui_spec, monkeypatch):
    """`proto up` on a terminal prototype.

    Every `docker compose` this CLI runs goes through one function, so one
    guard covers `up`, `down`, `reset`, `logs` and `test`. Without it the user
    gets compose's own error about a missing `compose.yml`, which reads as a
    broken generation rather than as the wrong command for the medium.
    """
    from click.testing import CliRunner

    from protopilot.cli import main

    tui_spec.save(tree)
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tree / "projects.json"))
    result = CliRunner().invoke(main, ["logs", "--dir", str(tree)])

    assert result.exit_code != 0
    assert "does not run in Docker" in result.output
    assert "make run" in result.output, "the refusal does not say what to type instead"
