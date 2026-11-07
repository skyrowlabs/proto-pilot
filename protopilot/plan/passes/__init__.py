"""The plan's passes: one module per step between an idea and a rendered tree.

Each module exports:

    NAME               str
    schema(plan)       -> JSON Schema for its structured output
    build(plan)        -> (system_prompt, user_prompt)
    offline(plan)      -> dict in that shape, sliced from `baseline.build_plan`
    apply(plan, data)  -> a new Plan

A pass that takes options, as `collect` takes its lenses, takes them by keyword in
all four.

`apply` reads only the fields it names, so no pass can reach `researched`,
`sources` or a finding. Whatever it refuses reaches the job as `PlanPassError`.
"""

from __future__ import annotations

import json
from types import ModuleType

from protopilot.llm import LLM
from protopilot.plan.baseline import clean
from protopilot.plan.model import Dream, Plan, Topic

BRIEF = """\
You are one step in planning an idea, before any research has been done. You have
no sources and no tools, and nothing you write will be checked against one.

- Never present anything as found or known: no statistics, prices, laws, named
  organisations or products, and no URLs or citations.
- Write what has to be established, not what you believe the answer to be.
- The plan is stamped "not researched" and must read that way.
"""


class PlanPassError(RuntimeError):
    """A pass cannot go on, usually because of what the model returned."""


def text(value: str) -> str:
    """One line of model text, which must say something: it lands in a heading or a bullet."""
    line = clean(value)
    if not line:
        raise ValueError("a required text field is empty")
    return line


def listed(values: list) -> list:
    """`values`, refused unless a list: a string or a dict would iterate without complaint."""
    if not isinstance(values, list):
        raise ValueError(f"a field that must be a list held {type(values).__name__}")
    return values


def lines(values: list[str]) -> list[str]:
    """A list of one-line items, with the blank ones dropped."""
    return [line for line in (clean(value) for value in listed(values)) if line]


def scope_block(plan: Plan) -> str:
    """The idea and its scope, as every pass after `scope` reads them."""
    facts = {
        "idea": plan.idea,
        "goal": plan.goal,
        "audience": plan.audience,
        "horizon": plan.horizon,
        "constraints": plan.constraints,
    }
    return "## The idea and its scope\n\n```json\n" + json.dumps(facts, indent=2, ensure_ascii=False) + "\n```"


def topics_block(topics: list[Topic], *fields: str) -> str:
    """Topics as JSON, with `fields` beyond the slug, title and reason."""
    keys = ("slug", "title", "why", *fields)
    rows = [{key: getattr(topic, key) for key in keys} for topic in topics]
    return "## The topics\n\n```json\n" + json.dumps(rows, indent=2, ensure_ascii=False) + "\n```"


def dreams_block(heading: str, dreams: list[Dream], *fields: str) -> str:
    """Dreams as JSON, with `fields` beyond the id, title and what-if."""
    keys = ("id", "title", "what_if", *fields)
    rows = [{key: getattr(dream, key) for key in keys} for dream in dreams]
    return f"## {heading}\n\n```json\n" + json.dumps(rows, indent=2, ensure_ascii=False) + "\n```"


def run_pass(module: ModuleType, plan: Plan, llm: LLM, *context: str, **options: object) -> Plan:
    """Produce a pass's output and fold it into a new plan, or raise. `context` goes to `build`."""
    if llm.offline:
        data = module.offline(plan, **options)
    else:
        system, user = module.build(plan, *context, **options)
        data = llm.structured(system=system, user=user, schema=module.schema(plan, **options), label=module.NAME)
    try:
        return module.apply(plan, data, **options)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        detail = f"missing field {exc}" if isinstance(exc, KeyError) else exc
        raise PlanPassError(f"pass {module.NAME!r} returned output that cannot be used: {detail}") from exc
