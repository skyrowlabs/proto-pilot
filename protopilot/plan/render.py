"""`Plan` to markdown: no model, no clock, so one plan is one set of bytes.

Topics, steps and findings keep the plan's order because that order means
something. Edges, sources and dreams are sorted, so their order in plan.json
cannot change the output. A dangling reference renders as its raw slug; saying
it is wrong is the verifier's job, and a renderer that crashed would hide it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from protopilot.plan.lenses import words as lens_words
from protopilot.plan.model import RUBRIC, Dream, Edge, Finding, Plan, Source, Topic, TopicResearch

PLAN_FILE = "PLAN.md"
DREAMS_FILE = "dreams.md"
SOURCES_FILE = "sources.md"
RUNBOOK_FILE = "RUNBOOK.md"
TOPICS_DIR = "topics"

HEADER = "<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->"
NOT_RESEARCHED = "> **Not researched.** Nothing here was checked against a source; every finding is an assumption."
#: What a citation proves, said wherever one is drawn: the page was read through a summary of it.
THROUGH_A_SUMMARY = (
    "each read through a model's summary of the page, not the page itself, so a citation shows the "
    "summary was read, never that the claim is in the source"
)
RESEARCHED = f"> **Researched.** Cited findings rest on pages fetched during this run, {THROUGH_A_SUMMARY}."
TOPIC_RESEARCHED = (
    f"> **Researched.** Cited findings rest on pages fetched during this run, {THROUGH_A_SUMMARY}. "
    "Anything uncited is an assumption."
)
#: Opens every runbook this tool writes, and is how a green run tells one from a person's own.
RUNBOOK_MARK = "<!-- Written by proto plan because this plan failed its checks. A green run removes this file. -->"
NOT_VERIFIED = f"> **Not verified.** This plan failed its checks; [{RUNBOOK_FILE}]({RUNBOOK_FILE}) says what is wrong."
NOT_VERIFIED_TOPIC = NOT_VERIFIED.replace(f"]({RUNBOOK_FILE})", f"](../{RUNBOOK_FILE})")
UNSET = "Not established."
RETRY = "`proto dream` tries again."
HOW_TO_CHOOSE = (
    'Only a person moves a dream: `proto dream promote <id>` makes it a topic, and `proto dream drop <id> --why "..."` '
    "rules it out."
)

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


def _topic_file(slug: str) -> str:
    return f"{TOPICS_DIR}/{slug}.md"


def _page(*blocks: str) -> str:
    """Blocks joined by a blank line; an empty block leaves no gap."""
    return "\n\n".join(b for b in (HEADER, *blocks) if b) + "\n"


def _bullets(items: list[str], empty: str = "None recorded.") -> str:
    return "\n".join(f"- {item}" for item in items) or empty


def topic_research(plan: Plan, topic: Topic) -> tuple[bool, str]:
    """Whether this topic was researched, and if not, why, in a sentence."""
    record: TopicResearch | None = plan.research_of(topic.slug)
    if record is not None and record.state == "researched":
        return True, ""
    if record is not None and record.state == "failed":
        return False, f"Research for this topic failed: {record.failure.rstrip('.')}."
    if record is not None:
        return False, "Research ran and cited no page it fetched."
    if any(dream.promoted_to == topic.slug for dream in plan.dreams):
        return False, "It was promoted from a dream, and a person's choice is not research."
    if plan.research_failure:
        return False, f"Research did not run: {plan.research_failure.rstrip('.')}."
    return False, "Research did not run for it."


def _stamp(plan: Plan) -> str:
    """The entry page's word on research: whole, in part with each topic left out named, or not at all."""
    if not plan.researched:
        why = f"\n>\n> Research did not run: {plan.research_failure}" if plan.research_failure else ""
        return NOT_RESEARCHED + why
    left = [(t, topic_research(plan, t)) for t in plan.topics]
    left = [f"> - {t.title}: {why}" for t, (done, why) in left if not done]
    if not left:
        return RESEARCHED
    return "\n".join(
        [RESEARCHED, ">", "> These topics are **not researched**, and every finding in them is an assumption:", *left]
    )


