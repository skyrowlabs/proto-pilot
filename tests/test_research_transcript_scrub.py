"""A research transcript keeps the evidence and nothing about the machine that made it (#51)."""

from __future__ import annotations

import json

import pytest
from plan_script import IDEA, script
from research_script import HELD, ResearchingLLM, transcript

from protopilot.jobs import Job
from protopilot.llm import ClaudeCodeLLM, LLMError, Researched, scrubbed
from protopilot.plan import ledger, pipeline
from protopilot.plan.model import Plan
from protopilot.runner import CommandResult

pytestmark = [pytest.mark.unit]

#: Built in pieces, so this file does not itself name a home directory (tests/test_publication.py).
HOME = "/home/" + "someone"
MACHINE = {
    "cwd": f"{HOME}/private-project",
    "memory_paths": [f"{HOME}/.claude/projects/x/memory"],
    "plugins": [{"name": "a-plugin", "path": f"{HOME}/.claude/plugins/a"}],
    "skills": ["a-private-skill"],
    "slash_commands": ["/a-private-command"],
    "claude_code_version": "9.9.9",
    "session_id": "abc",
}
FINGERPRINTS = (HOME, "a-private-skill", "a-private-command", "a-plugin", "9.9.9")


def fat(tools: list[str] = HELD) -> str:
    """A stream whose init carries the machine, with a system event nothing reads, as `claude` writes one."""
    lines = transcript(tools=tools).splitlines()
    init = {**json.loads(lines[0]), **MACHINE}
    noise = {"type": "system", "subtype": "thinking_tokens", "session_id": "abc", "estimated_tokens": 9}
    return "\n".join([json.dumps(init), json.dumps(noise), *lines[1:]]) + "\n"


class Once:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout

    def run(self, argv, cwd=None, timeout=None):  # noqa: ANN001, ANN201
        return CommandResult(list(argv), 0, self.stdout, "")


class Live(ResearchingLLM):
    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched:
        backend = ClaudeCodeLLM(runner=Once(fat()))
        return backend.research(system=system, user=user, schema=schema, label=label)


def test_no_fingerprint_of_the_machine_reaches_a_written_transcript_and_the_topic_is_still_researched(tmp_path):
    tree = tmp_path / "tree"
    assert pipeline.run_plan(Job(id="t", idea=IDEA), tree, Live(script(), {})).ok
    written = [p.read_text(encoding="utf-8") for p in ledger.research_dir(tree).glob("*.jsonl")]
    assert written and not [f for f in FINGERPRINTS for said in written if f in said]
    assert all('"thinking_tokens"' not in said for said in written)
    reconciled = ledger.reconciled(Plan.load(tree), tree)
    assert reconciled.researched and {r.state for r in reconciled.research} == {"researched"}


def test_a_scrubbed_stream_keeps_every_fetch_and_the_answer():
    assert ledger.fetches(scrubbed(fat())) == ledger.fetches(fat())
    assert scrubbed(transcript()) == transcript()


def test_the_isolation_check_still_reads_the_full_stream_and_refuses_a_shell():
    with pytest.raises(LLMError, match="held Bash"):
        ClaudeCodeLLM(runner=Once(fat([*HELD, "Bash"]))).research(system="s", user="u", schema={}, label="r")


def test_a_refused_stream_is_kept_scrubbed_too(tmp_path):
    from protopilot.llm import ResearchFailed

    with pytest.raises(ResearchFailed) as raised:
        ClaudeCodeLLM(runner=Once(fat([*HELD, "Bash"]))).research(system="s", user="u", schema={}, label="r")
    assert '"Bash"' in raised.value.transcript and not [f for f in FINGERPRINTS if f in raised.value.transcript]
