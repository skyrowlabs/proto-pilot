"""A red verdict -> the plan's edges and steps mended, and nothing else touched.

`apply` is `connect.apply` then `start.apply`, so repair owns what they own and
reaches no finding, source, dream or `researched`. A check on those goes to the
floor unrepaired, which is why `FIXES` is short. Slugs stay validated, and a repair
that returns a topic the plan lacks is refused.

`rejected` is the shrink guard: the plan analogue of a repair that cuts the smoke
suite. A fault is mended, never deleted, so a repair may give up only what the
failing check named. Everything else is proved by verifying the whole plan again.
"""

from __future__ import annotations

import json

from protopilot.plan import verify
from protopilot.plan.model import Edge, Plan
from protopilot.plan.passes import BRIEF, connect, start, topics_block

NAME = "repair"
#: As `proto new`'s loop: three repairs, then the floor.
ATTEMPTS = 3
#: The checks whose subject repair owns.
FIXES = ("no_cycles", "start_order")

SYSTEM = BRIEF + f"""
A plan failed a structural check. You are told what failed, and given the plan's
links and steps. Return the complete `edges` and `steps`, changed as little as will
fix what failed. Nothing else in the plan is within your reach.

- To break a `depends-on` loop, remove or retype one link on it and keep the others.
- To fix the steps, reorder them, or add the steps they are waiting on.
- Keep every edge that is on no loop: a dependency is never removed to suit the steps.
- Keep every step nothing is wrong with.

A repair that breaks those last two rules is thrown away.

{start.ORDER_RULES}"""


def fixable(result: verify.PlanVerdict) -> list[verify.CheckResult]:
    return [check for check in result.failed if check.name in FIXES]


def failure(result: verify.PlanVerdict, rejection: str = "") -> str:
    """What `build` is told: the failing checks repair can reach, and why its last try was thrown away."""
    text = "\n\n".join(check.report() for check in fixable(result))
    return f"{text}\n\nYour last repair was thrown away: {rejection}." if rejection else text


def schema(plan: Plan) -> dict:
    properties = {
        "edges": connect.schema(plan)["properties"]["edges"],
        "steps": start.schema(plan)["properties"]["steps"],
    }
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _current(plan: Plan) -> dict:
    return {"edges": [edge.model_dump() for edge in plan.edges], "steps": [step.model_dump() for step in plan.steps]}


def build(plan: Plan, failed: str) -> tuple[str, str]:
    current = "## The plan's links and steps\n\n```json\n" + json.dumps(_current(plan), indent=2, ensure_ascii=False)
    return SYSTEM, f"## What failed\n\n{failed}\n\n{topics_block(plan.topics)}\n\n{current}\n```"


def offline(plan: Plan) -> dict:
    """The plan as it stands: the twin has no diagnostic faculty, and saying so stops the loop."""
    return _current(plan)


def apply(plan: Plan, data: dict) -> Plan:
    return start.apply(connect.apply(plan, {"edges": data["edges"]}), {"steps": data["steps"]})


def _key(edge: Edge) -> str:
    return f"{edge.from_topic} {edge.kind} {edge.to_topic}"


def rejected(before: Plan, after: Plan) -> str:
    """Why `after` may not land, or an empty string. A loop breaks with one link, never all of them."""
    looped = {_key(edge) for edge in verify.cycle_edges(before)}
    lost = {_key(edge) for edge in before.edges} - {_key(edge) for edge in after.edges}
    if lost - looped:
        return f"it removed edges on no loop: {', '.join(sorted(lost - looped))}"
    if len(looped) > 1 and looped <= lost:
        return "it removed every link on the loop, and one is enough"
    faulted = {fault.topic for fault in verify.step_faults(before)}
    dropped = {step.topic for step in before.steps} - {step.topic for step in after.steps} - faulted
    if dropped:
        return f"it dropped steps nothing was wrong with: {', '.join(sorted(dropped))}"
    return ""


def changes(before: Plan, after: Plan) -> str:
    """What the repair did, from the data rather than the model's account of it. Empty if nothing."""
    was, now = {_key(edge) for edge in before.edges}, {_key(edge) for edge in after.edges}
    parts = [f"removed {key}" for key in sorted(was - now)] + [f"added {key}" for key in sorted(now - was)]
    if before.steps != after.steps:
        parts.append(f"steps now {', '.join(step.topic for step in after.steps)}")
    return "; ".join(parts)
