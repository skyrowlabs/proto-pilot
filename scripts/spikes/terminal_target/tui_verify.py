"""Boot the terminal app, drive it, run its smoke tests, report a verdict.

The counterpart of `protopilot/verify.py`, and it returns that module's
`VerifyResult` rather than a type of its own -- so a web run and a terminal run
produce records of the same shape and the comparison is a diff rather than an
argument about fields.

The stage names differ because the stages differ, and the mapping is the
finding Phase 5 of `docs/TODO/terminal-target.md` predicts:

    web            terminal      what it catches
    build       -> import        the tree does not load at all
    health      -> boot          it loads but will not start
    tests       -> tests         it starts but does not do what was asked
    browser     -> paint         it does all of that and shows nothing

Attribution order is the web order exactly (import, boot, tests, paint), even
though `boot` and `paint` are measured in the same subprocess -- a run whose
failing stage depends on which target it is would make the two columns of the
comparison unaddable.

No Docker, no port, no health race, no `/healthz`. Each attempt gets a fresh
SQLite file, which is the whole of what `docker compose down -v` was for: a
repair that changes a model must not be verified against the old schema.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from protopilot.runner import Runner, SubprocessRunner
from protopilot.verify import VerifyResult

PROBE = Path(__file__).resolve().parent / "boot_probe.py"

STAGES = ("import", "boot", "tests", "paint")


class TuiVerifier:
    """Everything that touches the generated tree, behind an injected Runner."""

    def __init__(
        self,
        project_dir: Path,
        runner: Optional[Runner] = None,
        python: str = sys.executable,
        db_dir: Optional[Path] = None,
        import_timeout: float = 120.0,
        boot_timeout: float = 180.0,
        test_timeout: float = 300.0,
    ) -> None:
        self.project_dir = Path(project_dir)
        self.runner = runner or SubprocessRunner()
        self.python = python
        self.db_dir = Path(db_dir) if db_dir else self.project_dir / ".dbs"
        self.import_timeout = import_timeout
        self.boot_timeout = boot_timeout
        self.test_timeout = test_timeout
        self.last_probe: dict = {}

    # -- the environment a generated tree runs in ----------------------

    def _env(self) -> dict:
        """A fresh database, and the tree on the path.

        `PYTHONPATH` rather than an install: the tree is not a package and
        never will be. `APP_DB` is new every call because there are no
        migrations here either -- `create_all` cannot alter an existing table,
        so a reused file would verify a repaired model against the schema it
        had before the repair.
        """
        self.db_dir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.project_dir)
        env["APP_DB"] = str(self.db_dir / f"{uuid.uuid4().hex}.sqlite3")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Textual reads these; without them it can decide the terminal is
        # interactive and behave differently under a captured pipe than it
        # does under a person.
        env["TERM"] = "xterm-256color"
        env["NO_COLOR"] = "1"
        return env

    def _run(self, argv: list, timeout: float):
        # `env=` is not on the Runner protocol, so this reaches past it and
        # sets the process environment around the call. Restored in a finally:
        # a leaked APP_DB would point the NEXT run at a database that already
        # has rows in it, and the seed guard would then make it look green.
        before = dict(os.environ)
        os.environ.update(self._env())
        try:
            return self.runner.run(argv, cwd=self.project_dir, timeout=timeout)
        finally:
            os.environ.clear()
            os.environ.update(before)

    # -- the stages ----------------------------------------------------

    def check_import(self):
        return self._run([self.python, "-c", "import app.main"], self.import_timeout)

    def boot(self) -> dict:
        result = self._run([self.python, str(PROBE)], self.boot_timeout)
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError, ValueError):
            payload = {"ok": False, "painted": False, "traceback": result.describe()}
        payload["stderr"] = result.stderr[-4000:]
        self.last_probe = payload
        return payload

    def run_tests(self):
        return self._run([self.python, "-m", "pytest", "-q", "tests/"], self.test_timeout)

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
        # it is the only check that can see what was actually drawn. Up to
        # here, an app that mounts and answers every query but paints an empty
        # screen is indistinguishable from one that works.
        if not probe.get("painted"):
            return VerifyResult(
                False,
                "paint",
                "the app started and rendered an empty screen buffer",
                _buffer_report(probe),
                probe.get("stderr", ""),
            )

        return VerifyResult(
            True,
            "tests",
            f"green -- {probe.get('screen', '?')} painted {probe.get('widgets', 0)} widget(s)",
            tests.output,
        )


def _buffer_report(probe: dict) -> str:
    return (
        f"screen: {probe.get('screen')}  widgets: {probe.get('widgets')}\n"
        "--- rendered buffer ---\n"
        f"{probe.get('buffer', '')}\n"
        "--- an empty application renders ---\n"
        f"{probe.get('empty_buffer', '')}"
    )
