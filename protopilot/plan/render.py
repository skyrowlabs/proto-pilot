"""`Plan` to markdown: no model, no clock, so one plan is one set of bytes.

Topics, steps and findings keep the plan's order because that order means
something. Edges, sources and dreams are sorted, so their order in plan.json
cannot change the output. A dangling reference renders as its raw slug; saying
it is wrong is the verifier's job, and a renderer that crashed would hide it.
"""

from __future__ import annotations

from pathlib import Path

from protopilot.plan.model import Dream, Edge, Finding, Plan, Source, Topic

PLAN_FILE = "PLAN.md"
DREAMS_FILE = "dreams.md"
SOURCES_FILE = "sources.md"
TOPICS_DIR = "topics"

HEADER = "<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->"
NOT_RESEARCHED = "> **Not researched.** Nothing here was checked against a source; every finding is an assumption."
UNSET = "Not established."


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


def _plan_page(plan: Plan) -> str:
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


def _topic_page(plan: Plan, topic: Topic) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    links = [_edge_line(e, titles) for e in _edges(plan) if topic.slug in (e.from_topic, e.to_topic)]
    known_sources = {s.id for s in plan.sources}
    return _page(
        f"# {topic.title}",
        _stamp(plan),
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


def render(plan: Plan) -> dict[str, str]:
    """Every markdown file, by path relative to the tree."""
    pages = {PLAN_FILE: _plan_page(plan)}
    pages.update({f"{TOPICS_DIR}/{t.slug}.md": _topic_page(plan, t) for t in plan.topics})
    pages[DREAMS_FILE] = _dreams_page(plan)
    pages[SOURCES_FILE] = _sources_page(plan)
    return pages


def write(plan: Plan, tree: Path) -> list[str]:
    """Overwrite the rendered files, and drop topic pages the plan no longer has."""
    pages = render(plan)
    topics = Path(tree) / TOPICS_DIR
    topics.mkdir(parents=True, exist_ok=True)
    for stale in topics.glob("*.md"):
        if stale.is_file() and f"{TOPICS_DIR}/{stale.name}" not in pages:
            stale.unlink()
    # The entry page goes last, so a fresh tree holding PLAN.md holds every page.
    for name in sorted(pages, key=lambda page: page == PLAN_FILE):
        (Path(tree) / name).write_text(pages[name], encoding="utf-8")
    return list(pages)
