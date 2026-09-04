"""Boot the app, wait for it, run its smoke tests, capture the logs.

This is the part of proto-pilot that decides whether a tree gets handed back.
Generation is the easy half; "workable running app" is this file.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from protopilot.runner import CommandResult, Runner

# Stages, in the order they can fail. The stage name is what the repair pass
# is told, and a repair prompt for "the image would not build" is a different
# prompt from one for "the create test asserted 2 == 1".
STAGES = ("build", "health", "tests")


class Verifies(Protocol):
    """What `drive_to_green` actually needs: something that returns a verdict.

    The concrete `Verifier` needs Docker; the repair loop does not care. Naming
    the capability rather than the class is what lets the test suite drive the
    loop with a scripted sequence of results -- which is the only way the repair
    loop gets covered at all, since exercising it for real means a red container.
    """

    def verify(self) -> "VerifyResult": ...


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    stage: str
    summary: str
    output: str = ""
    logs: str = ""

    def report(self) -> str:
        parts = [f"[{self.stage}] {self.summary}"]
        if self.output.strip():
            parts.append("--- command output ---\n" + self.output.strip())
        if self.logs.strip():
            parts.append("--- container logs ---\n" + self.logs.strip())
        return "\n\n".join(parts)


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 -- connection refused while booting
        return 0, str(exc)


class Verifier:
    """All docker interaction lives here, behind an injected Runner."""

    def __init__(
        self,
        project_dir: Path,
        port: int,
        runner: Runner,
        getter: Callable[[str, float], tuple[int, str]] | None = None,
        sleep: Callable[[float], None] | None = None,
        health_timeout: float = 180.0,
        build_timeout: float = 900.0,
        screens: list[str] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir)
        self.port = port
        # Concrete paths, not spec patterns: "/games/{row_id}" cannot be
        # fetched. The caller substitutes a real row id or drops it.
        self.screens = screens or []
        self.runner = runner
        # Resolved here, not in the signature. A default argument is evaluated
        # once at `def` time, so `getter=http_get` welded this seam shut: a
        # verifier built through `targets.web.verifier()` -- which passes no
        # getter -- could not be reached by monkeypatching `verify.http_get`,
        # and every test driving the real factory therefore stopped at the
        # build stage with the middle of this class never having run. Same
        # behaviour, resolved late, so the seam is one.
        self.getter = getter or http_get
        self.sleep = sleep or time.sleep
        self.health_timeout = health_timeout
        self.build_timeout = build_timeout

    def compose(self, *args: str, timeout: float | None = None) -> CommandResult:
        return self.runner.run(["docker", "compose", *args], cwd=self.project_dir, timeout=timeout)

    def down(self) -> CommandResult:
        return self.compose("down", "-v", "--remove-orphans", timeout=180)

    def up(self) -> CommandResult:
        # `down -v` first, every time. The schema is created by
        # `create_all()`, which cannot alter an existing table -- so a repair
        # that changed a model would otherwise be verified against the old
        # schema and fail for a reason that has already been fixed.
        self.down()
        return self.compose("up", "-d", "--build", timeout=self.build_timeout)

    def logs(self, tail: int = 200) -> str:
        result = self.compose("logs", "--no-color", f"--tail={tail}", timeout=60)
        return result.output

    def wait_healthy(self) -> tuple[bool, str]:
        url = f"http://localhost:{self.port}/healthz"
        deadline = time.monotonic() + self.health_timeout
        last = "no attempt made"
        while True:
            status, body = self.getter(url, 3.0)
            if status == 200:
                try:
                    if json.loads(body).get("ok") is True:
                        return True, body
                except json.JSONDecodeError:
                    pass
            last = f"HTTP {status}: {body[:400]}"
            if time.monotonic() >= deadline:
                return False, last
            self.sleep(2.0)

    def run_tests(self) -> CommandResult:
        # -T: no TTY. Without it this hangs forever in CI and in any
        # non-interactive shell, which is every shell proto-pilot runs in.
        return self.compose("exec", "-T", "app", "pytest", "-q", timeout=300)

    def verify(self) -> VerifyResult:
        built = self.up()
        if not built.ok:
            return VerifyResult(
                False,
                "build",
                "docker compose could not build or start the stack",
                built.describe(),
            )

        healthy, detail = self.wait_healthy()
        if not healthy:
            return VerifyResult(
                False,
                "health",
                f"/healthz never came up on port {self.port} within " f"{self.health_timeout:.0f}s",
                detail,
                self.logs(),
            )

        tests = self.run_tests()
        if not tests.ok:
            return VerifyResult(False, "tests", "the smoke tests failed", tests.describe(), self.logs())

        # Last, because it is the only stage that can see the browser. The
        # suite above runs through an in-process TestClient and never executes
        # a script tag, so up to this point a page that throws on load or
        # paints nothing is indistinguishable from one that works.
        page_result = self.check_pages()
        if page_result is not None and not page_result.ok:
            return VerifyResult(
                False,
                "browser",
                "a screen failed in the browser",
                page_result.report(),
                self.logs(),
            )

        return VerifyResult(
            True,
            "tests",
            f"green -- app is up on http://localhost:{self.port}",
            tests.output,
        )

    def check_pages(self):
        """Load every screen in a real browser. None when not configured.

        Returning None rather than a pass keeps the distinction honest: a
        machine without the browser has not verified the browser, and the
        caller says so rather than reporting a green it did not earn.
        """
        if not self.screens:
            return None
        from protopilot import browser

        if browser.available():
            return None
        return browser.check(f"http://localhost:{self.port}", self.screens)
