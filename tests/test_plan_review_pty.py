"""The outline review at a real terminal: nothing here patches `_stdin_is_terminal`."""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import require_or_skip
from plan_script import IDEA

from protopilot.cli import PLAN_REVIEW_PROMPT
from protopilot.plan.model import Plan

pytestmark = [pytest.mark.unit]

#: Generous, because an idle wait costs nothing: every read returns as soon as output lands.
DEADLINE_SECONDS = 60
CTRL_D = b"\x04"
WHY_PROMPT = "Why does it matter?"


class Terminal:
    """A process whose stdin, stdout and stderr are all one pty."""

    def __init__(self, *args: str):
        self.master, slave = pty.openpty()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "protopilot.cli", *args], stdin=slave, stdout=slave, stderr=slave, close_fds=True
        )
        os.close(slave)
        self.seen = ""
        self.cursor = 0

    def _read(self, wait: float) -> bool:
        """Take what is waiting; False once the child has closed its end."""
        if not select.select([self.master], [], [], wait)[0]:
            return True
        try:
            data = os.read(self.master, 65536)
        except OSError:  # Linux reports a closed slave as EIO
            return False
        self.seen += data.decode("utf-8", "replace").replace("\r\n", "\n")
        return bool(data)

    def expect(self, text: str) -> None:
        """Wait for `text` after the last thing matched, and move past it."""
        deadline = time.monotonic() + DEADLINE_SECONDS
        while (found := self.seen.find(text, self.cursor)) < 0:
            alive = self._read(max(0.0, min(1.0, deadline - time.monotonic())))
            if not alive or time.monotonic() > deadline:
                pytest.fail(f"never saw {text!r}; the terminal showed:\n{self.seen[self.cursor:]}")
        self.cursor = found + len(text)

    def send(self, line: str) -> None:
        os.write(self.master, line.encode() + b"\n")

    def press(self, key: bytes) -> None:
        os.write(self.master, key)

    def finish(self) -> int:
        """Drain to the end, so a full pty buffer cannot hold the child open, and reap it."""
        deadline = time.monotonic() + DEADLINE_SECONDS
        while self._read(0.2) and time.monotonic() < deadline:
            if self.proc.poll() is not None and not select.select([self.master], [], [], 0)[0]:
                break
        return self.proc.wait(timeout=DEADLINE_SECONDS)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        os.close(self.master)


def have_a_pty() -> bool:
    try:
        master, slave = pty.openpty()
    except OSError:
        return False
    os.close(master)
    os.close(slave)
    return True


@pytest.fixture
def terminal():
    require_or_skip(have_a_pty(), "this host cannot open a pseudo-terminal", requires="a pty")
    opened: list[Terminal] = []

    def start(*args: str) -> Terminal:
        opened.append(Terminal(*args))
        return opened[-1]

    yield start
    for each in opened:
        each.close()


def test_a_whole_review_at_a_terminal_edits_and_writes_the_plan(tmp_path, terminal):
    tree = tmp_path / "tree"
    term = terminal("plan", IDEA, "--offline", "--dir", str(tree))
    term.expect("Estimated model calls: 0")
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("drop 2")
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("rename 1 The people")
    term.expect("1. The people (audience)")
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("add Insurance")
    term.expect(WHY_PROMPT)
    term.send("It decides liability")
    term.expect("(insurance): It decides liability")
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("frobnicate")
    term.expect("not a review command: 'frobnicate'")
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("")
    term.expect("Start with PLAN.md.")
    assert term.finish() == 0
    plan = Plan.load(tree)
    assert [t.slug for t in plan.topics] == ["audience", "resources", "operations", "risks", "first_test", "insurance"]
    assert plan.topics[0].title == "The people"
    assert (tree / "topics" / "insurance.md").is_file() and not (tree / "topics" / "scope.md").exists()


def test_enter_at_a_terminal_writes_what_yes_writes(tmp_path, terminal):
    reviewed, accepted = tmp_path / "reviewed", tmp_path / "accepted"
    term = terminal("plan", IDEA, "--offline", "--dir", str(reviewed))
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("")
    assert term.finish() == 0
    assert terminal("plan", IDEA, "--offline", "--yes", "--dir", str(accepted)).finish() == 0

    def pages(tree: Path) -> dict[str, bytes]:
        return {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob("*") if p.is_file()}

    assert pages(reviewed) == pages(accepted)


def test_quit_at_a_terminal_writes_nothing(tmp_path, terminal):
    term = terminal("plan", IDEA, "--offline", "--dir", str(tmp_path / "tree"))
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("quit")
    term.expect("Aborted!")
    assert term.finish() == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("lines", [[], ["drop 1"]], ids=["untouched", "after-an-edit"])
def test_ctrl_d_at_the_review_aborts_and_writes_nothing(tmp_path, terminal, lines):
    term = terminal("plan", IDEA, "--offline", "--dir", str(tmp_path / "tree"))
    term.expect(PLAN_REVIEW_PROMPT)
    for line in lines:
        term.send(line)
        term.expect(PLAN_REVIEW_PROMPT)
    term.press(CTRL_D)
    term.expect("Aborted!")
    assert term.finish() == 1
    assert list(tmp_path.iterdir()) == []


def test_ctrl_d_inside_an_add_aborts_and_writes_nothing(tmp_path, terminal):
    term = terminal("plan", IDEA, "--offline", "--dir", str(tmp_path / "tree"))
    term.expect(PLAN_REVIEW_PROMPT)
    term.send("add Insurance")
    term.expect(WHY_PROMPT)
    term.press(CTRL_D)
    term.expect("Aborted!")
    assert term.finish() == 1
    assert list(tmp_path.iterdir()) == []
