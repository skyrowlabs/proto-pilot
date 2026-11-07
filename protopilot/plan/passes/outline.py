"""Scope -> the topics, at the count `--depth` asked for, and the human checkpoint.

The review stays here because a topic list can be read in thirty seconds and a
finished document cannot. `add`, `drop` and `rename` are the review's edits; each
raises `ValueError` with a sentence for the person making it. A rename changes
the title alone: the slug is the topic's identity, and every later pass keys on it.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import DEFAULT_DEPTH, MAX_TOPICS, MIN_TOPICS, TOPIC_COUNTS, Plan, Topic
from protopilot.plan.passes import BRIEF, scope_block, text

NAME = "outline"

SYSTEM = BRIEF + """
Break an idea into the deeper topics someone would have to think through before
acting on it. Choose topics specific to this idea, not headings any idea could use.

- `slug` is snake_case, starts with a letter, and becomes a file name.
- `title` is a few words a person would recognise.
- `why` is one line on why this topic matters to this idea.

Return exactly the number of topics you are asked for.
"""


def topic_count(plan: Plan) -> int:
    return TOPIC_COUNTS[plan.depth or DEFAULT_DEPTH]


def schema(plan: Plan) -> dict:
    fields = ("slug", "title", "why")
    return {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "minItems": topic_count(plan),
                "maxItems": topic_count(plan),
                "items": {
                    "type": "object",
                    "properties": {field: {"type": "string"} for field in fields},
                    "required": list(fields),
                    "additionalProperties": False,
                },
            },
        },
        "required": ["topics"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    return SYSTEM, f"{scope_block(plan)}\n\nReturn exactly {topic_count(plan)} topics."


def offline(plan: Plan) -> dict:
    whole = baseline.build_plan(plan.idea, plan.direction)
    return {"topics": [{"slug": t.slug, "title": t.title, "why": t.why} for t in whole.topics]}


def apply(plan: Plan, data: dict) -> Plan:
    rows = data["topics"]
    if len(rows) != topic_count(plan):
        raise ValueError(f"{len(rows)} topics, and {topic_count(plan)} were asked for")
    return plan.revised(topics=[Topic(slug=r["slug"], title=text(r["title"]), why=text(r["why"])) for r in rows])


def with_assumptions(plan: Plan) -> Plan:
    """The baseline's findings, all assumptions. Only an offline run has any before research."""
    findings = {topic.slug: topic.findings for topic in baseline.build_plan(plan.idea, plan.direction).topics}
    return plan.revised(topics=[t.model_copy(update={"findings": findings[t.slug]}) for t in plan.topics])


def _find(plan: Plan, which: str) -> Topic:
    """A topic by its number in the summary, or by its slug."""
    for number, topic in enumerate(plan.topics, start=1):
        if which in (str(number), topic.slug):
            return topic
    raise ValueError(f"no topic {which!r}; use a number from the list, or a slug")


def addable(plan: Plan, title: str) -> str:
    """The slug `title` would take, or a refusal: what can be said before asking why it matters."""
    if len(plan.topics) >= MAX_TOPICS:
        raise ValueError(f"an outline holds at most {MAX_TOPICS} topics; drop one first")
    if not baseline.clean(title):
        raise ValueError("a topic needs a title and a line on why it matters")
    slug = baseline.slug_for(baseline.clean(title))
    if any(topic.slug == slug for topic in plan.topics):
        raise ValueError(f"there is already a topic {slug!r}")
    return slug


def add(plan: Plan, title: str, why: str) -> Plan:
    slug = addable(plan, title)
    if not baseline.clean(why):
        raise ValueError("a topic needs a title and a line on why it matters")
    topic = Topic(slug=slug, title=baseline.clean(title), why=baseline.clean(why))
    return plan.revised(topics=[*plan.topics, topic])


def drop(plan: Plan, which: str) -> Plan:
    if len(plan.topics) <= MIN_TOPICS:
        raise ValueError(f"an outline holds at least {MIN_TOPICS} topics; add one first")
    gone = _find(plan, which)
    return plan.revised(topics=[topic for topic in plan.topics if topic is not gone])


def rename(plan: Plan, which: str, title: str) -> Plan:
    target, title = _find(plan, which), baseline.clean(title)
    if not title:
        raise ValueError("a topic needs a title")
    return plan.revised(
        topics=[t.model_copy(update={"title": title}) if t is target else t for t in plan.topics],
    )
