"""The research call: the web only, stream-json, and refused when the session held more.

The argv pins are the mechanism, as `test_llm_isolation.py` says of `ISOLATION`. The init
check is the evidence, read from each live stream: a session that held a tool beyond the
web, or any MCP server, has its answer thrown away.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from research_script import transcript

from protopilot.llm import (
    ISOLATION,
    RESEARCH_ISOLATION,
    ClaudeCodeLLM,
    ClaudeLLM,
    LLMError,
    ResearchFailed,
    ResearchUnavailable,
    research_result,
)
from protopilot.runner import CommandResult

pytestmark = [pytest.mark.unit]


class _Capturing:
    def __init__(self, stdout: str, code: int = 0) -> None:
        self.stdout, self.code = stdout, code
        self.argv: list[str] = []
        self.cwd: Path | None = None
        self.cwd_held: list[str] = []

    def run(self, argv, cwd=None, timeout=None):  # noqa: ANN001, ANN201
        self.argv, self.cwd = list(argv), cwd
        self.cwd_held = sorted(p.name for p in Path(cwd).iterdir()) if cwd else []
        return CommandResult(list(argv), self.code, self.stdout, "")


def researched(stdout: str | None = None) -> _Capturing:
    runner = _Capturing(transcript() if stdout is None else stdout)
    ClaudeCodeLLM(runner=runner, binary="claude").research(system="s", user="u", schema={"type": "object"}, label="r")
    return runner


def test_the_research_call_holds_the_web_and_nothing_else():
    argv = researched().argv
    assert argv[argv.index("--tools") + 1] == "WebSearch,WebFetch"
    assert argv[argv.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert "--strict-mcp-config" in argv
    assert json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}}
    window = len(RESEARCH_ISOLATION)
    assert any(tuple(argv[i : i + window]) == RESEARCH_ISOLATION for i in range(len(argv) - window + 1))


def test_the_research_call_streams_so_every_fetch_is_on_the_record():
    argv = researched().argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv and "--json-schema" in argv


def test_the_research_call_runs_in_an_empty_directory():
    runner = researched()
    assert runner.cwd is not None and runner.cwd_held == []
    assert not Path(runner.cwd).exists(), "the directory outlives the call"


def test_structured_still_holds_no_tool():
    runner = _Capturing(json.dumps({"subtype": "success", "structured_output": {}}))
    ClaudeCodeLLM(runner=runner, binary="claude").structured(system="s", user="u", schema={}, label="p")
    assert tuple(runner.argv[-len(ISOLATION) :]) == ISOLATION
    assert "WebFetch" not in " ".join(runner.argv)


def test_the_answer_is_the_streams_structured_output():
    assert research_result(transcript(), "r")["findings"][0]["kind"] == "cited"


@pytest.mark.parametrize(
    "said",
    [
        transcript(tools=["StructuredOutput", "WebFetch", "WebSearch", "Bash"]),
        transcript(mcp=[{"name": "drive", "status": "connected"}]),
    ],
    ids=["a-shell", "an-mcp-server"],
)
def test_a_session_that_held_more_than_the_web_is_thrown_away(said: str):
    with pytest.raises(LLMError, match="held"):
        researched(said)


@pytest.mark.parametrize(
    "said",
    [
        "",
        "not json\n",
        transcript(result={"type": "result", "subtype": "error_max_turns", "is_error": True}),
        transcript(result={"type": "result", "subtype": "success", "is_error": False}),
        transcript().replace('"subtype": "init"', '"subtype": "other"'),
    ],
    ids=["empty", "not-json", "an-error", "no-structured-output", "no-init"],
)
def test_a_stream_that_is_not_a_good_answer_is_an_llm_error(said: str):
    with pytest.raises(LLMError):
        researched(said)


def test_a_failed_process_is_an_llm_error():
    runner = _Capturing("", code=1)
    with pytest.raises(LLMError, match="failed"):
        ClaudeCodeLLM(runner=runner, binary="claude").research(system="s", user="u", schema={}, label="r")


@pytest.mark.parametrize(
    ("said", "retry"),
    [(transcript(result={"type": "result", "subtype": "error_max_turns", "is_error": True}), True)]
    + [(transcript(tools=["StructuredOutput", "WebFetch", "WebSearch", "Bash"]), False)],
    ids=["a-slip", "a-breach"],
)
def test_a_refused_stream_comes_back_whole_and_only_a_slip_is_worth_asking_again(said: str, retry: bool):
    with pytest.raises(ResearchFailed) as raised:
        researched(said)
    assert raised.value.transcript == said and raised.value.retry is retry


def test_the_api_backend_refuses_research_with_what_to_do_instead():
    llm = ClaudeLLM(client=object())
    with pytest.raises(ResearchUnavailable, match="--backend claude-code, or --no-research"):
        llm.research(system="s", user="u", schema={}, label="r")
    assert llm.research_refusal and not ClaudeCodeLLM(runner=_Capturing("")).research_refusal
