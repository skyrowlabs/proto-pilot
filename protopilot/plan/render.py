"""`Plan` to markdown: no model, no clock, so one plan is one set of bytes.

Topics, steps and findings keep the plan's order because that order means
something. Edges, sources and dreams are sorted, so their order in plan.json
cannot change the output. A dangling reference renders as its raw slug; saying
it is wrong is the verifier's job, and a renderer that crashed would hide it.
"""

from __future__ import annotations

import re
from pathlib import Path

from protopilot.plan.model import Dream, Edge, Finding, Plan, Source, Topic

PLAN_FILE = "PLAN.md"
DREAMS_FILE = "dreams.md"
SOURCES_FILE = "sources.md"
RUNBOOK_FILE = "RUNBOOK.md"
TOPICS_DIR = "topics"

HEADER = "<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->"
NOT_RESEARCHED = "> **Not researched.** Nothing here was checked against a source; every finding is an assumption."
#: Opens every runbook this tool writes, and is how a green run tells one from a person's own.
RUNBOOK_MARK = "<!-- Written by proto plan because this plan failed its checks. A green run removes this file. -->"
NOT_VERIFIED = f"> **Not verified.** This plan failed its checks; [{RUNBOOK_FILE}]({RUNBOOK_FILE}) says what is wrong."
NOT_VERIFIED_TOPIC = NOT_VERIFIED.replace(f"]({RUNBOOK_FILE})", f"](../{RUNBOOK_FILE})")
UNSET = "Not established."

#: What opens an HTML block in CommonMark, whose types 1 to 6 this lists: a comment or
#: `<details>` in plan text would hide the page after it. `<tags>` is not on the list
#: and is left alone, because a person's idea can hold one.
HTML_OPENER = re.compile(
    r"<(?=[!?]|/?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details"
    r"|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html"
    r"|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|pre|script|search"
    r"|section|style|summary|table|tbody|td|textarea|tfoot|th|thead|title|tr|track|ul)(?![a-z0-9-]))",
    re.IGNORECASE,
)


class PageBlocked(Exception):
    """Something that is not a page sits where a page must go; the message says what to do."""


def _inert(value: object) -> object:
    """`value` with every HTML opener in its strings escaped, however deeply nested."""
    if isinstance(value, str):
        return HTML_OPENER.sub("&lt;", value)
    if isinstance(value, list):
        return [_inert(item) for item in value]
    if isinstance(value, dict):
        return {key: _inert(item) for key, item in value.items()}
    return value


def _page(*blocks: str) -> str:
    """Blocks joined by a blank line; an empty block leaves no gap."""
    return "\n\n".join(b for b in (HEADER, *blocks) if b) + "\n"


def _bullets(items: list[str], empty: str = "None recorded.") -> str:
    return "\n".join(f"- {item}" for item in items) or empty


def _stamp(plan: Plan) -> str:
    return "" if plan.researched else NOT_RESEARCHED


def _edges(plan: Plan) -> list[Edge]:
    return sorted(plan.edges, key=lambda e: (e.from_topic, e.kind, e.to_topic))


def _edge_line(edge: Edge, titles: dict[str, str]) -> str:
    subject = titles.get(edge.from_topic, edge.from_topic)
    return f"{subject} {edge.kind.replace('-', ' ')} {titles.get(edge.to_topic, edge.to_topic)}"


