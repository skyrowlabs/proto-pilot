"""`proto doctor`: the SDK check and the two backend probes.

Both backends are stubbed at the boundary: `ClaudeLLM.check` spends a token on
a real request and `ClaudeCodeLLM.check` shells out to the `claude` binary. The
factories are replaced by name, which doubles as the assertion that `doctor`
still asks through those names.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from protopilot import cli as product_cli
from protopilot.cli import main

pytestmark = [pytest.mark.unit]


class ReachableBackend:
    """A backend that answers. Stands in for a real API key or a logged-in CLI."""

    model = "claude-test"
    effort = "low"

    def check(self) -> None:
        return None


class UnreachableBackend:
    def __init__(self, why: str = "no credit on this account") -> None:
        self.why = why
        self.model = "claude-test"
        self.effort = "low"

    def check(self) -> None:
        raise RuntimeError(self.why)


@pytest.fixture()
def doctor(monkeypatch):
    """Run `proto doctor` with both backends reachable and no network."""
    monkeypatch.setattr(product_cli, "ClaudeLLM", ReachableBackend)
    monkeypatch.setattr(product_cli, "ClaudeCodeLLM", ReachableBackend)

    def run():
        return CliRunner().invoke(main, ["doctor"])

    return run


# ── the backend probe, which is one question asked twice ─────────────────


def test_either_backend_on_its_own_is_enough(doctor, monkeypatch):
    """API credit and a subscription are two answers to "can this machine
    reach Claude", not two requirements."""
    monkeypatch.setattr(product_cli, "ClaudeLLM", lambda: UnreachableBackend("no credit on this account"))

    result = doctor()

    assert result.exit_code == 0, result.output
    assert "FAIL no backend" not in result.output
    assert "no credit on this account" in result.output
    assert "ok   subscription" in result.output


def test_neither_backend_is_fatal_and_both_hints_are_printed(doctor, monkeypatch):
    """A reader who has neither needs the two ways out, not the two errors."""
    monkeypatch.setattr(product_cli, "ClaudeLLM", lambda: UnreachableBackend("no credit"))
    monkeypatch.setattr(product_cli, "ClaudeCodeLLM", lambda: UnreachableBackend("claude: not found"))

    result = doctor()

    assert result.exit_code == 1
    assert "FAIL no backend" in result.output
    assert "ANTHROPIC_API_KEY" in result.output
    assert "`claude` CLI" in result.output
    assert "`--offline` still works" in result.output, "the dry-run escape hatch is the only thing left to offer"
    assert "--no-verify" not in result.output


def test_a_backend_that_answers_is_reported_with_the_model_it_would_use(doctor):
    """Reachable is not the whole answer: which model and what effort is what
    the next `proto plan` will actually spend."""
    output = doctor().output
    assert "ok   api credit: reachable (model claude-test, effort low)" in output
