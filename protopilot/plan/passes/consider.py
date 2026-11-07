"""Each topic -> its risks, its unknowns, and the decisions someone must make.

One call for the whole plan, not one per topic: the topics are short, and seeing
them together is what stops every topic reporting the same risk.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import Plan
from protopilot.plan.passes import BRIEF, findings_block, lines, scope_block, topics_block

NAME = "consider"
FIELDS = ("risks", "unknowns", "decisions")

SYSTEM = BRIEF + """
For every topic in a plan, say what could go wrong, what nobody knows yet, and
what someone will have to decide.

- `risks`: what could sink or damage this part of the idea.
- `unknowns`: questions that have to be answered, phrased as questions.
- `decisions`: choices a person must make, phrased as choices.

Return one entry per topic, with its slug, and use only the slugs you are given.
"""


def schema(plan: Plan) -> dict:
    strings = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string", "enum": [topic.slug for topic in plan.topics]},
                        **dict.fromkeys(FIELDS, strings),
                    },
                    "required": ["slug", *FIELDS],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["topics"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    connections = [f"- {e.from_topic} {e.kind} {e.to_topic}" for e in plan.edges]
    blocks = [scope_block(plan), topics_block(plan.topics), findings_block(plan)]
    return SYSTEM, "\n\n".join(
        [*(block for block in blocks if block), "## How they connect", "\n".join(connections) or "No links."]
    )


def offline(plan: Plan) -> dict:
    """The baseline's rows; a topic a person added has none, and stays empty."""
    rows = {topic.slug: topic for topic in baseline.build_plan(plan.idea, plan.direction).topics}
    empty = dict.fromkeys(FIELDS, [])
    return {
        "topics": [
            {"slug": t.slug, **({f: getattr(rows[t.slug], f) for f in FIELDS} if t.slug in rows else empty)}
            for t in plan.topics
        ]
    }


def apply(plan: Plan, data: dict) -> Plan:
    slugs = [row["slug"] for row in data["topics"]]
    known = [topic.slug for topic in plan.topics]
    if sorted(slugs) != sorted(known):
        raise ValueError(f"wanted one entry for each of {', '.join(known)}; got {', '.join(slugs) or 'none'}")
    rows = {row["slug"]: row for row in data["topics"]}
    topics = [t.model_copy(update={f: lines(rows[t.slug][f]) for f in FIELDS}) for t in plan.topics]
    return plan.revised(topics=topics)
