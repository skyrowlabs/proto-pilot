"""The credential check.

`doctor` exists to say why proto-pilot will not work here, so the one thing it
must never do is report ready on a machine that cannot reach the API. The SDK
defers credential resolution to the first request, so constructing a client
proves nothing -- these tests pin the check to an actual call.
"""

from __future__ import annotations

import pytest

from protopilot.llm import ClaudeLLM, _without_patterns


class FakeMessages:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return object()


class FakeClient:
    def __init__(self, error: Exception | None = None):
        self.messages = FakeMessages(error)


def test_check_actually_generates_against_the_configured_model():
    client = FakeClient()
    ClaudeLLM(model="claude-opus-5", client=client).check()
    assert client.messages.calls[0]["model"] == "claude-opus-5"
    # Cheap on purpose: doctor runs this every time.
    assert client.messages.calls[0]["max_tokens"] <= 16


def test_check_raises_when_credentials_do_not_resolve():
    # The shape the SDK raises with no key, no token and no profile on disk.
    client = FakeClient(TypeError("Could not resolve authentication method."))
    with pytest.raises(TypeError):
        ClaudeLLM(client=client).check()


# --- the subscription backend -------------------------------------------------
#
# A Claude plan buys no API credit, so this backend is the difference between
# "proto-pilot works for you" and "proto-pilot works for you once you top up".
# It is a subprocess, which means the envelope parsing is the part that breaks.

import json

from fakes import FakeRunner

from protopilot.llm import ClaudeCodeLLM, LLMError, build_llm

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit

SCHEMA = {"type": "object", "properties": {"name": {"type": "string"}}}


def envelope(**over) -> str:
    base = {
        "is_error": False,
        "subtype": "success",
        "stop_reason": "tool_use",
        "result": '{"name": "PackRat"}',
        "structured_output": {"name": "PackRat"},
    }
    base.update(over)
    return json.dumps(base)


def run_with(stdout: str, code: int = 0) -> ClaudeCodeLLM:
    runner = FakeRunner([(["claude"], (code, stdout, ""))])
    return ClaudeCodeLLM(runner=runner)


def test_returns_the_validated_structured_output():
    llm = run_with(envelope())
    assert llm.structured(system="s", user="u", schema=SCHEMA, label="schema") == {"name": "PackRat"}


def test_passes_the_schema_and_model_to_the_cli():
    runner = FakeRunner([(["claude"], (0, envelope(), ""))])
    ClaudeCodeLLM(runner=runner, model="claude-opus-5").structured(
        system="BRIEF", user="ASK", schema=SCHEMA, label="schema"
    )
    argv = runner.calls[0]
    assert "--json-schema" in argv and json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    assert argv[argv.index("--model") + 1] == "claude-opus-5"
    # Claude Code owns its system prompt, so ours has to ride in the user turn.
    prompt = argv[argv.index("--print") + 1]
    assert "BRIEF" in prompt and "ASK" in prompt


def test_missing_structured_output_is_an_llm_error_not_a_none():
    llm = run_with(envelope(structured_output=None, stop_reason="max_tokens"))
    with pytest.raises(LLMError, match="no structured output"):
        llm.structured(system="s", user="u", schema=SCHEMA, label="ui")


def test_cli_failure_surfaces_as_llm_error():
    llm = run_with("", code=1)
    with pytest.raises(LLMError):
        llm.structured(system="s", user="u", schema=SCHEMA, label="ui")


def test_non_json_output_surfaces_as_llm_error():
    llm = run_with("not json at all")
    with pytest.raises(LLMError, match="non-JSON"):
        llm.structured(system="s", user="u", schema=SCHEMA, label="ui")


def test_error_envelope_surfaces_as_llm_error():
    llm = run_with(envelope(is_error=True, subtype="error_during_execution", result="boom"))
    with pytest.raises(LLMError, match="boom"):
        llm.structured(system="s", user="u", schema=SCHEMA, label="ui")


def test_offline_beats_every_other_signal():
    # `--offline` must never be overridden by an env var that says otherwise;
    # the flag is how you promise a run will make no API calls.
    import os

    os.environ["PROTOPILOT_LLM"] = "claude-code"
    try:
        assert build_llm(offline=True).offline is True
    finally:
        del os.environ["PROTOPILOT_LLM"]


def test_unknown_backend_is_refused():
    with pytest.raises(LLMError, match="unknown backend"):
        build_llm(backend="gpt")


# --- a schema keyword only one backend takes ----------------------------------

PATTERNED = {
    "type": "object",
    "properties": {"a": {"type": "array", "items": {"type": "string", "pattern": "^x$"}}},
}


def test_the_api_backend_asks_in_words_for_what_the_sdk_says_it_cannot_enforce():
    assert _without_patterns(PATTERNED)["properties"]["a"]["items"] == {
        "type": "string",
        "description": "Must match the regular expression ^x$",
    }


def test_a_schema_with_no_pattern_reaches_the_api_unchanged():
    assert _without_patterns(SCHEMA) == SCHEMA


def test_a_field_named_pattern_is_a_field_and_not_a_keyword():
    named = {"type": "object", "properties": {"pattern": {"type": "string"}}}
    assert _without_patterns(named)["properties"] != {}


def test_the_cli_backend_keeps_the_pattern_because_it_enforces_it():
    runner = FakeRunner([(["claude"], (0, envelope(), ""))])
    ClaudeCodeLLM(runner=runner).structured(system="s", user="u", schema=PATTERNED, label="x")
    argv = runner.calls[0]
    assert json.loads(argv[argv.index("--json-schema") + 1]) == PATTERNED
