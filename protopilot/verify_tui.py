"""Boot the terminal app, drive it, run its smoke tests, report a verdict.

The counterpart of `verify.py`, and it returns that module's `VerifyResult`
rather than a type of its own -- `drive_to_green` consumes the `Verifies`
Protocol and must never learn which implementation it was handed.

The stage names differ because the stages differ:

    web            terminal      what it catches
    build       -> import        the tree does not load at all
    health      -> boot          it loads but will not start
    tests       -> tests         it starts but does not do what was asked
    browser     -> paint         it does all of that and shows nothing

Attribution order is the web order exactly -- import, boot, tests, paint --
even though `boot` and `paint` are measured in the same subprocess. A run whose
failing stage depended on which target it was would make the two targets
unaddable, and the whole reason the web target stays green is that it is the
control.

**Everything the web verifier is built around disappears.** No Docker, no port,
no `/healthz`, no health race, no compose project to orphan. What replaces
`docker compose down -v` is one line: each attempt gets a fresh SQLite file,
because there are no migrations here either and `create_all` cannot alter an
existing table -- so a reused database would verify a repaired model against
the schema it had before the repair.

## Every seam is an argument, and none of them is a callable default

`verify.Verifier` binds `getter=http_get` as a **default argument value**,
evaluated once at `def` time. Monkeypatching `verify.http_get` therefore cannot
reach a verifier built through `targets.web.verifier()`, which passes no
getter -- so every test that drives the real factory stops at the build stage,
and the middle of that class has never run under a test.

Nothing here repeats it. The runner, the interpreter and the probe path are
all constructor arguments whose default is `None`, resolved from this module's
namespace at call time, so a test can substitute any of them.
`tests/test_tui_verify.py` asserts that structurally rather than by inspection:
no default in this file is callable.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from protopilot.runner import Runner, SubprocessRunner
from protopilot.verify import VerifyResult

#: The boot probe, run as a subprocess against the generated tree.
#:
#: A file rather than a `-c` string: a traceback out of model-authored code is
#: the most valuable thing this stage produces, and one whose frames point at
#: `<string>` is worth much less.
PROBE = Path(__file__).resolve().parent / "tui_probe.py"

#: In the order they can fail. The stage name is what the repair pass is told,
#: and a repair prompt for "the modules do not import" is a different prompt
#: from one for "the app renders an empty screen".
STAGES = ("import", "boot", "tests", "paint")


class TuiVerifier:
    """Everything that touches the generated tree, behind an injected Runner."""

    def __init__(
        self,
        project_dir: Path,
        runner: Runner | None = None,
        python: str | None = None,
        probe: Path | None = None,
        db_dir: Path | None = None,
        import_timeout: float = 120.0,
        boot_timeout: float = 180.0,
        test_timeout: float = 300.0,
    ) -> None:
        self.project_dir = Path(project_dir)
        # Resolved here rather than in the signature. See the module docstring:
        # a callable frozen as a default argument is a seam that looks open and
        # is welded shut.
        self.runner = runner or SubprocessRunner()
        self.python = python or sys.executable
        self.probe = Path(probe) if probe else PROBE
        self.db_dir = Path(db_dir) if db_dir else self.project_dir / ".dbs"
        self.import_timeout = import_timeout
        self.boot_timeout = boot_timeout
        self.test_timeout = test_timeout
        self.last_probe: dict = {}

    # -- the environment a generated tree runs in ----------------------

    def env(self) -> dict:
        """A fresh database, and the tree on the path.

        `PYTHONPATH` rather than an install: the tree is not a package and never
        will be. `APP_DB` is new on every call because there are no migrations
        here -- a reused file would verify a repaired model against the schema
        it had before the repair, which is exactly what `docker compose down -v`
        buys the web target.
        """
        self.db_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.project_dir)
        env["APP_DB"] = str(self.db_dir / f"{uuid.uuid4().hex}.sqlite3")
        # No `__pycache__` written into a tree somebody is about to read.
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Textual reads both. Without them it can decide the terminal is
        # interactive and behave differently under a captured pipe than it does
        # under a person, which would make this stage measure the pipe.
        env["TERM"] = "xterm-256color"
        env["NO_COLOR"] = "1"
        return env

    def run(self, argv: list, timeout: float):
        """One command in the tree, with that environment around it.

        `env=` is not on the `Runner` protocol, so this sets the process
        environment around the call and puts it back in a `finally`. A leaked
        `APP_DB` would point the NEXT run at a database that already has rows
        in it, and the seed guard would then make an unseeded app look green.
        """
        before = dict(os.environ)
        os.environ.update(self.env())
        try:
            return self.runner.run(argv, cwd=self.project_dir, timeout=timeout)
        finally:
            os.environ.clear()
            os.environ.update(before)

    # -- the stages ----------------------------------------------------

    def check_import(self):
        return self.run([self.python, "-c", "import app.main"], self.import_timeout)

    def boot(self) -> dict:
        """Start the app under `App.run_test` and read back what it painted."""
        result = self.run([self.python, str(self.probe)], self.boot_timeout)
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError, ValueError):
            # The probe reports its own failures as JSON, so a payload that
            # will not parse means the process died before it could -- a
            # segfault, a timeout, a module-level `sys.exit()`. Report the
            # whole command rather than the parse error, which is about us.
            payload = {"ok": False, "painted": False, "traceback": result.describe()}
        payload["stderr"] = result.stderr[-4000:]
        self.last_probe = payload
        return payload

    def run_tests(self):
        return self.run([self.python, "-m", "pytest", "-q", "tests/"], self.test_timeout)

    def verify(self) -> VerifyResult:
        loaded = self.check_import()
        if not loaded.ok:
            return VerifyResult(False, "import", "the generated modules do not import", loaded.describe())

        probe = self.boot()
        if not probe.get("ok"):
            return VerifyResult(
                False,
                "boot",
                "the app raised while starting under App.run_test",
                probe.get("traceback", ""),
                probe.get("stderr", ""),
            )

        tests = self.run_tests()
        if not tests.ok:
            return VerifyResult(False, "tests", "the smoke tests failed", tests.describe(), probe.get("stderr", ""))

        # Last, for the same reason the browser stage is last on the web side:
        # it is the only check that can see what was actually drawn. Up to here
        # an app that mounts and answers every query but paints an empty screen
        # is indistinguishable from one that works.
        if not probe.get("painted"):
            return VerifyResult(
                False,
                "paint",
                "the app started and rendered an empty screen buffer",
                buffer_report(probe),
                probe.get("stderr", ""),
            )

        return VerifyResult(
            True,
            "tests",
            f"green -- {probe.get('screen', '?')} painted {probe.get('widgets', 0)} widget(s)",
            tests.output,
        )


def buffer_report(probe: dict) -> str:
    """What the repair pass is shown when a screen came up empty.

    Both buffers, side by side, because "it rendered nothing" is not actionable
    and "here is what it rendered, and here is what an empty application
    renders" is. This is the terminal target's replacement for a log tail, and
    it is strictly more legible: the model is shown the screen.
    """
    return (
        f"screen: {probe.get('screen')}  widgets: {probe.get('widgets')}  "
        f"stack depth: {probe.get('depth')}\n"
        "--- rendered buffer ---\n"
        f"{probe.get('buffer', '')}\n"
        "--- an empty application renders ---\n"
        f"{probe.get('empty_buffer', '')}"
    )
