"""A red verdict -> the plan's edges and steps mended, and nothing else touched.

`apply` is `connect.apply` then `start.apply`, so repair owns what they own and
reaches no finding, source, dream or `researched`. A check on those goes to the
floor unrepaired, which is why `FIXES` is short. Slugs stay validated, and a repair
that returns a topic the plan lacks is refused.

`rejected` is the shrink guard: the plan analogue of a repair that cuts the smoke
suite. A fault is mended, never deleted, so a repair may give up only what the
failing check named in the plan repair started from, however many attempts it
takes. `worsened` keeps the floor from holding a plan worse than the one before.
Everything else is proved by verifying the whole plan again.
"""

from __future__ import annotations

import json

from protopilot.plan import render, verify
from protopilot.plan.model import Edge, Plan, Step
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
- Keep every step nothing is wrong with, word for word. Only when the list is full may
  one give way, and only to a step that a kept step depends on.

A repair that breaks those last two rules, or leaves more wrong than it found, is
thrown away.

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


def _room(entry: Plan, after: Plan) -> int:
    """The healthy steps the cap may displace: one per new step that a step in `after` waits on."""
    if len(after.steps) < start.MAX_STEPS:
        return 0
    needs = entry.needs()
    wanted = {need for step in after.steps for need in needs.get(step.topic, set())}
    return len(wanted & ({step.topic for step in after.steps} - {step.topic for step in entry.steps}))


def _healthy(plan: Plan) -> list[Step]:
    """The steps no fault names, by position: a repeat's first occurrence is one of them."""
    faulted = {fault.index for fault in verify.step_faults(plan)}
    return [step for index, step in enumerate(plan.steps) if index not in faulted]


def _steps_lost(entry: Plan, after: Plan) -> str:
    gone = [step for step in _healthy(entry) if step not in after.steps]
    kept = {step.topic for step in after.steps}
    rewritten = sorted({step.topic for step in gone if step.topic in kept})
    if rewritten:
        return f"it rewrote steps nothing was wrong with: {', '.join(rewritten)}"
    dropped = sorted({step.topic for step in gone})
    if len(dropped) > _room(entry, after):
        return f"it dropped steps nothing was wrong with: {', '.join(dropped)}"
    return ""


def rejected(entry: Plan, after: Plan) -> str:
    """Why `after` may not land, judged against the plan repair began with. Empty if it may."""
    looped = {_key(edge) for edge in verify.cycle_edges(entry)}
    lost = {_key(edge) for edge in entry.edges} - {_key(edge) for edge in after.edges}
    if lost - looped:
        return f"it removed edges on no loop: {', '.join(sorted(lost - looped))}"
    for loop in verify.loops(entry):
        links = {_key(edge) for edge in loop}
        if len(links) > 1 and links <= lost:
            return "it removed every link on the loop, and one is enough"
    return _steps_lost(entry, after)


def worsened(found: verify.PlanVerdict, after: Plan) -> str:
    """Why `after` leaves more wrong than `found` said was wrong, or an empty string."""
    left = verify.verdict(after, render.render(after)).problems
    return (
        f"it left more wrong than it found: {left} problems, up from {found.problems}" if left > found.problems else ""
    )


def changes(before: Plan, after: Plan) -> str:
    """What the repair did, from the data rather than the model's account of it. Empty if nothing."""
    was, now = {_key(edge) for edge in before.edges}, {_key(edge) for edge in after.edges}
    parts = [f"removed {key}" for key in sorted(was - now)] + [f"added {key}" for key in sorted(now - was)]
    order = [step.topic for step in after.steps]
    if order != [step.topic for step in before.steps]:
        parts.append(f"steps now {', '.join(order)}")
    was_said = {step.topic: step for step in before.steps}
    reworded = [step.topic for step in after.steps if was_said.get(step.topic, step) != step]
    if reworded:
        parts.append(f"reworded {', '.join(reworded)}")
    return "; ".join(parts)
