"""A finished plan's topics: what `proto topic add` and `proto topic drop` may do to them.

A slug is a topic's identity, so everything that points at a topic names its slug. A
drop removes the topic and what pointed at it, and says what it removed. It deletes no
dream: one that extended the topic is set aside, and one the topic was promoted from
is dropped with the person's reason. The dropped topic is remembered, so adding its
title again says it was dropped, and why.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.dreaming import EARLIER
from protopilot.plan.model import Dream, DroppedTopic, Plan
from protopilot.plan.passes import outline

#: Why a dream was set aside by a drop. The person's own reason stays with the dropped topic.
TOPIC_DROPPED = "Its topic was dropped."


def _settled(dream: Dream, slug: str, reason: str) -> tuple[Dream, str]:
    """`dream` as the drop of `slug` leaves it, and a sentence if that changed it."""
    if dream.promoted_to == slug:
        ruled = dream.model_copy(update={"verdict": "dropped", "promoted_to": "", "reason": reason})
        return ruled, f"dropped dream {dream.id}, which this topic was promoted from"
    if dream.anchor == slug and dream.verdict not in ("set-aside", "dropped", "promoted"):
        earlier = f" {EARLIER.get(dream.verdict or '', 'Before')}: {dream.reason}" if dream.reason else ""
        aside = dream.model_copy(update={"verdict": "set-aside", "reason": f"{TOPIC_DROPPED}{earlier}"})
        return aside, f"set aside dream {dream.id}, because its topic was dropped"
    return dream, ""


def orphaned(before: Plan, after: Plan, slug: str) -> set[str]:
    """The sources `slug` cited in `before` that no topic of `after` cites: the ones a change left behind."""
    was = next((topic for topic in before.topics if topic.slug == slug), None)
    cited = {i for topic in after.topics for finding in topic.findings for i in finding.source_ids}
    return {i for finding in (was.findings if was else []) for i in finding.source_ids} - cited


def without_orphans(before: Plan, after: Plan, slug: str) -> Plan:
    """`after` without the sources only `slug` cited, so `sources.md` lists what a topic still rests on."""
    gone = orphaned(before, after, slug)
    return after.revised(sources=[source for source in after.sources if source.id not in gone]) if gone else after


def dropped(plan: Plan, slug: str, why: str) -> tuple[Plan, list[str]]:
    """`plan` without the topic `slug` or anything that pointed at it, and a sentence for each thing removed."""
    reason = baseline.clean(why)
    if not reason:
        raise ValueError("--why needs a reason, because what was ruled out is the expensive half")
    gone = next((topic for topic in plan.topics if topic.slug == slug), None)
    if gone is None:
        raise ValueError(f"no topic {slug!r}")
    kept = outline.drop(plan, slug)
    notes = []
    edges = [edge for edge in plan.edges if slug not in (edge.from_topic, edge.to_topic)]
    notes += [
        f"removed the link {e.from_topic} {e.kind} {e.to_topic}"
        for e in plan.edges
        if slug in (e.from_topic, e.to_topic)
    ]
    notes += [f"removed step {n}: {s.action}" for n, s in enumerate(plan.steps, start=1) if s.topic == slug]
    dreams = []
    for dream in plan.dreams:
        settled, note = _settled(dream, slug, reason)
        dreams.append(settled)
        notes += [note] if note else []
    lost = orphaned(plan, kept, slug)
    notes += [f"removed source {s.id}, which no other topic cites" for s in plan.sources if s.id in lost]
    if plan.research_of(slug) is not None:
        notes.append("left its research transcript where it is, and took its record out of the ledger")
    return (
        kept.revised(
            edges=edges,
            steps=[step for step in plan.steps if step.topic != slug],
            dreams=dreams,
            sources=[source for source in plan.sources if source.id not in lost],
            research=[record for record in plan.research if record.topic != slug],
            dropped_topics=[*plan.dropped_topics, DroppedTopic(slug=slug, title=gone.title, why=reason)],
        ),
        notes,
    )


def added(plan: Plan, title: str, why: str) -> tuple[Plan, str]:
    """`plan` with a new last topic, and what to say if a person once dropped it. It is their call to make again.

    A topic that comes back under its old slug is forgotten as dropped. One that takes a
    new slug is not, because a dream may still name the old one.
    """
    grown = outline.add(plan, title, why)
    new = grown.topics[-1]
    same = new.title.casefold()
    before = next((t for t in plan.dropped_topics if new.slug == t.slug or same == t.title.casefold()), None)
    if before is None:
        return grown, ""
    remembered = [topic for topic in plan.dropped_topics if topic.slug != new.slug]
    return grown.revised(dropped_topics=remembered), f"{before.title} was dropped before, because: {before.why}"
