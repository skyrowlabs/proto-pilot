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
A forged transcript is beyond any check here. `normal` keeps http/https, `www.`, `:443`
and `%7E` apart, which errs toward calling a citation an assumption: a ruling, for now.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from protopilot.llm import LLMError, stream_events
from protopilot.plan.model import Fetch, Plan, TopicResearch
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
    re.compile(r"\bstatus code [45]\d\d\b", re.IGNORECASE),
    re.compile(r"\b[45]\d\d (?:Forbidden|Not Found|Unauthorized|Gone|Too Many Requests|Bad Gateway)\b", re.IGNORECASE),
    re.compile(r"\b(?:page|file) not found\b", re.IGNORECASE),
    re.compile(r"\baccess denied\b", re.IGNORECASE),
    re.compile(r"\bjust a moment\b|\benable javascript\b", re.IGNORECASE),
)
#: What a record says when its evidence is gone, so a hand edit reads as what it is.
NO_EVIDENCE = "its transcript is missing, renamed or altered, so nothing it fetched counts"


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


def _evidence(record: TopicResearch, tree: Path) -> list[Fetch] | None:
    """The fetches in this topic's own transcript, or None if it is not there as written."""
    if record.transcript != transcript_name(record.topic):
        return None
    path = research_dir(tree) / record.transcript
    if path.is_symlink() or not path.is_file():
        return None
    said = path.read_text(encoding="utf-8", errors="replace")
    if digest(said) != record.sha256:
        return None
    try:
        return fetches(said)
    except LLMError:
        return None


def cites_own(plan: Plan, slug: str, found: list[Fetch]) -> bool:
    """Whether a finding of `slug` cites a source that this topic's own fetches back."""
    usable = {normal(fetch.url) for fetch in found if fetch.usable}
    urls = {source.id: normal(source.url) for source in plan.sources}
    topic = next((t for t in plan.topics if t.slug == slug), None)
    findings = topic.findings if topic else []
    return any(urls.get(i) in usable for f in findings if not f.assumption for i in f.source_ids)


def reconciled(plan: Plan, tree: Path) -> Plan:
    """`plan` with each record's fetches and state drawn again from its own transcript, never from plan.json.

    An honest failure needs no evidence and stays one. Any other record without its
    transcript is a failure that says so, and `researched` follows the records.
    """
    records = []
    for record in plan.research:
        found = _evidence(record, tree)
        if found is None and record.state == "failed" and not record.transcript:
            records.append(record.model_copy(update={"fetches": []}))
        elif found is None:
            records.append(record.model_copy(update={"fetches": [], "state": "failed", "failure": NO_EVIDENCE}))
        else:
            state = "researched" if cites_own(plan, record.topic, found) else "nothing cited"
            records.append(record.model_copy(update={"fetches": found, "state": state, "failure": ""}))
    researched = any(r.state == "researched" for r in records) if records else plan.researched
    return plan.revised(research=[r.model_dump() for r in records], researched=researched)
