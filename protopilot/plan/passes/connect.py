"""The reviewed outline -> typed edges between its topics.

It runs after research, so links rest on findings where research found any. A plan
made without research is linked from the outline alone, and the prompt says so.
"""

from __future__ import annotations

from typing import get_args

from protopilot.plan import baseline
from protopilot.plan.model import Edge, EdgeKind, Plan
from protopilot.plan.passes import BRIEF, findings_block, listed, scope_block, topics_block

NAME = "connect"

SYSTEM = BRIEF + """
Say how the topics of a plan relate. You have their names and reasons, and any
findings research made, so record what follows from those and leave out what would
need more evidence.

- `depends-on`: `from_topic` cannot be settled until `to_topic` is.
- `informs`: `from_topic` would change how `to_topic` is thought about.
- `conflicts-with`: serving one pulls against the other.

`depends-on` must never loop, and at least one topic must depend on nothing.
Use only the slugs you are given.
"""


def schema(plan: Plan) -> dict:
    slugs = {"type": "string", "enum": [topic.slug for topic in plan.topics]}
    return {
        "type": "object",
        "properties": {
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_topic": slugs,
                        "to_topic": slugs,
                        "kind": {"type": "string", "enum": list(get_args(EdgeKind))},
                    },
                    "required": ["from_topic", "to_topic", "kind"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["edges"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    blocks = [scope_block(plan), topics_block(plan.topics), findings_block(plan)]
    return SYSTEM, "\n\n".join(block for block in blocks if block)


def offline(plan: Plan) -> dict:
    """The baseline's edges between the topics that survived the review."""
    kept = {topic.slug for topic in plan.topics}
    edges = baseline.build_plan(plan.idea, plan.direction).edges
    return {"edges": [e.model_dump() for e in edges if {e.from_topic, e.to_topic} <= kept]}


def apply(plan: Plan, data: dict) -> Plan:
    rows = [Edge(from_topic=r["from_topic"], to_topic=r["to_topic"], kind=r["kind"]) for r in listed(data["edges"])]
    edges = list({(e.from_topic, e.to_topic, e.kind): e for e in rows}.values())
    known = {topic.slug for topic in plan.topics}
    for edge in edges:
        unknown = sorted({edge.from_topic, edge.to_topic} - known)
        if unknown:
            raise ValueError(f"an edge names topics that do not exist: {', '.join(unknown)}")
        if edge.from_topic == edge.to_topic:
            raise ValueError(f"an edge joins {edge.from_topic!r} to itself")
    if known <= {edge.from_topic for edge in edges if edge.kind == "depends-on"}:
        raise ValueError("every topic depends on another, so `depends-on` has a cycle and nothing can go first")
    return plan.revised(edges=edges)
