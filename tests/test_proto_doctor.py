"""`proto doctor`, and the per-target preflight it opens with.

This is the command a person runs the moment `proto new` fails, so it is on
the first-run path for everyone — and since the default target moved to `tui`
it is the *terminal* preflight that decides whether that person is told they
can generate at all. It had no test: `tests/test_cli_smoke.py` walks `cli.cli`,
which is this **repository's** `./pp` (Rule 15), so nothing there ever
executes a `proto` command, and the two backend probes reach the network,
which is why it stayed hand-verified.

Both externals are stubbed at the boundary and nowhere else. `ClaudeLLM.check`
spends a token on a real request and `ClaudeCodeLLM.check` shells out to the
`claude` binary, so the two factories are replaced by name — which doubles as
the assertion that `doctor` still asks through those names. `docker_available`
is the third: it is a `docker info` subprocess whose answer depends on the
machine, and the whole point of the per-target loop is that its answer must
not decide anything for a target with no container in it.

What is *not* stubbed is the target registry. Every expectation below is
recomputed from `targets.names()`, so a third target is covered by existing —
the same property that makes the registry a registry and not a list.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from protopilot import cli as product_cli
from protopilot import runner as runner_module
from protopilot import targets
from protopilot.cli import main
from protopilot.runner import SubprocessRunner

# Host-side: no key, no network, no Docker daemon. Everything that needs one
# is replaced at its boundary.
pytestmark = [pytest.mark.unit]

OTHERS = [name for name in targets.names() if name != targets.DEFAULT]


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
def docker_says(monkeypatch):
    """Control what a Docker probe would answer, and count who asked.

    Patched on `protopilot.runner`, which is where `targets.web.preflight`
    imports it from at call time. Returns the list of runners it was handed,
    so a test can assert both the answer that came back and the fact that a
    target which needs no daemon never asked.
    """
    asked: list = []

    def install(ok: bool, why: str) -> list:
        def fake(runner):
            asked.append(runner)
            return ok, why

        monkeypatch.setattr(runner_module, "docker_available", fake)
        return asked

    return install


@pytest.fixture()
def doctor(monkeypatch, docker_says):
    """Run `proto doctor` with the network and the port probe stubbed out.

    `free_port` binds a real socket and is not what any of this is about; a
    machine with 8080–8179 all taken would otherwise turn every assertion here
    into a flake about somebody else's process.
    """
    monkeypatch.setattr(product_cli, "ClaudeLLM", ReachableBackend)
    monkeypatch.setattr(product_cli, "ClaudeCodeLLM", ReachableBackend)
    monkeypatch.setattr(product_cli, "free_port", lambda: 8080)
    docker_says(True, "docker ok")

    def run():
        return CliRunner().invoke(main, ["doctor"])

    return run


def target_lines(output: str) -> dict[str, str]:
    """The one line each target got, keyed by target name."""
    found = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "target":
            found[parts[2].rstrip(":")] = line
    return found


# ── the per-target loop ──────────────────────────────────────────────────


def test_every_installed_target_gets_a_verdict(doctor):
    """Recomputed from the registry rather than listed. A target reported by
    nothing is a target whose preflight nobody can see the answer to."""
    result = doctor()
    reported = target_lines(result.output)

    assert set(reported) == set(targets.names())
    for name, line in reported.items():
        assert line.startswith("ok "), f"{name} was reported as anything but ready: {line}"


def test_each_targets_own_reason_is_what_is_printed(doctor, monkeypatch):
    """The preflight's second return value, not a sentence `doctor` invented.

    A target answers *why* as well as *whether*, and that half is the only
    actionable thing in the report — "not ready" with no reason is a dead end
    at exactly the moment somebody is stuck.
    """
    for name in targets.names():
        reason = f"{name} is fine because reasons"
        monkeypatch.setattr(targets.get(name), "preflight", lambda runner, why=reason: (True, why))

    output = doctor().output
    for name in targets.names():
        assert f"{name} is fine because reasons" in output


def test_only_the_default_target_is_marked_as_the_default(doctor):
    """`proto new` with no `--target` picks one, and this is one of the two
    places a user can find out which."""
    marked = [line for line in doctor().output.splitlines() if "(default)" in line]
    assert len(marked) == 1
    assert marked[0].split()[2] == targets.DEFAULT


def test_a_default_target_that_is_not_ready_is_fatal(doctor, monkeypatch):
    """The exit code is the default target's answer and nobody else's — that
    is what a person who typed `proto new` and got nothing needs to know."""
    monkeypatch.setattr(targets.get(targets.DEFAULT), "preflight", lambda runner: (False, "the widget mill is cold"))

    result = doctor()

    assert result.exit_code == 1
    assert target_lines(result.output)[targets.DEFAULT].startswith("FAIL")
    assert "the widget mill is cold" in result.output
    assert "not ready" in result.output


@pytest.mark.parametrize("other", OTHERS)
def test_a_non_default_target_that_is_not_ready_is_not_fatal(doctor, monkeypatch, other):
    """The defect this loop exists to fix, stated as a test.

    A flat `docker_available` FAIL told somebody whose default target needs no
    daemon that they could not generate. The web target being unavailable is
    now a note with a way forward, not a verdict.
    """
    monkeypatch.setattr(targets.get(other), "preflight", lambda runner: (False, "the docker daemon is not reachable"))

    result = doctor()

    assert result.exit_code == 0, result.output
    assert "FAIL target" not in result.output
    assert target_lines(result.output)[other].startswith("-- ")
    assert "the docker daemon is not reachable" in result.output
    assert f"it builds {targets.DEFAULT}" in result.output, "a target that is out has to say what still works"
    assert "ready" in result.output.splitlines()[-1]


def test_a_machine_with_no_docker_at_all_is_still_ready(doctor, docker_says):
    """The first-run path since the default flip, end to end.

    `doctor` is what a new user runs when `proto new` fails, and the answer on
    a machine with no daemon has to be "yes, you can generate" — because what
    `proto new` builds there is a terminal app that never wanted one.
    """
    docker_says(False, "docker is not installed or not on PATH")

    result = doctor()

    assert result.exit_code == 0, result.output
    default_line = target_lines(result.output)[targets.DEFAULT]
    assert default_line.startswith("ok "), f"the default target was refused over Docker: {default_line}"
    assert result.output.splitlines()[-1] == "ready"


def test_the_preflight_is_handed_a_runner_and_only_the_target_that_needs_one_asks(doctor, docker_says):
    """Two halves of one seam.

    `doctor` builds one runner and passes it down, so a target's preflight can
    shell out; and a target with no container in it never reaches that code at
    all. Counted on the *probe* rather than on the loop, because the second
    half is only true if the question is the target's.
    """
    asked = docker_says(True, "docker ok")

    doctor()

    assert len(asked) == 1, f"{len(asked)} target(s) consulted Docker; exactly one has a container in it"
    assert isinstance(
        asked[0], SubprocessRunner
    ), "the target's preflight was handed something it cannot shell out with"


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
    assert "--offline --no-verify" in result.output, "the dry-run escape hatch is the only thing left to offer"


def test_a_backend_that_answers_is_reported_with_the_model_it_would_use(doctor):
    """Reachable is not the whole answer: which model and what effort is what
    the next `proto new` will actually spend."""
    output = doctor().output
    assert "ok   api credit: reachable (model claude-test, effort low)" in output
