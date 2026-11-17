"""The graph -> an ordered first few steps, each with its reason.

The model writes the reasoning and the graph constrains the choice. It is offered
every topic with its `depends-on`, so a chain still yields several steps. `apply`
refuses what a plan cannot hold, and the order is the verifier's: a step that jumps
ahead lands in the plan, goes red at `start_order`, and reaches repair.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import STEP_FIELD_WORDS, Plan, Step, Topic
from protopilot.plan.passes import BRIEF, PlanPassError, findings_block, scope_block, text, topics_block
from protopilot.plan.passes.collect import word_pattern

NAME = "start"
MAX_STEPS = 5

ORDER_RULES = """\
The order is a hard rule, and a list that breaks it fails verification:

- The first step must name a topic that depends on nothing.
- A later step may name a topic only if every topic it depends on was named by an
  earlier step.
- Never name a topic twice.
"""

SYSTEM = BRIEF + f"""
Say where to begin. Prefer whichever step retires the riskiest unknown soonest.

{ORDER_RULES}
Return an ordered list of steps, no more than you are told. Each names a topic, an
`action` someone could take soon, and a `why` that says why it comes at this point.

A step is read as a to-do, so keep each one short; the topic page holds the detail.

- `action`: one plain instruction of {STEP_FIELD_WORDS["action"]} words at most, starting with a verb.
- `why`: one sentence of {STEP_FIELD_WORDS["why"]} words at most on why it comes here.

Write both as ordinary prose, with commas, hyphens and a full stop where they belong.
Punctuation is allowed: it ends a word just as a space does, and adds none.
"""


def ready(plan: Plan) -> list[Topic]:
    """The topics with no unmet `depends-on`, before anything has been done."""
    needs = plan.needs()
    return [topic for topic in plan.topics if not needs[topic.slug]]


def _most_steps(plan: Plan) -> int:
    return min(MAX_STEPS, len(plan.topics))


def _step_text(plan: Plan, field: str) -> dict:
    """A step field's schema: held to its word cap only when the plan has no steps yet.

    Repair and promote reuse this schema and must return a healthy step word for word,
    and a step written before the cap may be longer than it. Held to the pattern, such
    a plan could not be repaired at all; there the cap is only asked for, in `SYSTEM`.
    """
    rule: dict = {"type": "string"}
    if not plan.steps:
        rule["pattern"] = word_pattern(STEP_FIELD_WORDS[field])
    return rule


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
                        "action": _step_text(plan, "action"),
                        "why": _step_text(plan, "why"),
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
    found = findings_block(plan)
    block = f"{block}\n\n{found}" if found else block
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
    known = {topic.slug for topic in plan.topics}
    for number, step in enumerate(steps, start=1):
        if step.topic not in known:
            raise ValueError(f"step {number} names a topic that does not exist: {step.topic}")
    return plan.revised(steps=steps[:MAX_STEPS])
