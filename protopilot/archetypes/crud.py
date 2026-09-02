"""Keeping track of things: the shape most ideas actually are.

A tracker, a log, a directory, an inventory. Entities with fields, a list page,
a form, a record page. This is the archetype `proto` has always built, and
extracting it changed nothing about the output — `tests/test_crud_characterisation.py`
holds that byte for byte.

It is also the **fallback**. A classifier that is not sure should land here,
because this is the one shape that produces something usable for any idea at
all: a half-right tracker is a working app, where a half-right board game is a
page with no game on it.
"""

from __future__ import annotations

from protopilot.spec import Spec

NAME = "crud"
LABEL = "A tool for keeping track of things"
MATCHES = "a tracker, a log, an inventory, a directory, a reading list, a simple admin tool"

#: Fixed questions, with stable ids. The ids are the contract: they key
#: `spec.answers` and the passes read them by name, which is what separates
#: these from the model's own invented questions (those have no schema and go
#: to `direction`).
#:
#: Four is the ceiling and two is usually right. A questionnaire that asks what
#: a person already said is worse than no questionnaire.
QUESTIONS = (
    {
        "id": "central_thing",
        "question": "What is the one thing this app is mostly a list of?",
        "why": "It becomes the first entity, and the home page is built around it.",
        "options": [],  # free text: the answer is the user's own vocabulary
        "recommended": "",
    },
    {
        "id": "who_uses_it",
        "question": "Who is using this?",
        "why": "Decides whether records need an owner, and how much the home page explains.",
        "options": ["just me", "a few people who all see everything", "a team with separate views"],
        "recommended": "just me",
    },
    {
        "id": "what_matters_most",
        "question": "When you open it, what do you most want to see first?",
        "why": "Shapes the home page and the default sort, which is most of the felt difference.",
        "options": ["everything, newest first", "only what still needs doing", "a count or summary"],
        "recommended": "everything, newest first",
    },
)

#: Fixed files this archetype adds to the skeleton. Empty, and see
#: `archetypes/__init__.py` for why the field exists at all.
ASSETS: tuple[str, ...] = ()


def screens(spec: Spec) -> list[dict]:
    """The CRUD screen set.

    Screens are the contract the smoke tests and the routes are both generated
    from, so they need a predictable shape. A model free to invent URL
    conventions per app produces tests and routes that disagree.

    This was `baseline.standard_screens`. It lives here now because the screen
    rule is the archetype's, not the baseline's — an archetype whose pages are
    a board and a scoreboard has to be able to say so.
    """
    out: list[dict] = [{"name": "Home", "path": "/", "entity": None, "kind": "custom"}]
    for entity in spec.entities:
        title = entity.plural.replace("_", " ").capitalize()
        out += [
            {"name": title, "path": f"/{entity.plural}", "entity": entity.name, "kind": "list"},
            {
                "name": f"New {entity.name}",
                "path": f"/{entity.plural}/new",
                "entity": entity.name,
                "kind": "form",
            },
            {
                "name": f"{entity.name} detail",
                "path": f"/{entity.plural}/{{row_id}}",
                "entity": entity.name,
                "kind": "detail",
            },
        ]
    return out


def brief() -> str:
    """The fragment the routes / ui / smoke passes are given.

    Only what is true of *this shape*. Anything true of every app belongs in
    `passes/_shared.py`, which is byte-identical across passes on purpose so it
    stays a prompt-cache prefix — text that varies by archetype must not go
    there or it stops being one.
    """
    return (
        "This is a tracking tool: a small number of things, each with a few\n"
        "fields, that a person adds to and looks through. The shape is a list\n"
        "page, a form, and a record page per entity.\n"
        "\n"
        "Make the list page the one that earns its keep. It is where the app is\n"
        "actually used, so it should show enough per row to be scannable without\n"
        "opening anything, and it should look wrong when it is empty rather than\n"
        "silently blank. Prefer the user's own vocabulary for headings and\n"
        "labels: if they said 'gig', the page says Gigs, not Events."
    )


def offline(spec: Spec, ctx) -> dict:
    """Deterministic generation, with no model.

    `baseline.py` **is** this archetype's baseline — it was written before
    archetypes existed, when CRUD was the only shape there was. So this
    delegates rather than duplicating seven hundred lines, and the import is
    local because `baseline` imports this module's `screens()` for its own
    fallback.

    A second archetype does not get to do this. It writes its own.
    """
    from protopilot import baseline

    return {
        "app/models.py": baseline.models_py(spec),
        "app/seed.py": baseline.seed_py(spec),
        "app/routes.py": baseline.routes_py(spec),
        "tests/test_smoke.py": baseline.smoke_py(spec),
        **baseline.templates_for(spec),
    }
