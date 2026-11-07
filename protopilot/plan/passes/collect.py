"""The plan -> new dreams, one lens at a time, each with no verdict.

Lightness is the schema's job: a dream is a title, a what-if, an anchor and what it
would take, each under its share of the cap. `apply` numbers them itself, so a dream's
id is never the model's, and reads no verdict. What it stores may still be over the
cap or off the list; `dreaming.admit` says which, so one bad dream costs only itself.
"""

from __future__ import annotations

import re

from protopilot.plan import lenses as lens_data
from protopilot.plan.lenses import LENSES, Lens
from protopilot.plan.model import DREAM_FIELD_WORDS, WORD_BREAK, Dream, Plan
from protopilot.plan.passes import BRIEF, dreams_block, listed, scope_block, text, topics_block

NAME = "collect"
#: `render` writes the "What if", so a model's own would read twice.
WHAT_IF_OPENING = re.compile(r"^what if\b[\s,:-]*", re.IGNORECASE)

SYSTEM = BRIEF + f"""
Dream: say what else this idea could become. Plans narrow, and this step widens. A
dream gets less detail than a topic and wider reach, and it may ignore what is
practical. Nobody will mistake it for a plan; it is kept apart from one.

Answer each lens you are given, and let the lens change the idea rather than decorate
it. Dreams that could have come from any other lens are wasted.

- `title`: {DREAM_FIELD_WORDS["title"]} words at most.
- `what_if`: one sentence of {DREAM_FIELD_WORDS["what_if"]} words at most, finishing "What if ...".
  Leave off the words "what if".
- `takes`: a phrase of {DREAM_FIELD_WORDS["takes"]} words at most on what it would take.
- `anchor`: the slug of the topic this extends.
- `lens`: the slug of the lens it came through.

These limits are hard, and a hyphen, slash or dash ends a word just as a space does.
A dream that needs more is a topic, so cut it. No research and no phases. Do not
repeat a dream already in the pool, and do not copy the plan's own sentences.
"""


def word_pattern(most: int) -> str:
    """A JSON Schema `pattern` for text of at most `most` words, as `dream_words` counts them."""
    return f"^[^{WORD_BREAK}]+([{WORD_BREAK}]+[^{WORD_BREAK}]+){{0,{most - 1}}}$"


def next_number(dreams: list[Dream]) -> int:
    """One past the highest number in use, so an id never comes back while its dream is held."""
    return max((int(found[0]) for found in (re.findall(r"\d+", dream.id) for dream in dreams) if found), default=0) + 1


def schema(plan: Plan, lenses: tuple[Lens, ...] = LENSES, per_lens: int = 1) -> dict:
    fields = {name: {"type": "string", "pattern": word_pattern(most)} for name, most in DREAM_FIELD_WORDS.items()}
    return {
        "type": "object",
        "properties": {
            "dreams": {
                "type": "array",
                "maxItems": len(lenses) * per_lens,
                "items": {
                    "type": "object",
                    "properties": {
                        **fields,
                        "lens": {"type": "string", "enum": [lens.slug for lens in lenses]},
                        "anchor": {"type": "string", "enum": [topic.slug for topic in plan.topics]},
                    },
                    "required": [*fields, "lens", "anchor"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["dreams"],
        "additionalProperties": False,
    }


def build(plan: Plan, lenses: tuple[Lens, ...] = LENSES, per_lens: int = 1) -> tuple[str, str]:
    asked = "\n".join(f"- {lens.slug}: {lens.ask}" for lens in lenses)
    parts = [scope_block(plan), topics_block(plan.topics), f"## The lenses\n\n{asked}"]
    if plan.dreams:
        parts.append(dreams_block("Already in the pool", plan.dreams))
    return SYSTEM, "\n\n".join([*parts, f"Return {per_lens} dream(s) for each lens."])


def _template(lens: Lens, number: int, slug: str) -> dict:
    """A dream that says what it is: the twin reads no English, so it has no ideas to offer."""
    seen = lens_data.words(lens.slug)
    return {
        "title": f"Template {number}: {seen}",
        "what_if": f"a model read topic {number} through the lens {seen}? Offline mode writes no ideas, so this "
        "line is a template.",
        "lens": lens.slug,
        "anchor": slug,
        "takes": "A model backend; offline mode cannot say.",
    }


def offline(plan: Plan, lenses: tuple[Lens, ...] = LENSES, per_lens: int = 1) -> dict:
    """The next unused pairs of lens and topic, so a round grows the pool until they run out."""
    used = {(dream.lens, dream.anchor) for dream in plan.dreams}
    count, rows = len(plan.topics), []
    for offset, lens in enumerate(lenses):
        order = [(offset + step) % count for step in range(count)]
        free = [index for index in order if (lens.slug, plan.topics[index].slug) not in used]
        rows += [_template(lens, index + 1, plan.topics[index].slug) for index in free[:per_lens]]
    return {"dreams": rows}


def apply(plan: Plan, data: dict, lenses: tuple[Lens, ...] = LENSES, per_lens: int = 1) -> Plan:
    first = next_number(plan.dreams)
    rows = listed(data["dreams"])[: len(lenses) * per_lens]
    fresh = [
        Dream(
            id=f"d{first + offset}",
            title=text(row["title"]),
            what_if=text(WHAT_IF_OPENING.sub("", text(row["what_if"]))),
            lens=text(row["lens"]),
            anchor=text(row["anchor"]),
            takes=text(row["takes"]),
        )
        for offset, row in enumerate(rows)
    ]
    return plan.revised(dreams=[*plan.dreams, *fresh])