def _topic_stamp(plan: Plan, topic: Topic) -> str:
    done, why = topic_research(plan, topic)
    if not plan.researched:
        failed = plan.research_of(topic.slug)
        return f"{NOT_RESEARCHED} {why}" if failed is not None else NOT_RESEARCHED
    return TOPIC_RESEARCHED if done else f"> **Not researched.** {why} Every finding here is an assumption."


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
    topic_map = [f"[{t.title}]({_topic_file(t.slug)}): {t.why}" for t in plan.topics]
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
        _topic_stamp(plan, topic),
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


def _scores(dream: Dream) -> list[str]:
    """Each rubric answer on its own: a rank nobody can see the reasons for is what they replace."""
    scores = [(field, getattr(dream, field)) for field in RUBRIC if getattr(dream, field)]
    return [f"Scores: {', '.join(f'{field} {score}' for field, score in scores)}"] if scores else []


def _dream_block(dream: Dream, titles: dict[str, str]) -> str:
    facts = [
        f"Extends: {titles.get(dream.anchor, dream.anchor)}",
        f"Lens: {lens_words(dream.lens)}",
        f"Would take: {dream.takes}",
        *_scores(dream),
    ]
    if dream.verdict == "promoted":
        facts += ["Verdict: promoted", *([dream.reason] if dream.reason else [])]
    elif dream.verdict:
        facts.append(f"Verdict: {dream.verdict}" + (f". {dream.reason}" if dream.reason else ""))
    if dream.if_adopted:
        facts.append(f"If adopted: {dream.if_adopted}")
    if dream.promoted_to:
        facts.append(
            f"Now the topic: [{titles.get(dream.promoted_to, dream.promoted_to)}]({_topic_file(dream.promoted_to)})"
        )
    return f"### {dream.title} ({dream.id})\n\nWhat if {dream.what_if}\n\n{_bullets(facts)}"


def _dream_order(dream: Dream) -> tuple[int, str, str]:
    """By number: d10 comes after d9, and a repeated id still cannot leak plan.json's order."""
    return (len(dream.id), *_whole_record(dream))


def _dreams_page(plan: Plan) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    dreams = sorted(plan.dreams, key=_dream_order)
    sections = (
        ("Proposals", "proposed"),
        ("Set aside", "set-aside"),
        ("Promoted", "promoted"),
        ("Dropped", "dropped"),
        ("Not yet evaluated", None),
    )
    failed = (
        f"**Dreaming failed:** {plan.dream_failure} The plan does not depend on it. {RETRY}"
        if plan.dream_failure
        else ""
    )
    blocks = []
    for heading, verdict in sections:
        chosen = [_dream_block(d, titles) for d in dreams if d.verdict == verdict]
        if chosen:
            blocks.append("\n\n".join([f"## {heading}", *chosen]))
    return _page(
        "# Dreams",
        "Extensions of the idea, kept apart from the plan. Nothing here is researched.",
        failed,
        HOW_TO_CHOOSE if dreams else "",
        *(blocks or ([] if failed else ["No dreams yet: dreaming has not run for this plan."])),
    )


def _source_order(source: Source) -> tuple[int, str, str]:
    """By number, as dreams are: s10 comes after s9."""
    return (len(source.id), *_whole_record(source))


def _link_target(url: str) -> str:
    """A URL that cannot close or break the markdown link it sits in."""
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29").replace("<", "%3C").replace(">", "%3E")