def _plan_page(plan: Plan, verified: bool) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    scope = [
        f"**Goal:** {plan.goal or UNSET}",
        f"**Audience:** {plan.audience or UNSET}",
        f"**Horizon:** {plan.horizon or UNSET}",
    ]
    if plan.direction:
        scope.insert(0, f"**Direction:** {plan.direction}")
    topic_map = [f"[{t.title}]({TOPICS_DIR}/{t.slug}.md): {t.why}" for t in plan.topics]
    steps = [f"{n}. **{titles.get(s.topic, s.topic)}:** {s.action} {s.why}" for n, s in enumerate(plan.steps, start=1)]
    return _page(
        f"# {plan.title}",
        _stamp(plan),
        "" if verified else NOT_VERIFIED,
        f"## The idea\n\n{plan.idea}",
        "\n\n".join(scope),
        f"## Constraints\n\n{_bullets(plan.constraints)}",
        f"## Open questions\n\n{_bullets(plan.questions)}",
        f"## Topic map\n\n{_bullets(topic_map)}",
        f"## How the topics connect\n\n{_bullets([_edge_line(e, titles) for e in _edges(plan)])}",
        "## Where to start\n\n" + ("\n".join(steps) or "None recorded."),
        f"Extensions of the idea are kept apart, in [{DREAMS_FILE}]({DREAMS_FILE}).",
    )


def _finding_line(finding: Finding, known_sources: set[str]) -> str:
    """Anything no real source backs reads as an assumption, whatever its flag says."""
    cited = f" (sources: {', '.join(finding.source_ids)})" if finding.source_ids else ""
    backed = known_sources.intersection(finding.source_ids)
    label = "**Assumption:** " if finding.assumption or not backed else ""
    return f"{label}{finding.text}{cited}"


def _topic_page(plan: Plan, topic: Topic, verified: bool) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    links = [_edge_line(e, titles) for e in _edges(plan) if topic.slug in (e.from_topic, e.to_topic)]
    known_sources = {s.id for s in plan.sources}
    return _page(
        f"# {topic.title}",
        _stamp(plan),
        "" if verified else NOT_VERIFIED_TOPIC,
        f"Part of [{plan.title}](../{PLAN_FILE}).",
        topic.why,
        f"## Findings\n\n{_bullets([_finding_line(f, known_sources) for f in topic.findings])}",
        f"## Connections\n\n{_bullets(links)}",
        f"## Risks\n\n{_bullets(topic.risks)}",
        f"## Unknowns\n\n{_bullets(topic.unknowns)}",
        f"## Decisions to make\n\n{_bullets(topic.decisions)}",
    )


def _whole_record(record: Dream | Source) -> tuple[str, str]:
    """Id first, then every field, so a repeated id cannot leak plan.json's order."""
    return record.id, record.model_dump_json()


def _dream_block(dream: Dream, titles: dict[str, str]) -> str:
    facts = [
        f"Extends: {titles.get(dream.anchor, dream.anchor)}",
        f"Lens: {dream.lens}",
        f"Would take: {dream.takes}",
    ]
    if dream.verdict:
        facts.append(f"Verdict: {dream.verdict}" + (f". {dream.reason}" if dream.reason else ""))
    if dream.if_adopted:
        facts.append(f"If adopted: {dream.if_adopted}")
    return f"### {dream.title} ({dream.id})\n\nWhat if {dream.what_if}\n\n{_bullets(facts)}"


def _dreams_page(plan: Plan) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    dreams = sorted(plan.dreams, key=_whole_record)
    sections = (("Proposals", "proposed"), ("Set aside", "set-aside"), ("Not yet evaluated", None))
    blocks = []
    for heading, verdict in sections:
        chosen = [_dream_block(d, titles) for d in dreams if d.verdict == verdict]
        if chosen:
            blocks.append("\n\n".join([f"## {heading}", *chosen]))
    return _page(
        "# Dreams",
        "Extensions of the idea, kept apart from the plan. Nothing here is researched.",
        *(blocks or ["No dreams yet: dreaming has not run for this plan."]),
    )


def _sources_page(plan: Plan) -> str:
    sources = [f"{s.id}: [{s.title}]({s.url})" for s in sorted(plan.sources, key=_whole_record)]
    return _page("# Sources", _stamp(plan), _bullets(sources, empty="No sources."))


