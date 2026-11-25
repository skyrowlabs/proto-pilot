"""The Claude API layer.

One method, `structured()`: a system prompt, a user prompt, a JSON Schema, and
a validated dict back. Every pass in this tool is that shape, so the retry,
caching, and refusal handling live here once.

`research()` is the one exception: the plan's research pass, the only call that
holds tools, and only on the CLI backend. The api backend refuses it.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# Streaming, and a large ceiling: a pass can return a lot of tokens, and a
# non-streaming request at this size trips the SDK's HTTP
# timeout rather than returning a partial answer.
MAX_TOKENS = 64000


class LLMError(RuntimeError):
    pass


class Refused(LLMError):
    """Claude declined the request. Carries the category so the CLI can say why."""

    def __init__(self, category: str | None, explanation: str | None) -> None:
        super().__init__(f"request refused ({category or 'unspecified'}): {explanation or ''}")
        self.category = category
        self.explanation = explanation


class ResearchUnavailable(LLMError):
    """This backend cannot make a research call; the message says what to use instead."""


class Breach(LLMError):
    """A research session that held more than the web, or did not say what it held. Never worth asking again."""


class ResearchFailed(LLMError):
    """A research call whose answer was not used, with the stream it came in.

    The stream is kept apart from accepted transcripts and never read as evidence. `retry`
    is False when asking again would repeat the same outcome: a breach, or a timeout.
    """

    def __init__(self, message: str, transcript: str, retry: bool, kept: str = "") -> None:
        super().__init__(message)
        self.transcript, self.retry, self.kept = transcript, retry, kept


@dataclass(frozen=True)
class Researched:
    """A research call's validated object, and the raw stream-json it came in: the evidence."""

    data: dict
    transcript: str


class LLM(Protocol):
    offline: bool

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict: ...


class Researcher(LLM, Protocol):
    """A backend that can also make the one tool-using call, `research`. Only the CLI backend can."""

    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched: ...


class OfflineLLM:
    """No API calls. Passes fall back to their deterministic baseline.

    This is not a mock -- it is a real, if unimaginative, generator, and it is
    what proto-pilot's own test suite runs against. A pipeline that can only be
    exercised with a network call and a credit card is a pipeline that stops
    being tested.
    """

    offline = True

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        raise NotImplementedError(f"pass {label!r} has no offline baseline")


#: Keywords whose values are data, not schemas: a "pattern" inside one is somebody's value.
SCHEMA_DATA = ("const", "enum", "default", "examples")


