"""Idea -> goal, audience, horizon, constraints and up to three questions.

The `clarify` analogue. Answers are prose, as a model-invented question's are in
`clarify.split_answers`, but they land in `constraints` rather than `direction`:
`existing_plan` compares `direction` with what was typed, so writing to it would
make a plan refuse its own command.

What the person stated in the brief is theirs too. The model is shown it and asked
only for the blanks; `apply` puts each stated field back over whatever came back, so
a goal the person typed is the plan's goal whether or not the model repeated it.
"""

from __future__ import annotations

from protopilot.plan import baseline
from protopilot.plan.model import Brief, Depth, Plan
from protopilot.plan.passes import BRIEF, lines

NAME = "scope"
MAX_QUESTIONS = 3

SYSTEM = BRIEF + """
Read a one-line idea and say what planning it would have to serve.

- `goal`: what a finished plan should let someone decide or do.
- `audience`: who the idea is for. An empty string if the idea does not say.
- `horizon`: the span the plan covers. An empty string if the idea does not say.
- `constraints`: only limits the idea or the direction actually state.

Where the person stated a field, return it unchanged: it is theirs, not yours to
improve. Leave out of `constraints` anything they stated as a must-have or placed
out of scope: both are already recorded, and a constraint that restates one is the
same line twice. Never ask a question their brief already answers, and never plan
for anything they placed out of scope.

Return between 0 and 3 `questions`, and only if different answers would produce a
genuinely different topic list and the idea does not already answer them. Zero is
a good answer and usually the right one.
"""


def seed(idea: str, direction: str, depth: Depth | None, brief: Brief | None = None) -> Plan:
    """The plan before any pass: names, the idea and the brief, which no model gets to choose."""
    plan = baseline.build_plan(idea, direction)
    cleared = {"goal": "", "constraints": [], "topics": [], "edges": [], "steps": []}
    return plan.revised(**cleared, depth=depth, brief=brief or Brief())


def schema(plan: Plan) -> dict:
    return {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "audience": {"type": "string"},
            "horizon": {"type": "string"},
            "constraints": {"type": "array", "items": {"type": "string"}},
            "questions": {"type": "array", "minItems": 0, "maxItems": MAX_QUESTIONS, "items": {"type": "string"}},
        },
        "required": ["goal", "audience", "horizon", "constraints", "questions"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    parts = [f"Idea: {plan.idea}"]
    if plan.direction:
        parts.append(f"Direction the user gave: {plan.direction}")
    stated = plan.brief
    parts += [f"Goal the user stated: {stated.goal}"] if stated.goal else []
    parts += [f"Audience the user stated: {stated.audience}"] if stated.audience else []
    parts += [f"Horizon the user stated: {stated.horizon}"] if stated.horizon else []
    parts += [f"Must-have the user stated: {item}" for item in stated.must]
    parts += [f"Out of scope, as the user stated: {item}" for item in stated.out]
    return SYSTEM, "\n".join(parts)


def offline(plan: Plan) -> dict:
    whole = baseline.build_plan(plan.idea, plan.direction)
    return {
        "goal": whole.goal,
        "audience": whole.audience,
        "horizon": whole.horizon,
        "constraints": whole.constraints,
        "questions": whole.questions,
    }


def apply(plan: Plan, data: dict) -> Plan:
    # The direction and the brief stay whatever came back: they are the person's, not the model's.
    brief = plan.brief
    stated = [plan.direction] if plan.direction else []
    return plan.revised(
        goal=brief.goal or baseline.clean(data["goal"]),
        audience=brief.audience or baseline.clean(data["audience"]),
        horizon=brief.horizon or baseline.clean(data["horizon"]),
        constraints=list(dict.fromkeys([*stated, *brief.must, *lines(data["constraints"])])),
        questions=lines(data["questions"])[:MAX_QUESTIONS],
    )


def answered(plan: Plan, answers: dict[str, str]) -> Plan:
    """Move each answered question into `constraints`; the rest stay open."""
    given = {question: baseline.clean(answer) for question, answer in answers.items() if baseline.clean(answer)}
    return plan.revised(
        constraints=[*plan.constraints, *(f"{question} {answer}" for question, answer in given.items())],
        questions=[question for question in plan.questions if question not in given],
    )
