"""`SubprocessRunner`: what the `claude-code` backend gets back from a real subprocess."""

from __future__ import annotations

import sys

import pytest

from protopilot.runner import CommandResult, SubprocessRunner

pytestmark = pytest.mark.unit


def python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_a_command_that_exits_zero_is_ok_and_keeps_both_streams():
    result = SubprocessRunner().run(python("import sys; print('out'); print('err', file=sys.stderr)"))
    assert (result.ok, result.returncode, result.stdout, result.stderr) == (True, 0, "out\n", "err\n")
    assert result.output == "out\n\nerr"


def test_a_nonzero_exit_is_a_result_with_its_code():
    result = SubprocessRunner().run(python("import sys; sys.exit(3)"))
    assert (result.ok, result.returncode, result.output) == (False, 3, "")


def test_a_binary_that_is_not_there_is_exit_127_and_says_which(tmp_path):
    missing = str(tmp_path / "no_such_claude")
    result = SubprocessRunner().run([missing, "--version"])
    assert (result.ok, result.returncode, result.stderr) == (False, 127, f"{missing}: not found")


def test_a_timeout_is_exit_124_with_the_output_so_far():
    code = "import sys, time; sys.stdout.write('partial'); sys.stdout.flush(); time.sleep(30)"
    result = SubprocessRunner().run(python(code), timeout=0.5)
    assert (result.ok, result.returncode, result.stdout) == (False, 124, "partial")
    assert result.stderr.endswith("[timed out after 0.5s]")


def test_the_command_runs_in_the_directory_it_is_given(tmp_path):
    result = SubprocessRunner().run(python("import os; print(os.getcwd())"), cwd=tmp_path)
    assert result.stdout.strip() == str(tmp_path.resolve())


def test_describe_shows_the_command_over_its_output_and_drops_blank_stderr():
    result = CommandResult(["claude", "-p", "hi"], 0, "answer\n", "  \n")
    assert result.describe() == "$ claude -p hi\nanswer"
