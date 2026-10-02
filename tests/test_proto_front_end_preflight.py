"""`proto console` and `proto serve` fail before they take the terminal.

Both front ends spend minutes per generation and take the screen (or a port)
while doing it. A backend that cannot run is therefore worth finding out about
at the prompt, and the two ways of getting that wrong are opposite:

* discovering it **mid-generation**, three passes and several minutes in; or
* raising inside a running Textual app, where a `ClickException` is painted
  over by the next frame and gone when the screen tears down.

So the check happens in the command, before either front end starts.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from protopilot.cli import main

pytestmark = pytest.mark.unit

FRONT_ENDS = ["console", "serve"]


@pytest.fixture(autouse=True)
def no_launch(monkeypatch):
    """Stop each command at its launcher.

    Without this, a test that gets *past* the preflight goes on to do what the
    command is for: `serve` binds a port and blocks inside `uvicorn.run`, and
    `console` takes the terminal. The first run of this file hung for exactly
    that reason. A preflight test is about what happens **before** the front
    end starts, so the front end is the one thing it must not start.

    Both are patched at the attribute the command looks up at call time, not at
    the name it binds: `serve` does `import uvicorn` then `uvicorn.run(...)`,
    and `console` does `from protopilot.console import run` inside the
    function body.

    **Autouse, including on the tests that expect the preflight to stop the
    command.** Those do not need it when the code is right — and when it is
    wrong they are exactly the tests that run on past the missing check and
    launch the thing. Planting a removed preflight turned this file into a
    120-second hang rather than a failure, which is a worse signal than the
    bug: a red names the broken assertion, a hang names nothing. A test that
    can only report correctly while the code is correct is not much of a test.
    """
    import uvicorn

    import protopilot.console as console_pkg

    launched = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: launched.append("serve"))
    monkeypatch.setattr(console_pkg, "run", lambda *a, **k: launched.append("console"))
    return launched


@pytest.fixture()
def broken_claude(tmp_path, monkeypatch):
    """A `claude` binary that is not there. The check is a `--version` call, so
    a path that does not resolve is the cheapest true failure."""
    monkeypatch.setenv("PROTOPILOT_CLAUDE_BIN", str(tmp_path / "not-a-real-binary"))
    return tmp_path


@pytest.mark.parametrize("command", FRONT_ENDS)
def test_a_broken_subscription_binary_is_named_at_the_prompt(command, broken_claude):
    result = CliRunner().invoke(main, [command, "--backend", "claude-code"])
    assert result.exit_code != 0, result.output
    assert "PROTOPILOT_CLAUDE_BIN" in result.output, f"the message does not say what to set: {result.output}"


@pytest.mark.parametrize("command", FRONT_ENDS)
def test_the_env_var_is_preflighted_and_not_only_the_flag(command, broken_claude, monkeypatch):
    """`PROTOPILOT_LLM` is the ordinary way to pin a backend — an operator sets
    it once in their shell and never passes `--backend` again.

    `serve` checked only when the flag was passed explicitly, so the common
    case got no check at all and failed partway into a generation instead. The
    resolution now goes through `build_llm`, which owns the rule, rather than
    through a second copy of it in the command.
    """
    monkeypatch.setenv("PROTOPILOT_LLM", "claude-code")
    result = CliRunner().invoke(main, [command])
    assert result.exit_code != 0, f"no preflight ran for the env-var case: {result.output}"
    assert "PROTOPILOT_CLAUDE_BIN" in result.output, result.output


@pytest.mark.parametrize("command", FRONT_ENDS)
def test_the_offline_backend_is_never_preflighted(command, broken_claude, no_launch):
    """The baseline needs nothing, so asking it anything is a way to fail for
    no reason on a machine that has no `claude` at all — which is exactly the
    machine `--offline` exists for."""
    result = CliRunner().invoke(main, [command, "--backend", "offline", "--workspace", str(broken_claude)])
    assert "PROTOPILOT_CLAUDE_BIN" not in result.output, result.output
    # And it really did get through: without this, "the message is absent"
    # would also be satisfied by the command failing for some other reason
    # before the preflight ran at all.
    assert no_launch == [command], f"{command} did not reach its launcher: {result.output}"


@pytest.mark.parametrize("command", FRONT_ENDS)
def test_the_api_backend_is_not_charged_for_a_launch(command, monkeypatch, no_launch):
    """`ClaudeLLM.check()` deliberately spends a token, because a zero balance
    is invisible until a real request is made. That is the right trade for
    `proto doctor`, which is asked to find out, and the wrong one for every
    launch of a front end — so the preflight runs only the free check.

    Asserted by making the paid one explode if it is ever called.
    """
    from protopilot import llm as llm_mod

    charged = []

    def explode(self):
        charged.append(1)
        raise AssertionError("the launch preflight made a billable call")

    monkeypatch.setattr(llm_mod.ClaudeLLM, "check", explode)
    result = CliRunner().invoke(main, [command, "--backend", "api"])
    assert not charged, "a front-end launch billed the API to check it could"
    assert no_launch == [command], f"{command} never reached its launcher: {result.output}"
