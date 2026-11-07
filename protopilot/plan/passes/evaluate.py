"""New dreams -> four separate scores, a verdict and a sentence, and near-duplicates merged.

A second call, so nothing judges its own output. It reads every dream with no verdict
and touches no other: a dream a person has seen keeps what it has. `duplicate_of` may
name anything in the pool, which is how a set-aside or dropped dream stays unproposed.
"""

from __future__ import annotations

from protopilot.plan.model import MODEL_RATINGS, MODEL_VERDICTS, RUBRIC, TWIN_RATINGS, Dream, Plan
from protopilot.plan.passes import BRIEF, dreams_block, listed, propose, scope_block, text, topics_block

NAME = "evaluate"
#: Written by the twin in place of a judgement it cannot make.
NOT_JUDGED = "not judged"
TEMPLATE_REASON = "Offline template, so nothing judged it: the first few in lens order are shown."

SYSTEM = BRIEF + """
Judge dreams somebody else wrote: extensions of a plan, kept apart from it. Rate each
on four separate questions, as `low`, `medium` or `high`, and never combine them.

- `pull`: does it make the idea more worth doing?
- `reach`: does it open something the plan cannot?
- `cost`: how much would it take? `high` is expensive.
- `fit`: does it sit inside the stated constraints? `low` means it fights them.

Then give a `verdict`, `proposed` if a person should look at it and `set-aside` if not,
and a `reason`: one sentence saying what decided it. Be willing to set most aside.

`duplicate_of`: the id of an earlier dream, new or already in the pool, that says
nearly the same thing, or "" if there is none. Rate and judge it either way.
"""


def fresh(plan: Plan) -> list[Dream]:
    """The dreams this round collected: only those have no verdict yet."""
    return [dream for dream in plan.dreams if dream.verdict is None]


def schema(plan: Plan) -> dict:
    rating = {"type": "string", "enum": list(MODEL_RATINGS)}
    return {
        "type": "object",
        "properties": {
            "dreams": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": [dream.id for dream in fresh(plan)]},
                        **dict.fromkeys(RUBRIC, rating),
                        "verdict": {"type": "string", "enum": list(MODEL_VERDICTS)},
                        "reason": {"type": "string"},
                        "duplicate_of": {"type": "string", "enum": ["", *(dream.id for dream in plan.dreams)]},
                    },
                    "required": ["id", *RUBRIC, "verdict", "reason", "duplicate_of"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["dreams"],
        "additionalProperties": False,
    }


def build(plan: Plan) -> tuple[str, str]:
    parts = [scope_block(plan), topics_block(plan.topics, "risks", "unknowns", "decisions")]
    held = [dream for dream in plan.dreams if dream.verdict is not None]
    if held:
        parts.append(dreams_block("Already in the pool, for spotting duplicates only", held, "verdict"))
    return SYSTEM, "\n\n".join([*parts, dreams_block("The new dreams", fresh(plan), "lens", "anchor", "takes")])


def offline(plan: Plan) -> dict:
    """The twin has no taste, so it says so: order decides, and every rating reads `not judged`."""
    return {
        "dreams": [
            {
                "id": dream.id,
                **dict.fromkeys(RUBRIC, NOT_JUDGED),
                "verdict": MODEL_VERDICTS[0] if index < propose.MOST else MODEL_VERDICTS[1],
                "reason": TEMPLATE_REASON,
                "duplicate_of": "",
            }
            for index, dream in enumerate(fresh(plan))
        ]
    }


def _judged(dream: Dream, row: dict, ratings: tuple[str, ...]) -> Dream:
    if row["verdict"] not in MODEL_VERDICTS:
        raise ValueError(f"dream {dream.id} was given the verdict {row['verdict']!r}, which only a person can give")
    for field in RUBRIC:
        if row[field] not in ratings:
            raise ValueError(f"dream {dream.id} was given the {field} {row[field]!r}, which is not a rating")
    scores = {field: row[field] for field in RUBRIC}
    return dream.model_copy(update={**scores, "verdict": row["verdict"], "reason": text(row["reason"])})


def _applied(plan: Plan, data: dict, ratings: tuple[str, ...]) -> Plan:
    rows = {row["id"]: row for row in reversed(listed(data["dreams"]))}
    # A dream may merge only into one that will still be there: a dream evaluate never read will not.
    targets = {dream.id for dream in plan.dreams if dream.verdict is not None or dream.id in rows}
    merged: set[str] = set()
    kept = []
    for dream in plan.dreams:
        row = rows.get(dream.id) if dream.verdict is None else None
        if row is None:
            kept.append(dream)
        elif row["duplicate_of"] in targets - merged - {dream.id}:
            merged.add(dream.id)
        else:
            kept.append(_judged(dream, row, ratings))
    return plan.revised(dreams=kept)


def apply(plan: Plan, data: dict) -> Plan:
    return _applied(plan, data, MODEL_RATINGS)


def apply_twin(plan: Plan, data: dict) -> Plan:
    """The twin alone may say `not judged`: from a model it would be four scores missing."""
    return _applied(plan, data, TWIN_RATINGS)
