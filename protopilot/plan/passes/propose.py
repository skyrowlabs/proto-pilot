"""The shortlist -> the top few, each saying what would change if adopted.

A third call. It may only choose among what `evaluate` proposed, so it cannot rescue
what was set aside, and whatever it leaves out is set aside with evaluate's reason.
"""

from __future__ import annotations

from protopilot.plan.model import Dream, Plan
from protopilot.plan.passes import BRIEF, dreams_block, listed, scope_block, text, topics_block

NAME = "propose"
#: The top few of a round. A longer list is one nobody reads to the end.
MOST = 3
PASSED_OVER = f"A round proposes at most {MOST}, and this was not among them."
TEMPLATE_IF_ADOPTED = "Nothing: a template proposes no change. Run with a model to dream."

SYSTEM = BRIEF + f"""
A shortlist of dreams has been judged. Choose the few most worth a person's attention,
{MOST} at most, and fewer if the rest do not earn it.

For each one you choose, `if_adopted` says in one or two sentences what would change in
this plan: which topics, which first steps, what stops being true. Say what would
change, not why it is good, and write it fresh rather than repeating the plan's words.
"""


def shortlist(plan: Plan) -> list[Dream]:
    """What `evaluate` proposed this round: nothing else is proposed and lacks `if_adopted`."""
    return [dream for dream in plan.dreams if dream.verdict == "proposed" and not dream.if_adopted]


def schema(plan: Plan) -> dict:
    return {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "maxItems": MOST,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": [dream.id for dream in shortlist(plan)]},
                        "if_adopted": {"type": "string"},
                    },
                    "required": ["id", "if_adopted"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["proposals"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    choices = dreams_block(
        "The shortlist", shortlist(plan), "anchor", "takes", "pull", "reach", "cost", "fit", "reason"
    )
    return SYSTEM, "\n\n".join([scope_block(plan), topics_block(plan.topics), choices])


def offline(plan: Plan) -> dict:
    return {"proposals": [{"id": d.id, "if_adopted": TEMPLATE_IF_ADOPTED} for d in shortlist(plan)[:MOST]]}


def apply(plan: Plan, data: dict) -> Plan:
    open_ids = {dream.id for dream in shortlist(plan)}
    chosen: dict[str, str] = {}
    for row in listed(data["proposals"]):
        if row["id"] not in open_ids:
            raise ValueError(f"{row['id']!r} is not on the shortlist")
        chosen.setdefault(row["id"], text(row["if_adopted"]))
    picked = dict(list(chosen.items())[:MOST])

    def settled(dream: Dream) -> Dream:
        if dream.id in picked:
            return dream.model_copy(update={"if_adopted": picked[dream.id]})
        if dream.id in open_ids:
            return dream.model_copy(update={"verdict": "set-aside", "reason": f"{dream.reason} {PASSED_OVER}"})
        return dream

    return plan.revised(dreams=[settled(dream) for dream in plan.dreams])
