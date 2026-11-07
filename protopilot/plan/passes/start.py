"""The graph -> an ordered first few steps, each with its reason.

The model writes the reasoning and the graph constrains the choice. It is offered
every topic with its `depends-on`, so a chain still yields several steps. `apply`
then walks the steps, twin's included: a step needs every topic it depends on
covered by an earlier step, so a first step must be ready, and a repeat is refused.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import Plan, Step, Topic
from protopilot.plan.passes import BRIEF, PlanPassError, scope_block, text, topics_block

NAME = "start"
MAX_STEPS = 5

SYSTEM = BRIEF + """
Say where to begin. Prefer whichever step retires the riskiest unknown soonest.

The order is a hard rule, and a list that breaks it is refused:

- The first step must name a topic that depends on nothing.
- A later step may name a topic only if every topic it depends on was named by an
  earlier step.
- Never name a topic twice.

Return an ordered list of steps, no more than you are told. Each names a topic, an
`action` someone could take soon, and a `why` that says why it comes at this point.
"""


def ready(plan: Plan) -> list[Topic]:
    """The topics with no unmet `depends-on`, before anything has been done."""
    needs = plan.needs()
    return [topic for topic in plan.topics if not needs[topic.slug]]


def _most_steps(plan: Plan) -> int:
    return min(MAX_STEPS, len(plan.topics))


def schema(plan: Plan) -> dict:
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": _most_steps(plan),
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "enum": [topic.slug for topic in plan.topics]},
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
    if not ready(plan):
        raise PlanPassError("every topic depends on another, so `depends-on` has a cycle and nothing can go first")
    needs = plan.needs()
    waits = [f"- {t.slug} depends on: {', '.join(sorted(needs[t.slug])) or 'nothing'}" for t in plan.topics]
    block = topics_block(plan.topics, "risks", "unknowns")
    graph = "## What each topic depends on\n\n" + "\n".join(waits)
    return SYSTEM, f"{scope_block(plan)}\n\n{block}\n\n{graph}\n\nReturn at most {_most_steps(plan)} steps."


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
    needs = plan.needs()
    covered: set[str] = set()
    for number, step in enumerate(steps, start=1):
        if step.topic not in needs:
            raise ValueError(f"step {number} names a topic that does not exist: {step.topic}")
        if step.topic in covered:
            raise ValueError(f"step {number} ({step.topic}) repeats a topic")
        waiting = sorted(needs[step.topic] - covered)
        if waiting:
            raise ValueError(
                f"step {number} ({step.topic}) waits on {', '.join(waiting)}, which no earlier step covers"
            )
        covered.add(step.topic)
    return plan.revised(steps=steps[:MAX_STEPS])