def _sources_page(plan: Plan) -> str:
    titles = {t.slug: t.title for t in plan.topics}
    citing: dict[str, list[str]] = {}
    for topic in plan.topics:
        for source_id in dict.fromkeys(i for finding in topic.findings for i in finding.source_ids):
            citing.setdefault(source_id, []).append(topic.title)
    sources = [
        f"{s.id}: [{s.title}]({_link_target(s.url)})"
        + (f", cited by {', '.join(citing[s.id])}" if s.id in citing else "")
        for s in sorted(plan.sources, key=_source_order)
    ]
    blocks = [_bullets(sources, empty="No sources.")]
    unfetched = [
        f"{titles.get(r.topic, r.topic)}: {url}"
        for r in sorted(plan.research, key=lambda r: r.topic)
        for url in r.unfetched
    ]
    failed = [
        f"{titles.get(r.topic, r.topic)}: {f.url} ({f.why})"
        for r in sorted(plan.research, key=lambda r: r.topic)
        for f in r.fetches
        if not f.usable
    ]
    heuristic = (
        "Telling a usable fetch from a failed one is a heuristic: a refusal or a redirect comes back as text, "
        "not as an error, so this list reads the status and the text."
    )
    if unfetched:
        blocks.append(
            "## Cited, and not fetched with usable content\n\nA finding cited each of these, and this run holds no "
            f"usable fetch of it, so that finding is labelled an assumption. {heuristic}\n\n{_bullets(unfetched)}"
        )
    if failed:
        blocks.append(f"## Fetched, and not usable\n\n{heuristic}\n\n{_bullets(failed)}")
    return _page("# Sources", _stamp(plan), *blocks)


def furniture(plan: Plan) -> dict[str, set[str]]:
    """Per topic page, the lines it draws from anything but that topic's own words.

    A topic with its text blanked still draws them, in either state of the banner, so
    a title or a heading is not the topic saying something. A promoted topic's opening
    line stays too: it is the words a person moved, so another dream like it is no copy.
    """
    plan = Plan.model_validate(_inert(plan.model_dump()))
    blank = {"findings": [], "risks": [], "unknowns": [], "decisions": []}
    promoted = {dream.promoted_to for dream in plan.dreams}
    topics = [t.model_copy(update={**blank, "why": t.why if t.slug in promoted else ""}) for t in plan.topics]
    bare = plan.revised(topics=topics)
    return {
        _topic_file(topic.slug): {
            line for verified in (True, False) for line in _topic_page(bare, topic, verified).splitlines()
        }
        for topic in bare.topics
    }


def render(plan: Plan, runbook: str = "") -> dict[str, str]:
    """Every markdown file, by path relative to the tree. A `runbook` marks the plan unverified."""
    plan = Plan.model_validate(_inert(plan.model_dump()))
    verified = not runbook
    pages = {PLAN_FILE: _plan_page(plan, verified)}
    pages.update({_topic_file(t.slug): _topic_page(plan, t, verified) for t in plan.topics})
    pages[DREAMS_FILE] = _dreams_page(plan)
    pages[SOURCES_FILE] = _sources_page(plan)
    if runbook:
        pages[RUNBOOK_FILE] = f"{RUNBOOK_MARK}\n\n{_inert(runbook)}"
    return pages


def is_ours(path: Path) -> bool:
    """A runbook this tool wrote, read without following a link."""
    if path.is_symlink() or not path.is_file():
        return False
    return path.read_text(encoding="utf-8", errors="replace").startswith(RUNBOOK_MARK)


def _blockers(pages: dict[str, str], tree: Path) -> list[Path]:
    """What stands where a page must go: a link, dangling or not, a directory, a read-only file, a person's runbook."""
    folder = tree / TOPICS_DIR
    blocked = [folder] if folder.is_symlink() or (folder.exists() and not folder.is_dir()) else []
    for name in pages:
        path = tree / name
        if name.startswith(f"{TOPICS_DIR}/") and blocked[:1] == [folder]:
            continue
        foreign = name == RUNBOOK_FILE and path.exists() and not is_ours(path)
        read_only = path.is_file() and not os.access(path, os.W_OK)
        if path.is_symlink() or path.is_dir() or foreign or read_only:
            blocked.append(path)
    return blocked


def blocked(plan: Plan, tree: Path) -> list[Path]:
    """What would stop `plan` being drawn in `tree`, for a caller that must know before it saves."""
    return _blockers(render(plan), Path(tree))


def _clear_stale(pages: dict[str, str], tree: Path, folder_free: bool) -> None:
    """Drop a topic page the plan lost, and a runbook of ours once green. A link is never followed or removed."""
    stale = [path for path in (tree / TOPICS_DIR).glob("*.md") if f"{TOPICS_DIR}/{path.name}" not in pages]
    stale = stale if folder_free else []
    if RUNBOOK_FILE not in pages and is_ours(tree / RUNBOOK_FILE):
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
