"""Subprocess execution, behind an interface.

The `claude-code` backend runs the `claude` CLI through a `Runner`. That is
what lets a test hand it a scripted result instead of a real subprocess.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr.strip() else "")).strip()

    def describe(self) -> str:
        return f"$ {' '.join(self.argv)}\n{self.output}"


class Runner(Protocol):
    def run(self, argv: list[str], cwd: Path | None = None, timeout: float | None = None) -> CommandResult: ...


class SubprocessRunner:
    def run(self, argv: list[str], cwd: Path | None = None, timeout: float | None = None) -> CommandResult:
        try:
            proc = subprocess.run(  # noqa: S603 -- argv is built by us, never by the model
                argv,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return CommandResult(argv, 127, "", f"{argv[0]}: not found")
        except subprocess.TimeoutExpired as exc:
            # A timeout is a result, not an exception: the caller reports the
            # partial output with it.
            return CommandResult(
                argv,
                124,
                _text(exc.stdout),
                _text(exc.stderr) + f"\n[timed out after {timeout}s]",
            )
        return CommandResult(argv, proc.returncode, proc.stdout, proc.stderr)


def _text(value: object) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
