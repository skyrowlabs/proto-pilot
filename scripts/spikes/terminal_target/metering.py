"""What a generation cost, taken from the envelope the backend already returns.

`ClaudeCodeLLM.structured` reads exactly one key out of the `claude
--output-format json` envelope -- `structured_output` -- and drops the rest,
including `usage`, `total_cost_usd` and `duration_api_ms`. That is the right
call for the product (a pass has no use for a token count) and it is why token
figures cannot simply be read off the LLM object.

They are obtainable, and the seam already exists: `ClaudeCodeLLM` takes an
injected `runner`. A runner that keeps the envelope it just parsed hands the
numbers back without one line changing under `protopilot/`.

Measured on this machine, 2026-09-03, from a one-word prompt:

    {"usage": {"input_tokens": 2, "cache_creation_input_tokens": 16152,
               "cache_read_input_tokens": 15908, "output_tokens": 4},
     "total_cost_usd": 0.169, "duration_api_ms": 4631}

Two things that reads out of, both of which belong in the report rather than in
a footnote. The ~32k of cached input on a two-token prompt is Claude Code's own
system prompt and tool definitions, paid on every pass; and `total_cost_usd` is
an API-equivalent price for a call that was billed to a subscription, so it is
a comparable number, not a bill.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from protopilot.runner import CommandResult, SubprocessRunner

#: Envelope keys worth keeping. Named rather than kept whole because the
#: envelope also carries a session id and a permission-denial list, and a
#: measurement record that quietly accumulates whatever the CLI adds next is a
#: record nobody can diff against last week's.
ENVELOPE_KEYS = ("total_cost_usd", "duration_api_ms", "duration_ms", "num_turns", "stop_reason", "subtype")


class MeteredRunner(SubprocessRunner):
    """A `SubprocessRunner` that keeps the last JSON envelope it saw.

    Deliberately not a `Runner` for anything else: give the verifier its own
    plain runner. A shared instance would have `last_envelope` overwritten by
    whichever `docker compose` call happened to run in between.
    """

    def __init__(self) -> None:
        self.last_envelope: Optional[dict] = None

    def run(self, argv: List[str], cwd: Optional[Path] = None, timeout: Optional[float] = None) -> CommandResult:
        self.last_envelope = None
        result = super().run(argv, cwd=cwd, timeout=timeout)
        try:
            envelope = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return result
        if isinstance(envelope, dict) and "usage" in envelope:
            self.last_envelope = envelope
        return result


@dataclass
class Call:
    """One model call, and everything the run record needs to know about it."""

    label: str
    ok: bool
    seconds: float
    usage: Optional[dict] = None
    envelope: Optional[dict] = None
    error: str = ""
    prompt_chars: Optional[dict] = None

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "ok": self.ok,
            "seconds": round(self.seconds, 2),
            "prompt_chars": self.prompt_chars,
            "usage": self.usage,
            "envelope": self.envelope,
            "error": self.error,
        }


@dataclass
class MeteredLLM:
    """An `LLM` that records what every call cost, and delegates the rest.

    The `LLM` protocol is one method, so wrapping it is honest: the passes are
    handed something indistinguishable from the backend they would otherwise
    get, and the real `build.generate` / `build.drive_to_green` accept it
    without knowing. That is what lets the web half of this measurement use the
    actual pipeline rather than a re-implementation of it.
    """

    inner: Any
    runner: Optional[MeteredRunner] = None
    calls: List[Call] = field(default_factory=list)
    on_call: Optional[Any] = None

    @property
    def offline(self) -> bool:
        return bool(getattr(self.inner, "offline", False))

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        started = time.monotonic()
        try:
            data = self.inner.structured(system=system, user=user, schema=schema, label=label)
        except Exception as exc:
            self._record(label, False, time.monotonic() - started, str(exc), system, user)
            raise
        self._record(label, True, time.monotonic() - started, "", system, user)
        return data

    def _record(self, label: str, ok: bool, seconds: float, error: str, system: str, user: str) -> None:
        """Every call, including the repair loop's.

        Recording here rather than at the call sites is what makes the two
        halves symmetric: `build.drive_to_green` runs the web target's repair
        pass inside itself and never hands the prompts back, so a caller-side
        hook would have captured five passes on one target and six on the
        other -- and the repairs are the runs the whole measurement is about.
        """
        envelope = getattr(self.runner, "last_envelope", None) if self.runner else None
        usage = envelope.get("usage") if isinstance(envelope, dict) else None
        kept = {k: envelope.get(k) for k in ENVELOPE_KEYS} if isinstance(envelope, dict) else None
        call = Call(
            label=label,
            ok=ok,
            seconds=seconds,
            usage=usage,
            envelope=kept,
            error=error,
            prompt_chars={"system": len(system), "user": len(user)},
        )
        self.calls.append(call)
        if self.on_call is not None:
            self.on_call(call, system, user)

    # -- summaries -----------------------------------------------------

    def totals(self) -> Dict[str, Any]:
        """Everything added up, and an explicit statement when it cannot be.

        `usage_available: false` is the point of this method. A backend that
        does not surface token counts must produce a named absence rather than
        a zero, because a zero reads as "it was free".
        """
        metered = [c for c in self.calls if c.usage]
        totals: Dict[str, Any] = {
            "calls": len(self.calls),
            "seconds": round(sum(c.seconds for c in self.calls), 2),
            "usage_available": bool(metered),
        }
        if not metered:
            return totals
        for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            totals[key] = sum(int((c.usage or {}).get(key) or 0) for c in metered)
        costs = [float((c.envelope or {}).get("total_cost_usd") or 0.0) for c in self.calls]
        total_cost = sum(costs)
        totals["cost_usd_equivalent"] = round(total_cost, 4) if total_cost else None
        return totals