def render(plan: Plan, runbook: str = "") -> dict[str, str]:
    """Every markdown file, by path relative to the tree. A `runbook` marks the plan unverified."""
    plan = Plan.model_validate(_inert(plan.model_dump()))
    verified = not runbook
    pages = {PLAN_FILE: _plan_page(plan, verified)}
    pages.update({f"{TOPICS_DIR}/{t.slug}.md": _topic_page(plan, t, verified) for t in plan.topics})
    pages[DREAMS_FILE] = _dreams_page(plan)
    pages[SOURCES_FILE] = _sources_page(plan)
    if runbook:
        pages[RUNBOOK_FILE] = f"{RUNBOOK_MARK}\n\n{_inert(runbook)}"
    return pages


def _is_ours(path: Path) -> bool:
    """A runbook this tool wrote, read without following a link."""
    if path.is_symlink() or not path.is_file():
        return False
    return path.read_text(encoding="utf-8", errors="replace").startswith(RUNBOOK_MARK)


def _blockers(pages: dict[str, str], tree: Path) -> list[Path]:
    """What stands where a page must go: a link, dangling or not, a directory, a person's runbook."""
    folder = tree / TOPICS_DIR
    blocked = [folder] if folder.is_symlink() or (folder.exists() and not folder.is_dir()) else []
    for name in pages:
        path = tree / name
        if name.startswith(f"{TOPICS_DIR}/") and blocked[:1] == [folder]:
            continue
        foreign = name == RUNBOOK_FILE and path.exists() and not _is_ours(path)
        if path.is_symlink() or path.is_dir() or foreign:
            blocked.append(path)
    return blocked


def _clear_stale(pages: dict[str, str], tree: Path, folder_free: bool) -> None:
    """Drop a topic page the plan lost, and a runbook of ours once green. A link is never followed or removed."""
    stale = [path for path in (tree / TOPICS_DIR).glob("*.md") if f"{TOPICS_DIR}/{path.name}" not in pages]
    stale = stale if folder_free else []
    if RUNBOOK_FILE not in pages and _is_ours(tree / RUNBOOK_FILE):
        stale.append(tree / RUNBOOK_FILE)
    for path in stale:
        if path.is_file() and not path.is_symlink():
            path.unlink()


def write(plan: Plan, tree: Path, runbook: str = "") -> list[str]:
    """Overwrite the rendered files and drop stale ones, never through anything `_blockers` names.

    A green plan that is blocked moves nothing. A red one still draws every page it can
    reach, so no old page goes on reading as verified, and then refuses.
    """
    tree = Path(tree)
    pages = render(plan, runbook)
    blocked = _blockers(pages, tree)
    names = ", ".join(str(path) for path in blocked)
    if blocked and not runbook:
        raise PageBlocked(
            f"The plan is saved but nothing was drawn, because a page needs this name: {names}. "
            "Move it out of the way and rerun, which draws the plan again with no model call."
        )
    folder = tree / TOPICS_DIR
    folder_free = folder not in blocked
    if folder_free:
        folder.mkdir(parents=True, exist_ok=True)
    _clear_stale(pages, tree, folder_free)
    free = [
        name for name in pages if tree / name not in blocked and (folder_free or not name.startswith(f"{TOPICS_DIR}/"))
    ]
    # The entry page goes last, so a fresh tree holding PLAN.md holds every page. Over an old
    # one a red plan goes first, so a write that dies midway leaves it marked rather than clean.
    entry_first = bool(runbook) and (tree / PLAN_FILE).is_file()
    for name in sorted(free, key=lambda page: (page == PLAN_FILE) != entry_first):
        (tree / name).write_text(pages[name], encoding="utf-8")
    if blocked:
        raise PageBlocked(
            f"The plan is saved and failed its checks, and a page needs this name: {names}. Every other page is "
            "drawn and marked not verified. Move it out of the way and rerun, which draws the rest with no model call."
        )
    return list(pages)


def read(tree: Path) -> dict[str, str]:
    """The pages on disk, in `render`'s shape, so a check reads what landed as it reads what was drawn."""
    tree = Path(tree)
    found = [*tree.glob("*.md"), *(tree / TOPICS_DIR).glob("*.md")]
    return {
        path.relative_to(tree).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in found
        if path.is_file() and not path.is_symlink()
    }
