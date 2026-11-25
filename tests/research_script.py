"""Research transcripts in the shape `claude --output-format stream-json` writes, as Phase 1 recorded it.

`transcript` builds one: an init event naming the tools, a `WebFetch` and its result per
fetch, then the result event. `ResearchingLLM` is a `FakeLLM` that also answers `research`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from fakes import FakeLLM

from protopilot.llm import Researched

URL = "https://example.org/tool-libraries"
OTHER = "https://example.net/insurance"
SUMMARY = "The page says most tool libraries carry general liability insurance."
HELD = ["StructuredOutput", "WebFetch", "WebSearch"]


def fetched(url: str = URL, code: int = 200, text: str = SUMMARY, size: int = 5000) -> tuple:
    return (url, code, text, size)


def cited(text: str = "Most tool libraries carry liability cover.", url: str = URL, title: str = "A guide") -> dict:
    return {"text": text, "kind": "cited", "sources": [{"url": url, "title": title}] if url else []}


def assumed(text: str = "Volunteers will turn up every week.") -> dict:
    return {"text": text, "kind": "assumption", "sources": []}


def transcript(
    findings: Sequence[dict] = (),
    fetches: Sequence[tuple] = (),
    tools: Sequence[str] = HELD,
    mcp: Sequence[dict] = (),
    result: dict | None = None,
) -> str:
    """One research session as stream-json lines. `findings` default to one cited finding and two assumed."""
    findings = list(findings) or [cited(), assumed(), assumed("A shed can hold the first hundred tools.")]
    fetches = list(fetches) or [fetched()]
    events: list[dict] = [{"type": "system", "subtype": "init", "tools": list(tools), "mcp_servers": list(mcp)}]
    for number, (url, code, text, size) in enumerate(fetches):
        use = f"toolu_{number}"
        events.append(
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "id": use, "name": "WebFetch", "input": {"url": url}}]},
            }
        )
        events.append(
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "tool_use_id": use, "content": text}]},
                "tool_use_result": {"bytes": size, "code": code, "codeText": "", "url": url},
            }
        )
    events.append(
        result
        or {"type": "result", "subtype": "success", "is_error": False, "structured_output": {"findings": findings}}
    )
    return "\n".join(json.dumps(event) for event in events) + "\n"


class ResearchingLLM(FakeLLM):
    """Canned structured answers, and canned research transcripts by topic slug (or in order)."""

    def __init__(self, responses: Sequence[object], research: dict[str, object] | Sequence[object] = ()):
        super().__init__(responses)
        self.research_script = research
        self.researched: list[str] = []

    def research(self, *, system: str, user: str, schema: dict, label: str) -> Researched:
        from protopilot.llm import research_result

        slug = label.split(" ", 1)[1]
        self.researched.append(slug)
        if isinstance(self.research_script, dict):
            said = self.research_script.get(slug, transcript())
        else:
            queue = list(self.research_script)
            said = queue[len(self.researched) - 1] if len(self.researched) <= len(queue) else transcript()
        if isinstance(said, Exception):
            raise said
        assert isinstance(said, str)
        return Researched(research_result(said, label), said)


def old_shape(said: str) -> str:
    """`said` as a run before #53 answered it: each finding's one `source_url` and `source_title`."""
    events = [json.loads(line) for line in said.splitlines()]
    for event in events:
        for row in (event.get("structured_output") or {}).get("findings", []):
            first = (row.pop("sources") or [{"url": "", "title": ""}])[0]
            row["source_url"], row["source_title"] = first["url"], first["title"]
    return "\n".join(json.dumps(event) for event in events) + "\n"
