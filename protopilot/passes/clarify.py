"""The question pass.

Runs before intake, on the raw idea. One cheap call that returns a few
targeted questions rather than a spec, because the cheapest place to fix a
misunderstanding is before anything is generated -- an idea read wrong costs
five passes, a Docker build and a verify loop to discover.

Deliberately small: at most four questions, each with concrete suggested
answers, each one that would actually change the spec. A questionnaire that
asks what a person already said is worse than no questionnaire.
"""

from __future__ import annotations

NAME = "clarify"

SYSTEM = """\
You are about to specify a small prototype from a one-line idea. Before that,
ask the few questions whose answers would change what gets built.

The app will be server-rendered HTML: FastAPI, Jinja templates, plain forms,
full page loads. No JavaScript, no canvas, no 3D, no drag-and-drop, no
realtime, no npm, no CDN. A grid of squares that submits a form per click is
buildable; an animated 3D board is not.

Return between 1 and 4 questions. Fewer is better. Ask a question only if:

- different answers would produce a genuinely different spec, AND
- the idea as written does not already answer it.

Good questions decide scope, the central object, or who uses it. Bad
questions ask about styling, ask what the person just told you, or ask
something you should simply decide ("should it have a database?").

Each question gets 2 to 4 concrete suggested answers, phrased as choices a
person can pick, plus `recommended` naming the one you would pick. The user
may ignore all of them and type their own.

If the idea needs something the runtime cannot do, do not ask permission for
it -- say so in `heads_up`, one plain sentence, in the user's own words, and
ask your questions about the version that can actually be built. `heads_up`
is an empty string when the idea fits as asked.
"""

SCHEMA: dict = {
    "type": "object",
    "properties": {
        "heads_up": {
            "type": "string",
            "description": (
                "One sentence on anything the idea asks for that this stack "
                "cannot build, in the user's words. Empty if it all fits."
            ),
        },
        "questions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "short snake_case key"},
                    "question": {"type": "string"},
                    "why": {
                        "type": "string",
                        "description": "One clause on what the answer changes.",
                    },
                    "options": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "recommended": {"type": "string"},
                },
                "required": ["id", "question", "why", "options", "recommended"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["heads_up", "questions"],
    "additionalProperties": False,
}


def build(idea: str, direction: str = "") -> tuple[str, str]:
    parts = [f"Idea: {idea}"]
    if direction.strip():
        parts.append(f"Direction the user gave: {direction.strip()}")
    return SYSTEM, "\n".join(parts)


def answers_to_direction(direction: str, answers: dict[str, str]) -> str:
    """Fold the answers back into the direction intake already reads.

    Appending rather than adding a new channel: `direction` is already carried
    through every pass, so answers survive to the UI pass for free. A second
    parallel field would have to be threaded through all five.
    """
    given = [f"{q}: {a}".strip() for q, a in answers.items() if str(a).strip()]
    if not given:
        return direction
    joined = ". ".join(given)
    return f"{direction}. {joined}".strip(". ").strip() if direction.strip() else joined
