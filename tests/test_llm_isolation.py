"""The `claude-code` backend generates; it does not act.

`files.py` is the write guard, and README and AGENTS.md both state its
guarantee flatly: *the model can only write five paths*, *model output is data,
not authority*. That was true of the `api` backend and **false of this one**,
because `claude --print` runs with its full tool set -- Read, Write, Bash and
the caller's working directory. The guard authorises what the returned JSON may
write. It has no authority over the subprocess that returned it.

Verified live on 2026-09-03 before this file existed: a one-line prompt asking
`claude --print` to overwrite a file in the cwd overwrote it, and the envelope
came back with ``permission_denials: []``. Nothing refused; there was nothing
to refuse.

## Why this is a unit test over argv and not a live call

The honest check is to run the real binary and ask what tools it holds, which
is how ``ISOLATION`` was arrived at and how it was confirmed (exactly one tool,
``StructuredOutput``). That takes a subscription, a network and about ten
seconds, so it cannot be the thing standing between this hole and its
reintroduction. What *can* run on every commit is the argv: the flags are the
whole mechanism, and dropping one is the realistic regression.

So this pins the mechanism and the docstring above records the evidence. The
two together are the check -- neither is sufficient alone, and it is worth
being explicit that a green run here proves the flags are passed, not that the
flags still do what they did when somebody watched them work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot.llm import ISOLATION, ClaudeCodeLLM  # noqa: E402
from protopilot.runner import CommandResult  # noqa: E402

pytestmark = [pytest.mark.unit]


class _Capturing:
    """A `Runner` that records the argv and returns a valid envelope."""

    def __init__(self) -> None:
        self.argv: list[str] = []

    def run(self, argv, cwd=None, timeout=None):  # noqa: ANN001, ANN201
        self.argv = list(argv)
        envelope = {
            "is_error": False,
            "subtype": "success",
            "structured_output": {"ok": True},
        }
        return CommandResult(argv=list(argv), returncode=0, stdout=json.dumps(envelope), stderr="")


def _argv_for_one_call() -> list[str]:
    runner = _Capturing()
    llm = ClaudeCodeLLM(runner=runner, binary="claude")
    llm.structured(system="s", user="u", schema={"type": "object"}, label="probe")
    return runner.argv


def test_every_isolation_flag_reaches_the_subprocess() -> None:
    """Derived from `ISOLATION`, never a second copy of the list.

    Restating the flags here would make this test agree with a stale constant:
    delete a flag from `ISOLATION` and a hand-written expectation still passes
    against the value it was written for. Reading the tuple means the only way
    to lose a flag is to lose it from both, which is the edit somebody has to
    mean.
    """
    argv = _argv_for_one_call()
    for index, flag in enumerate(ISOLATION):
        assert flag in argv, f"{flag!r} (ISOLATION[{index}]) never reached the argv"


def test_the_isolation_flags_keep_their_pairing() -> None:
    """Presence is not enough: `--tools` and its empty value must stay adjacent.

    `--tools` with a missing value would consume the next flag as its argument,
    which is the failure that leaves the model holding a full tool set while
    every flag is still technically "in the argv".
    """
    argv = _argv_for_one_call()
    window = len(ISOLATION)
    starts = [i for i in range(len(argv) - window + 1) if tuple(argv[i : i + window]) == tuple(ISOLATION)]
    assert starts, f"ISOLATION appears out of order or split up:\n  {argv}"


def test_the_built_in_allow_list_is_empty_rather_than_a_deny_list() -> None:
    """`--tools ""` and not `--disallowed-tools`, and this is the reason.

    A deny list has to name every tool, and the first attempt at this missed
    two -- the model pointed them out itself, which is a deny list working by
    the model's goodwill rather than by the flag. An allow list of nothing has
    no such hole.
    """
    argv = _argv_for_one_call()
    assert "--disallowed-tools" not in argv, "a deny list cannot be exhaustive; use --tools with an empty value"
    assert argv[argv.index("--tools") + 1] == "", "--tools must allow nothing, not something"


def test_the_mcp_registry_is_isolated_too() -> None:
    """The half that `--tools` cannot reach.

    MCP servers are a separate registry and survive `--tools ""`. With that
    flag alone the model reported it still held the operator's Google Drive,
    Slack and Cloudflare connections -- so a generation pass could reach
    whatever the operator happens to have configured. Both flags are needed:
    `--strict-mcp-config` to ignore the ambient configuration, and an empty
    `--mcp-config` to be the only one it honours.
    """
    argv = _argv_for_one_call()
    assert "--strict-mcp-config" in argv, "without this, ambient MCP configuration is still loaded"
    supplied = json.loads(argv[argv.index("--mcp-config") + 1])
    assert supplied == {"mcpServers": {}}, f"the supplied MCP config must be empty, got {supplied!r}"


def test_isolation_does_not_disturb_the_schema_contract() -> None:
    """The flags must not cost the thing the backend exists for.

    Taking the tools away could plausibly have taken `--json-schema` with them,
    since structured output is itself delivered by a tool call. It does not --
    confirmed live, and pinned here so a future flag added to `ISOLATION` that
    *does* break it fails in the unit suite rather than in a pass.
    """
    argv = _argv_for_one_call()
    assert "--json-schema" in argv
    assert json.loads(argv[argv.index("--json-schema") + 1]) == {"type": "object"}
    assert argv[argv.index("--output-format") + 1] == "json"
