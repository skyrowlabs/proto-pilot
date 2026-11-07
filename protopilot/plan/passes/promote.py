"""A topic a person promoted from a dream -> connected and considered, and nothing else moved.

The new topic is always the plan's last. Its links and notes come from one call, and
every link must touch it, so what the plan had settled stays settled. A link that
breaks the order or closes a loop is the verifier's to find and repair's to mend.

Offline it depends on the dream's anchor, which is true of any extension and cannot
close a loop, and its risks, unknowns and decisions stay empty, as a person's added
topic does. Research is another pass: nothing here writes a finding.
"""

from __future__ import annotations

from protopilot.plan.model import Plan, Topic
from protopilot.plan.passes import BRIEF, connect, consider, lines, listed, scope_block, topics_block

NAME = "promote"

SYSTEM = BRIEF + """
A person has made a new topic out of an extension of this idea. Fit it into the plan.

- `edges`: how the new topic relates to the others. Every edge must have the new topic
  at one end, and the slugs you are given are the only ones to use.
  `depends-on`: `from_topic` cannot be settled until `to_topic` is.
  `informs`: `from_topic` would change how `to_topic` is thought about.
  `conflicts-with`: serving one pulls against the other.
  `depends-on` must never loop.
- `risks`: what could sink or damage this part of the idea.
- `unknowns`: questions that have to be answered, phrased as questions.
- `decisions`: choices a person must make, phrased as choices.
"""


def _new(plan: Plan) -> Topic:
    return plan.topics[-1]


def schema(plan: Plan) -> dict:
    strings = {"type": "array", "items": {"type": "string"}}
    properties = {"edges": connect.schema(plan)["properties"]["edges"], **dict.fromkeys(consider.FIELDS, strings)}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def build(plan: Plan) -> tuple[str, str]:
    links = [f"- {edge.from_topic} {edge.kind} {edge.to_topic}" for edge in plan.edges]
    new = topics_block([_new(plan)]).replace("## The topics", "## The new topic")
    held = [scope_block(plan), topics_block(plan.topics[:-1]), "## How they connect", "\n".join(links) or "No links."]
    return SYSTEM, "\n\n".join([*held, new])


def offline(plan: Plan) -> dict:
    new = _new(plan)
    anchor = next(dream.anchor for dream in plan.dreams if dream.promoted_to == new.slug)
    edge = {"from_topic": new.slug, "to_topic": anchor, "kind": "depends-on"}
    return {"edges": [edge], **dict.fromkeys(consider.FIELDS, [])}


def apply(plan: Plan, data: dict) -> Plan:
    new = _new(plan)
    rows = listed(data["edges"])
    strays = [row for row in rows if new.slug not in (row["from_topic"], row["to_topic"])]
    if strays:
        raise ValueError(f"an edge leaves out the new topic {new.slug}: {strays[0]['from_topic']}")
    connected = connect.apply(plan, {"edges": [*(edge.model_dump() for edge in plan.edges), *rows]})
    notes = {field: lines(data[field]) for field in consider.FIELDS}
    return connected.revised(topics=[*plan.topics[:-1], new.model_copy(update=notes)])
