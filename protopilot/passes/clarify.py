"""The question pass, which is also the classifier.

Runs before intake, on the raw idea. One cheap call that returns *what shape of
thing this is*, *how it should look*, and the few questions whose answers would
change what gets built — because the cheapest place to fix a misunderstanding is
before anything is generated, and an idea read wrong costs five passes, a Docker
build and a verify loop to discover.

**One call, not two.** The archetype's own fixed questions are merged in locally
from the registry, so nothing is spent asking the model to repeat what we
already wrote down. It is asked only for the two things it can see that we
cannot: which shape this idea is, and up to two questions specific enough to
this idea that no fixed set would contain them.

The answers come back typed. Fixed questions carry stable ids and land in
`spec.answers`; the model's own questions have model-invented ids and no
contract, so they go to `direction` as prose. That split is the point — it is
honest about which half has a schema, and it replaced a function that flattened
every answer into one sentence before intake ever ran.
"""

from __future__ import annotations

from protopilot import archetypes

NAME = "clarify"

SYSTEM_TEMPLATE = """\
You are about to specify a small prototype from a one-line idea. Two jobs.

## 1. Classify

Pick the archetype whose shape this idea actually is:

{menu}

`confidence` is about **fit**, not about how many options there were. Say
`low` when the idea does not really match any shape on that list -- including
when the list is short and you are picking the closest thing rather than the
right thing -- or when it genuinely could be more than one. Say `high` only
when the idea actually is the shape you named.

A list with one entry on it does not make that entry a good fit. If the only
available shape is a tracker and the idea is a board game, that is `low`, and
saying so is the most useful thing you can do: it is what tells the tool it is
building the closest honest approximation rather than the thing that was asked
for.

Also pull out any styling steer the idea already contains -- "cat themed",
"like a 1950s diner", "dark and minimal" -- into `theme`. Leave its fields
empty strings when the idea says nothing about how it should look. Do not
invent a theme nobody asked for.

## 2. Ask what you cannot already know

The archetype comes with its own fixed questions and they are already being
asked. Do NOT repeat them. Return between 0 and 2 *additional* questions, and
only if:

- different answers would produce a genuinely different spec, AND
- the idea as written does not already answer it, AND
- it is specific to THIS idea rather than to its shape.

Zero is a good answer and usually the right one. Each question gets 2 to 4
concrete suggested answers plus `recommended`. A questionnaire that asks what a
person already said is worse than no questionnaire.

## The runtime

Server-rendered HTML: FastAPI, Jinja templates, plain forms, full page loads.
No JavaScript build step, no npm, no CDN, no realtime, no 3D. A grid of squares
that submits a form per click is buildable and is how a board game works here;
an animated 3D board is not.

If the idea needs something the runtime cannot do, do not ask permission for
it -- say so in `heads_up`, one plain sentence, in the user's own words, and
classify the version that can actually be built. `heads_up` is an empty string
when the idea fits as asked.
"""


def _theme_schema() -> dict:
    fields = {
        "palette": "e.g. 'warm earth tones'. Empty string if the idea says nothing.",
        "motif": "the recurring visual idea, e.g. 'paw prints'. Empty string if none.",
        "tone": "e.g. 'playful', 'clinical'. Empty string if none.",
        "subject": "what drawn artwork should depict, e.g. 'cats and dogs'. Empty string if none.",
    }
    return {
        "type": "object",
        "properties": {k: {"type": "string", "description": v} for k, v in fields.items()},
        "required": sorted(fields),
        "additionalProperties": False,
    }


def schema() -> dict:
    """Built from the registry, so a new archetype is selectable by existing.

    `archetype` is an **enum** rather than a free string: the model then cannot
    name a shape this build does not have, which removes a whole failure mode
    instead of validating it after the fact.
    """
    return {
        "type": "object",
        "properties": {
            "archetype": {
                "type": "string",
                "enum": archetypes.names(),
                "description": "Which shape this idea is.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low"],
                "description": "`low` if the idea could genuinely be more than one shape.",
            },
            "theme": _theme_schema(),
            "heads_up": {
                "type": "string",
                "description": (
                    "One sentence on anything the idea asks for that this stack "
                    "cannot build, in the user's words. Empty if it all fits."
                ),
            },
            "questions": {
                "type": "array",
                "minItems": 0,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "short snake_case key"},
                        "question": {"type": "string"},
                        "why": {"type": "string", "description": "One clause on what the answer changes."},
                        "options": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string"}},
                        "recommended": {"type": "string"},
                    },
                    "required": ["id", "question", "why", "options", "recommended"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["archetype", "confidence", "theme", "heads_up", "questions"],
        "additionalProperties": False,
    }


def build(idea: str, direction: str = "") -> tuple[str, str]:
    system = SYSTEM_TEMPLATE.format(menu=archetypes.matches(), default=archetypes.DEFAULT)
    parts = [f"Idea: {idea}"]
    if direction.strip():
        parts.append(f"Direction the user gave: {direction.strip()}")
    return system, "\n".join(parts)


def chosen_archetype(result: dict) -> str:
    """The archetype to use, after the fallback rule.

    Low confidence lands on the default rather than on the model's best guess.
    An enum stops it naming something that does not exist; this stops it
    committing to a shape it is not sure of, which is the more common failure
    and the more expensive one -- a wrong shape is five passes of the wrong app.

    The prompt asks about **fit** rather than ambiguity, and that wording was
    bought with a live call. Asked to classify "a cat and dog themed 3d chess
    app" against a list containing only `crud`, the first version returned
    `high` -- correctly, by its own wording, since there was nothing to be
    ambiguous between. Which made the whole fallback dead code in exactly the
    case it exists for: a game confidently filed as a tracker. A one-entry list
    does not make that entry a good fit, and the prompt now says so.
    """
    name = str(result.get("archetype") or "")
    if result.get("confidence") == "low" or name not in archetypes.names():
        return archetypes.DEFAULT
    return name


def fixed_questions(archetype_name: str) -> list[dict]:
    """The archetype's own questions, as the front end renders them."""
    try:
        module = archetypes.get(archetype_name)
    except archetypes.MissingArchetype:
        module = archetypes.get(archetypes.DEFAULT)
    return [dict(q) for q in module.QUESTIONS]


def fixed_ids(archetype_name: str) -> set[str]:
    return {q["id"] for q in fixed_questions(archetype_name)}


def split_answers(archetype_name: str, answers: dict[str, str]) -> tuple[dict[str, str], str]:
    """Typed answers, and the prose leftovers.

    An answer to a question the archetype declared has a stable id and a
    consumer that reads it by name, so it belongs in `spec.answers`. An answer
    to a question the model invented has neither, so pretending it is structured
    would be a lie the type system would go on to repeat. It becomes direction.

    This replaced `answers_to_direction()`, which flattened *both* kinds into one
    sentence. Deleted rather than kept alongside: two routes from an answer to a
    pass means the typed one gets quietly bypassed.
    """
    known = fixed_ids(archetype_name)
    typed = {k: v.strip() for k, v in answers.items() if k in known and str(v).strip()}
    prose = [f"{k}: {v}".strip() for k, v in answers.items() if k not in known and str(v).strip()]
    return typed, ". ".join(prose)


def merge_direction(direction: str, extra: str) -> str:
    """Append the model-question answers to whatever steer the user typed."""
    parts = [p.strip() for p in (direction, extra) if p and p.strip()]
    return ". ".join(parts)