def _without_patterns(schema: Any) -> Any:
    """`schema` with each `pattern` moved into a description.

    The SDK's own `transform_schema` treats `pattern` as a keyword the Messages API does
    not take, and a schema it refuses would cost the whole pass. So this backend asks in
    words, and the caller's own check is what holds. The CLI backend enforces it.
    """
    if isinstance(schema, list):
        return [_without_patterns(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    kept = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            kept[key] = {name: _without_patterns(rule) for name, rule in value.items()}
        else:
            kept[key] = value if key in SCHEMA_DATA else _without_patterns(value)
    if isinstance(schema.get("pattern"), str):
        asked = f"Must match the regular expression {kept.pop('pattern')}"
        kept["description"] = f"{schema['description']} {asked}" if schema.get("description") else asked
    return kept


_API_RESEARCH_WHY = (
    "Research runs only on the claude-code backend so far: the api backend's web search has never been run here."
)
API_RESEARCH = f"{_API_RESEARCH_WHY} Pass --backend claude-code, or --no-research for a plan stamped Not researched."
#: Said by `proto research`, which has no `--no-research` to offer.
API_RESEARCH_ONE = f"{_API_RESEARCH_WHY} Pass --backend claude-code."


class ClaudeLLM:
    offline = False
    #: Read before any call, so a plan is refused rather than billed and then stamped.
    research_refusal = API_RESEARCH

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.environ.get("PROTOPILOT_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("PROTOPILOT_EFFORT", DEFAULT_EFFORT)
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise LLMError("the `anthropic` package is not installed; `pip install anthropic`") from exc
            # Zero-arg: resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
            # `ant auth login` profile. An unset env var does not mean no
            # credentials.
            self._client = anthropic.Anthropic()

    def check(self) -> None:
        """Prove a run would actually work, not merely authenticate.

        Three things can be separately wrong and only the third is obvious:
        constructing `Anthropic()` resolves nothing (the SDK defers credential
        lookup to the first request, so a bare constructor succeeds with no
        key at all); `models.retrieve` proves the credential but not the
        balance; and a zero balance fails only once a real run is
        already three passes deep. So this asks for one token. It costs a
        fraction of a cent, and it is the only check that fails in the same
        place a run would.
        """
        try:
            self._client.messages.create(
                model=self.model,
                max_tokens=16,
                thinking={"type": "disabled"},
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": "ok"}],
            )
        except _api_errors() as exc:
            raise LLMError(_api_message(exc)) from exc

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        try:
            return self._structured(system=system, user=user, schema=schema, label=label)
        except _api_errors() as exc:
            # The CLI prints an LLMError without a traceback. Running out of
            # credit, hitting a rate limit or losing the connection mid-pass
            # are ordinary outcomes of talking to an API, and they should read
            # like one rather than like proto-pilot itself crashing.
            raise LLMError(f"pass {label!r} failed: {_api_message(exc)}") from exc

    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched:
        """Refused, not attempted: untested web-search code would be a claim nobody checked."""
        raise ResearchUnavailable(API_RESEARCH)

    def _structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        with self._client.beta.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            # Adaptive thinking: `budget_tokens` is rejected on this model
            # family, and disabling thinking on Opus 5 costs more in
            # malformed tool calls than it saves.
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": _without_patterns(schema)},
            },
            # Server-side fallback: a safety refusal on one pass would
            # otherwise abort a run that is most of the way done.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[
                {
                    "type": "text",
                    "text": system,
                    # The system prompt is identical across the repair loop's
                    # attempts; caching it is most of the win on a retry.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            raise Refused(getattr(details, "category", None), getattr(details, "explanation", None))

        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise LLMError(f"pass {label!r} returned no text block")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"pass {label!r} returned invalid JSON: {exc}") from exc


#: The flags that make this backend a *generator* rather than an agent.
#:
#: `claude --print` runs with its full tool set by default -- Read, Write, Bash,
#: and the caller's working directory. So `files.py`'s guarantee, which README
#: and AGENTS.md both state flatly ("the model can only write five paths",
#: "model output is data, not authority"), was true of the `api` backend and
#: false of this one: the guard authorises what the returned JSON may write and
#: has no authority over the subprocess that returned it. Verified 2026-09-03 by
#: asking `claude --print` to overwrite a file in the cwd, which it did, with
#: `permission_denials: []`.
#:
#: Three flags rather than one, and the third is the one that is easy to miss.
#: `--tools ""` is an allow list of nothing, which beats `--disallowed-tools`
#: (a deny list has to name every tool, and missing one is silent). But it
#: governs only the **built-in** registry: MCP servers survive it, and with
#: `--tools ""` alone the model reported it still had the operator's Google
#: Drive, Slack and Cloudflare connections. An allow list is exhaustive only
#: over the registry it governs, and a second registry is invisible to it.
#:
#: Checked by asking the model what it holds rather than by trusting the flags
#: -- `tests/test_llm_isolation.py` pins the argv, and the live check that
#: produced this list reported exactly one tool, `StructuredOutput`.
#:
#: A side effect worth knowing when reading token counts: dropping the tool
#: definitions takes the ambient system prompt from ~32k to ~3.6k cached
#: tokens, so this is also the cheaper configuration by a wide margin.
ISOLATION = (
    "--tools",
    "",
    "--strict-mcp-config",
    "--mcp-config",
    '{"mcpServers":{}}',
)


#: The research call's tools: the web, read only. Never a write, a shell or an MCP server.
RESEARCH_TOOLS = ("WebSearch", "WebFetch")
RESEARCH_ISOLATION = (
    "--tools",
    ",".join(RESEARCH_TOOLS),
    "--allowedTools",
    ",".join(RESEARCH_TOOLS),
    "--strict-mcp-config",
    "--mcp-config",
    '{"mcpServers":{}}',
)
#: All a research session may report holding; `StructuredOutput` is how `--json-schema` answers.
RESEARCH_HELD = frozenset({"StructuredOutput", *RESEARCH_TOOLS})


def stream_events(transcript: str) -> list[dict]:
    """One dict per line of `--output-format stream-json`; a line that is not JSON is an error."""
    events = []
    for number, line in enumerate(transcript.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LLMError(f"line {number} of the research stream is not JSON") from exc
        if isinstance(event, dict):
            events.append(event)
    return events


def _tool_uses(events: list[dict]) -> list[dict]:
    """Every `tool_use` block an assistant event holds, whatever its name."""
    blocks = []
    for event in events:
        content = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
        if isinstance(content, list):
            blocks += [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
    return blocks


def research_result(transcript: str, label: str) -> dict:
    """The structured object a research stream ends on, refused unless the session held only its tools.

    The tools are read from the stream's own `init` events and from every tool it used, so
    a flag that stopped working is caught on the run it stopped working on, not by a test.
    """
    events = stream_events(transcript)
    inits = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    if not inits:
        raise Breach(f"pass {label!r}: the research stream has no init event, so its tools are unknown")
    for init in inits:
        tools = init.get("tools")
        servers = init.get("mcp_servers")
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            raise Breach(f"pass {label!r}: an init event does not list its tools, so they are unknown")
        if not isinstance(servers, list):
            raise Breach(f"pass {label!r}: an init event does not list its MCP servers, so they are unknown")
        extra = sorted(set(tools) - RESEARCH_HELD)
        if extra or servers:
            held = ", ".join(extra) or "an MCP server"
            raise Breach(f"pass {label!r}: the research session held {held}, so its answer was not used")
    used = sorted({str(block.get("name")) for block in _tool_uses(events)} - RESEARCH_HELD)
    if used:
        raise LLMError(f"pass {label!r}: the research session used {', '.join(used)}, so its answer was not used")
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is None:
        raise LLMError(f"pass {label!r}: the research stream ended without a result")
    if result.get("is_error") or result.get("subtype") != "success":
        detail = result.get("result") or result.get("api_error_status") or result.get("subtype") or "unknown"
        raise LLMError(f"pass {label!r} failed: {detail}")
    data = result.get("structured_output")
    if not isinstance(data, dict):
        raise LLMError(f"pass {label!r}: no structured output (stop_reason {result.get('stop_reason')!r})")
    return data


class ClaudeCodeLLM:
    """Claude via the Claude Code CLI, billed to a subscription.

    The Messages API and a Claude subscription are separate products: a Pro or
    Max plan buys no API credit, and there is no flag that makes the SDK bill
    one. `claude -p --json-schema` is the supported way to get a
    schema-validated object out of Claude using the credentials a subscription
    holder already has, so it is the backend for people who have a plan but no
    credit -- and the reason this class exists rather than an apology in the
    README.

    The trade is real. Every invocation carries Claude Code's own system
    prompt and tool definitions (~26k tokens), which no cache prefix of ours
    can absorb. This backend is slower per pass and noisier in tokens; it is also the one that
    works when the balance is zero.
    """

    offline = False
    research_refusal = ""

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        runner: Any | None = None,
        binary: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model or os.environ.get("PROTOPILOT_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("PROTOPILOT_EFFORT", DEFAULT_EFFORT)
        self.binary = binary or os.environ.get("PROTOPILOT_CLAUDE_BIN", "claude")
        # Long on purpose: a timeout mid-run costs every pass before it.
        self.timeout = timeout or float(os.environ.get("PROTOPILOT_TIMEOUT", "2700"))
        if runner is None:
            from protopilot.runner import SubprocessRunner

            runner = SubprocessRunner()
        self._runner = runner

    def check(self) -> None:
        result = self._runner.run([self.binary, "--version"], timeout=30.0)
        if not result.ok:
            raise LLMError(f"{self.binary}: not usable ({result.output or 'no output'})")

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        # No `system` parameter on the CLI: Claude Code owns its system prompt.
        # Prepending it to the user turn keeps the passes' prompts unchanged,
        # which is what lets one set of prompts serve both backends.
        argv = [
            self.binary,
            "--print",
            f"{system}\n\n---\n\n{user}",
            "--model",
            self.model,
            "--json-schema",
            json.dumps(schema),
            "--output-format",
            "json",
            *ISOLATION,
        ]
        result = self._runner.run(argv, timeout=self.timeout)
        if not result.ok:
            raise LLMError(f"pass {label!r} failed: {result.output or 'no output'}")

        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise LLMError(f"pass {label!r}: {self.binary} returned non-JSON output") from exc

        if envelope.get("is_error") or envelope.get("subtype") != "success":
            detail = envelope.get("result") or envelope.get("api_error_status") or "unknown"
            raise LLMError(f"pass {label!r} failed: {detail}")

        # `structured_output` is the schema-validated object. `result` is the
        # same thing as a string; preferring the former means a pass never
        # parses what the CLI has already parsed.
        data = envelope.get("structured_output")
        if data is None:
            raise LLMError(f"pass {label!r}: no structured output " f"(stop_reason {envelope.get('stop_reason')!r})")
        return data

    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched:
        """One tool-using call: the web only, `stream-json` so every fetch is on the record.

        Run from an empty directory, so no project file reaches the session. `structured`
        and `ISOLATION` are untouched: this is the only call that holds a tool.
        """
        argv = [
            self.binary,
            "--print",
            f"{system}\n\n---\n\n{user}",
            "--model",
            self.model,
            "--json-schema",
            json.dumps(schema),
            "--output-format",
            "stream-json",
            "--verbose",
            *RESEARCH_ISOLATION,
        ]
        with tempfile.TemporaryDirectory(prefix="protopilot-research-") as empty:
            result = self._runner.run(argv, cwd=Path(empty), timeout=self.timeout)
        if not result.ok:
            message = f"pass {label!r} failed: {_stream_error(result.stdout, result.stderr)}"
            raise ResearchFailed(message, result.stdout, retry=result.returncode != TIMED_OUT)
        try:
            return Researched(research_result(result.stdout, label), result.stdout)
        except LLMError as exc:
            raise ResearchFailed(str(exc), result.stdout, retry=not isinstance(exc, Breach)) from exc


#: The return code `runner.SubprocessRunner` gives a call that ran out of time.
TIMED_OUT = 124


def _stream_error(stdout: str, stderr: str) -> str:
    """What a failed stream says went wrong: its result event's error, else stderr's tail, else stdout's."""
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            detail = event.get("result") or event.get("api_error_status") or event.get("subtype")
            if detail:
                return str(detail)[-500:]
    return (stderr.strip() or stdout.strip())[-500:] or "no output"


def _api_errors() -> tuple[type[BaseException], ...]:
    """The SDK's error base class, or nothing if the SDK is absent.

    Narrow on purpose: a bug in proto-pilot should still surface as a
    traceback, because the point of this wrapper is to distinguish the API
    failing from us failing.
    """
    try:
        import anthropic
    except ImportError:  # pragma: no cover - dependency guard
        return ()
    return (anthropic.APIError,)


def _api_message(exc: BaseException) -> str:
    """The human sentence out of an SDK error, not its JSON envelope."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    message = getattr(exc, "message", None)
    return str(message) if message else str(exc)


def build_llm(offline: bool = False, backend: str | None = None) -> LLM:
    """Pick a backend.

    Explicit argument first, then `PROTOPILOT_LLM`, then the API. The three
    are not interchangeable in cost or speed, so the choice is never inferred
    from whether credentials happen to resolve -- silently falling back to a
    subscription because the balance was zero would bill a plan the caller did
    not offer up.
    """
    choice = backend or os.environ.get("PROTOPILOT_LLM") or ("offline" if offline else "api")
    if offline:
        choice = "offline"
    if choice == "offline":
        return OfflineLLM()
    if choice in ("claude-code", "subscription"):
        return ClaudeCodeLLM()
    if choice == "api":
        return ClaudeLLM()
    raise LLMError(f"unknown backend {choice!r}; expected 'api', 'claude-code' or 'offline'")
