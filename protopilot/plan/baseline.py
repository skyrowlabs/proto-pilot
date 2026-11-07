"""The offline twin: a generic plan built from the idea's words alone.

It cannot read English, so it claims nothing about the idea. The topics are the
ones most ideas share, every finding is labelled an assumption, there are no
sources, and `researched` stays False so the renderer stamps the document.
"""

from __future__ import annotations

import re

from protopilot.plan.model import MAX_SLUG_LENGTH, Edge, Finding, Plan, Step, Topic

#: Words that open an idea without naming it, dropped from the directory name.
FILLER = frozenset({"a", "an", "and", "build", "create", "for", "make", "of", "start", "the", "to"})
SLUG_WORDS = 4
FALLBACK_SLUG = "plan"

#: slug, title, why, findings, risk, unknown, decision. `{idea}` is filled in.
TOPICS = (
    (
        "audience",
        "Who it is for",
        'Everything else about "{idea}" rests on who it serves, and that is still a guess.',
        (
            "Someone specific wants this enough to change what they do today.",
            "The first people to use it can be reached directly.",
        ),
        "The people it is meant for do not feel the problem it answers.",
        "Who would miss this if it stopped existing?",
        "Which one group does the first version serve?",
    ),
    (
        "scope",
        "What is in and what is out",
        'Without a boundary, "{idea}" grows until it cannot be finished.',
        (
            "A much smaller version would still be worth having.",
            "Most of what could be included can wait.",
        ),
        "The first version is too large to finish.",
        "What is the smallest version someone would still choose?",
        "What is deliberately left out of the first version?",
    ),
    (
        "resources",
        "What it takes",
        'The money, time and skills behind "{idea}" decide what is realistic.',
        (
            "It can start without outside funding.",
            "The skills it needs can be found among the people already involved.",
        ),
        "It costs more to keep going than to start, and nobody planned for that.",
        "What does the first year cost in money and in hours?",
        "How much time and money is committed before it has to prove itself?",
    ),
    (
        "operations",
        "How it runs day to day",
        'Once started, "{idea}" has to keep working on an ordinary week.',
        (
            "It can run without one person doing everything.",
            "The routine work is small enough to be sustained.",
        ),
        "It depends on one person who eventually stops.",
        "What has to happen every week for this to keep working?",
        "Who is responsible when something goes wrong?",
    ),
    (
        "risks",
        "What could sink it",
        'Naming what could end "{idea}" is cheaper now than discovering it later.',
        (
            "No legal or safety requirement rules it out.",
            "Nothing already available does this well enough.",
        ),
        "A requirement nobody checked stops it after the effort is spent.",
        "What has stopped similar attempts?",
        "Which risk is accepted, and which has to be retired first?",
    ),
    (
        "first_test",
        "The cheapest way to learn",
        'A small trial of "{idea}" can answer in days what planning cannot.',
        (
            "A trial can run before anything permanent is built.",
            "The result of a trial would change what happens next.",
        ),
        "The trial is too comfortable to show anything.",
        "What result would mean stopping?",
        "What is tried first, and with whom?",
    ),
)

#: (from, kind, to). `depends-on` runs one way only, so the graph has no cycle.
EDGES = (
    ("scope", "depends-on", "audience"),
    ("resources", "depends-on", "scope"),
    ("operations", "depends-on", "resources"),
    ("first_test", "depends-on", "audience"),
    ("first_test", "informs", "risks"),
    ("risks", "informs", "scope"),
    ("scope", "conflicts-with", "resources"),
)

#: In order, each one depending only on topics before it.
STEPS = (
    (
        "audience",
        "Name the people this is for, and talk to a few of them.",
        "It depends on nothing, and all else rests on it.",
    ),
    ("first_test", "Design the smallest trial those people could take part in.", "It tests the biggest guess soonest."),
    ("scope", "Write down what the first version leaves out.", "The trial's result is what makes that boundary real."),
)


def clean(text: str) -> str:
    """Collapse all whitespace, so one idea has one spelling on every run."""
    return " ".join(text.split())


def slug_for(idea: str) -> str:
    """A snake_case directory name, always valid whatever the idea contains."""
    words = [w for w in re.findall(r"[a-z0-9]+", idea.lower()) if w not in FILLER][:SLUG_WORDS]
    if not words:
        return FALLBACK_SLUG
    slug = "_".join(words)
    slug = slug if slug[0].isalpha() else f"{FALLBACK_SLUG}_{slug}"
    return slug[:MAX_SLUG_LENGTH].rstrip("_")


def _topic(idea: str, slug: str, title: str, why: str, findings, risk: str, unknown: str, decision: str) -> Topic:
    return Topic(
        slug=slug,
        title=title,
        why=why.format(idea=idea),
        findings=[Finding(text=text, assumption=True) for text in findings],
        risks=[risk],
        unknowns=[unknown],
        decisions=[decision],
    )


def build_plan(idea: str, direction: str = "") -> Plan:
    idea, direction = clean(idea), clean(direction)
    return Plan(
        slug=slug_for(idea),
        title=idea[:1].upper() + idea[1:],
        idea=idea,
        direction=direction,
        goal=f"Decide whether this idea is worth pursuing: {idea}",
        constraints=[direction] if direction else [],
        topics=[_topic(idea, *row) for row in TOPICS],
        edges=[Edge(from_topic=a, kind=kind, to_topic=b) for a, kind, b in EDGES],
        steps=[Step(topic=topic, action=action, why=why) for topic, action, why in STEPS],
    )
