"""The graph -> an ordered first few steps, each with its reason.

The model writes the reasoning and the graph constrains the choice. It is shown
only `ready` topics. `apply` then walks the steps, twin's included: a step needs
every topic it depends on covered by an earlier step, so a first step must be
ready, and the baseline's later steps may build on the ones before them.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import Plan, Step, Topic
from protopilot.plan.passes import BRIEF, PlanPassError, scope_block, text, topics_block

NAME = "start"
MAX_STEPS = 5

SYSTEM = BRIEF + """
Say where to begin. You are given only the topics that depend on nothing, so every
one of them can be started now. Prefer whichever retires the riskiest unknown soonest.

Return an ordered 1 to 5 steps. Each names one of those topics, an `action` someone
could take this week, and a `why` that says why it comes at this point.
"""


def _needs(plan: Plan) -> dict[str, set[str]]:
    """Each topic's `depends-on` targets. `connect` has already refused a dangling edge."""
    needs: dict[str, set[str]] = {topic.slug: set() for topic in plan.topics}
    for edge in plan.edges:
        if edge.kind == "depends-on" and edge.from_topic in needs:
            needs[edge.from_topic].add(edge.to_topic)
    return needs


def ready(plan: Plan) -> list[Topic]:
    """The topics with no unmet `depends-on`, before anything has been done."""
    needs = _needs(plan)
    return [topic for topic in plan.topics if not needs[topic.slug]]


def schema(plan: Plan) -> dict:
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_STEPS,
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "enum": [topic.slug for topic in ready(plan)]},
                        "action": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["topic", "action", "why"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    topics = ready(plan)
    if not topics:
        raise PlanPassError("every topic depends on another, so `depends-on` has a cycle and nothing can go first")
    return SYSTEM, f"{scope_block(plan)}\n\n{topics_block(topics, 'risks', 'unknowns')}"


def offline(plan: Plan) -> dict:
    """The baseline's steps on the topics that survived the review, or else the first ready one."""
    kept = {topic.slug for topic in plan.topics}
    steps = baseline.build_plan(plan.idea, plan.direction).steps
    rows = [step.model_dump() for step in steps if step.topic in kept]
    first = ready(plan)[0]
    return {"steps": rows or [{"topic": first.slug, "action": f"Begin on {first.title}.", "why": first.why}]}


def apply(plan: Plan, data: dict) -> Plan:
    steps = [Step(topic=r["topic"], action=text(r["action"]), why=text(r["why"])) for r in data["steps"]]
    if not steps:
        raise ValueError("no steps, and a plan has to say where to begin")
    needs = _needs(plan)
    covered: set[str] = set()
    for number, step in enumerate(steps, start=1):
        if step.topic not in needs:
            raise ValueError(f"step {number} names a topic that does not exist: {step.topic}")
        waiting = sorted(needs[step.topic] - covered)
        if waiting:
            raise ValueError(
                f"step {number} ({step.topic}) waits on {', '.join(waiting)}, which no earlier step covers"
            )
        covered.add(step.topic)
    return plan.revised(steps=steps[:MAX_STEPS])
