"""The Claude API layer.

One method, `structured()`: a system prompt, a user prompt, a JSON Schema, and
a validated dict back. Every pass in this tool is that shape, so the retry,
caching, and refusal handling live here once.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# Streaming, and a large ceiling: a routes pass for a five-entity app is a lot
# of tokens, and a non-streaming request at this size trips the SDK's HTTP
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


class LLM(Protocol):
    offline: bool

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict: ...


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


class ClaudeLLM:
    offline = False

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
        """Prove a generation would actually run, not merely authenticate.

        Three things can be separately wrong and only the third is obvious:
        constructing `Anthropic()` resolves nothing (the SDK defers credential
        lookup to the first request, so a bare constructor succeeds with no
        key at all); `models.retrieve` proves the credential but not the
        balance; and a zero balance fails only once a real generation is
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
                "format": {"type": "json_schema", "schema": schema},
            },
            # Server-side fallback: a safety refusal on one pass would
            # otherwise abort a generation that is most of the way done.
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
    prompt and tool definitions (~26k tokens), so the STACK_BRIEF-as-cache-
    prefix design that makes `ClaudeLLM` cheap does not apply here. This
    backend is slower per pass and noisier in tokens; it is also the one that
    works when the balance is zero.
    """

    offline = False

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
        # SVG-heavy UI passes run long: 15 minutes was not enough for a
        # chess board's worth of drawn pieces, and a timeout mid-generation
        # costs every pass before it.
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
