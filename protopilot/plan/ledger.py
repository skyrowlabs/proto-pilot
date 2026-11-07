"""The research ledger: what a run fetched, read from its own stream-json, never from the model.

A source counts as fetched only when a `WebFetch` in this run's transcript brought back
usable content for its URL. Telling usable from failed is a **heuristic**: a 403 or an
unfollowed redirect returns no error flag, only text and, where the CLI sends one, a
status code. `usable` reads both, and errs toward calling a fetch failed.

What a usable fetch proves is narrow: `WebFetch` returns a model's summary of the page,
not the page, so a citation shows that summary was read, never that a claim is in the source.

The transcripts live in `.protopilot/research/`, beside the reviewed outline a resumed
run starts from. `reconciled` redraws each record's fetches from its transcript, so a
`fetched: true` typed into plan.json, or a fetch typed into the ledger, earns nothing.
A forged transcript is beyond any check here.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from protopilot.llm import LLMError, stream_events
from protopilot.plan.model import Fetch, Plan
from protopilot.spec import SPEC_DIR

RESEARCH_DIR = f"{SPEC_DIR}/research"
DRAFT_FILE = "outline.json"
#: Text a failed fetch comes back as, or a summary saying it read nothing. A heuristic.
FAILED_TEXT = (
    re.compile(r"returned HTTP [45]\d\d", re.IGNORECASE),
    re.compile(r"REDIRECT DETECTED"),
    re.compile(r"response body was not retrieved", re.IGNORECASE),
    re.compile(r"\b(?:could not|couldn't|cannot|can't|unable to) (?:find|read|access|retrieve) any", re.IGNORECASE),
    re.compile(r"\bnot readable text\b", re.IGNORECASE),
)


def normal(url: str) -> str:
    """One spelling per page: no fragment, a lowercase scheme and host, no trailing slash."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(block.get("text", "")) for block in content if isinstance(block, dict))
    return ""


def judged(url: str, text: str, meta: dict | None, is_error: bool) -> Fetch:
    """One fetch, usable or not, with the reason. `meta` is the CLI's `tool_use_result`, if it sent one."""
    meta = meta or {}
    code, size = meta.get("code"), meta.get("bytes")
    if is_error:
        return Fetch(url=url, usable=False, why="the tool reported an error")
    if isinstance(code, int) and not 200 <= code < 300:
        return Fetch(url=url, usable=False, why=f"HTTP {code}")
    if size == 0 or not text.strip():
        return Fetch(url=url, usable=False, why="nothing came back")
    failed = next((pattern for pattern in FAILED_TEXT if pattern.search(text)), None)
    if failed:
        return Fetch(url=url, usable=False, why="the summary reads as a failure")
    return Fetch(url=url, usable=True)


def fetches(transcript: str) -> list[Fetch]:
    """Every `WebFetch` the transcript holds a result for, in order."""
    asked: dict[str, str] = {}
    found: list[Fetch] = []
    for event in stream_events(transcript):
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        if event.get("type") == "assistant":
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "WebFetch":
                    url = (block.get("input") or {}).get("url")
                    if isinstance(url, str) and block.get("id"):
                        asked[block["id"]] = url
        elif event.get("type") == "user":
            results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
            meta = event.get("tool_use_result")
            # The CLI's metadata names no tool_use_id, so it is read only when one result is all there is.
            meta = meta if len(results) == 1 and isinstance(meta, dict) else None
            for block in results:
                url = asked.pop(str(block.get("tool_use_id")), None)
                if url is not None:
                    found.append(judged(url, _text(block.get("content")), meta, bool(block.get("is_error"))))
    return found


def usable_urls(plan: Plan) -> set[str]:
    """The URLs this plan's ledger holds a usable fetch of, normalised."""
    return {normal(fetch.url) for record in plan.research for fetch in record.fetches if fetch.usable}


# -- the sidecar --------------------------------------------------------


def research_dir(tree: Path) -> Path:
    return Path(tree) / RESEARCH_DIR


def transcript_name(slug: str) -> str:
    return f"{slug}.jsonl"


def digest(transcript: str) -> str:
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


def write_transcript(tree: Path, slug: str, transcript: str) -> str:
    """Land a topic's transcript whole, and return its file name."""
    folder = research_dir(tree)
    folder.mkdir(parents=True, exist_ok=True)
    name = transcript_name(slug)
    temp = folder / f".{name}.tmp"
    temp.write_text(transcript, encoding="utf-8")
    temp.replace(folder / name)
    return name


def read_transcript(tree: Path, slug: str) -> str | None:
    path = research_dir(tree) / transcript_name(slug)
    if path.is_symlink() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def save_draft(tree: Path, plan: Plan) -> None:
    """The reviewed outline, so a run that stops during research resumes from it."""
    path = research_dir(tree) / DRAFT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{DRAFT_FILE}.tmp")
    temp.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def draft(tree: Path) -> Plan | None:
    """The outline a stopped run left, or None. One that cannot be read is a `ValueError`."""
    path = research_dir(tree) / DRAFT_FILE
    if path.is_symlink() or not path.is_file():
        return None
    return Plan.model_validate_json(path.read_text(encoding="utf-8"))


def forget_draft(tree: Path) -> None:
    """Once plan.json has landed, the draft is history. The transcripts stay: they are the evidence."""
    with suppress(OSError):
        (research_dir(tree) / DRAFT_FILE).unlink(missing_ok=True)


def reconciled(plan: Plan, tree: Path) -> Plan:
    """`plan` with each record's fetches drawn again from its transcript; a missing or edited one holds none."""
    records = []
    for record in plan.research:
        if not record.transcript:
            records.append(record.model_copy(update={"fetches": []}))
            continue
        path = research_dir(tree) / Path(record.transcript).name
        said = None if path.is_symlink() or not path.is_file() else path.read_text(encoding="utf-8", errors="replace")
        try:
            found = fetches(said) if said is not None and digest(said) == record.sha256 else []
        except LLMError:
            found = []
        records.append(record.model_copy(update={"fetches": found}))
    return plan.revised(research=[r.model_dump() for r in records])
