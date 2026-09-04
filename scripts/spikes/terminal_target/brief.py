"""The Textual + SQLite prompt material: the analogue of `passes/_shared.py`.

`TUI_BRIEF` is byte-identical across passes and across repair attempts for the
same reason `STACK_BRIEF` is, and the reason survives the change of backend:
`ClaudeCodeLLM` sends the system text as the head of the user turn, so anything
interpolated per pass moves the boundary of what could be cached and changes
what the model is reading between passes. A brief that varies per pass is also
a brief nobody can quote in a report.

Everything that varies -- the spec, the archetype fragment, the source of the
previous pass -- goes in the user message, exactly as it does on the web side.

**This is spike material, not a target package.** Phase 2 of
`docs/TODO/terminal-target.md` is where a `protopilot/targets/` seam is decided,
and it is gated on what these prompts measure. Nothing here is imported by
`protopilot/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Tuple

from protopilot.passes._shared import FILES_SCHEMA, visible_spec

#: The five paths the model may write, and the terminal counterpart of
#: `files.WRITABLE`. Enforced by `writer.check_path`, before anything reaches
#: disk, for the same reason: model output is data, not authority.
WRITABLE = (
    "app/models.py",
    "app/screens.py",
    "app/seed.py",
    "app/widgets.py",
    "app/app.tcss",
    "tests/test_smoke.py",
)

#: Under a writable glob but skeleton. Empty here, and named rather than
#: omitted, so the shape matches `files.PROTECTED` and a later addition is a
#: value in a tuple.
PROTECTED: Tuple[str, ...] = ()


TUI_BRIEF = """\
You are generating one slice of a prototype terminal application. The rest of
the application already exists and is fixed. Work within it exactly.

## The fixed skeleton (you cannot change any of this)

- Textual (the Python TUI framework) over SQLAlchemy 2.0 (typed `Mapped[...]`
  / `mapped_column`) and a single SQLite file. Python 3.11+.
- It is ONE process. There is no server, no port, no container, no second
  service, and no Postgres. The whole application is `python -m app.main` in a
  terminal, and the database is a file beside it.
- There is NO web page anywhere. No HTML, no Jinja, no CSS, no JavaScript, no
  SVG, no browser. The screen is a terminal: rows of cells, a fixed set of
  widgets, and a keyboard.
- There are NO migrations. `Base.metadata.create_all()` runs when the app
  mounts and the database file is created if it is missing.

Modules you import from, which already exist:

- `app.db`      -> `Base`, `engine`, `SessionLocal`, and `session()`, a
                   context manager yielding a `Session`:
                   `with session() as db: ...`.
- `app.base`    -> `AppScreen`, the base class every screen subclasses. It
                   binds `q` to quit and `escape` to go back, and provides
                   `self.db()`, a context manager yielding a `Session`. It does
                   NOT compose anything for you: your screen's `compose()`
                   yields its own `Header()` and `Footer()`.
- `app.main`    -> `TerminalApp`, the `App` subclass. It creates the tables,
                   calls `seed(db)`, and pushes `HomeScreen()` from
                   `app.screens`. You do not write any of it, and `HomeScreen`
                   is the one screen name it hard-codes: `app/screens.py` must
                   define a class with exactly that name.
- `app.models`  -> the generated model classes.

Third-party packages available to import, beyond Textual and SQLAlchemy:

- `rich` (Textual's own dependency) -> `rich.text.Text`, `rich.table.Table`.
  Nothing else is installed, and you cannot add a dependency: a pass that
  needs a package which is not listed here has no way to get one. There is no
  outbound network access at any point.

## What a screen looks like

Textual widgets you may use, and no others: `Header`, `Footer`, `Static`,
`Label`, `Button`, `Input`, `TextArea`, `Checkbox`, `Select`, `DataTable`,
`ListView`, `ListItem`, `Tree`, `Markdown`, `Rule`, `Digits`, `ProgressBar`,
and the containers `Container`, `Vertical`, `Horizontal`, `VerticalScroll`,
`HorizontalScroll`, `Grid`.

- A screen is a `class SomethingScreen(AppScreen)` with a `compose()` method
  yielding widgets, and handler methods for the events it cares about --
  `on_button_pressed`, `on_input_submitted`, `on_data_table_row_selected`,
  `on_list_view_selected`, and `action_*` methods bound to keys through
  `BINDINGS`.
- Navigation is `self.app.push_screen(OtherScreen(row_id))` and
  `self.app.pop_screen()`. There are no URLs. The spec calls its pages
  "screens" and gives each one a `path` -- read that path as the screen's
  stable identifier, not as an address; nothing fetches it.
- Every widget you intend to look up later gets an `id=`. Query with
  `self.query_one("#thing", Input)`, and pass the type so the value you read
  back is the type you think it is.
- Reading and writing the database happens inside `with self.db() as db:` in a
  handler, never at import time and never in `compose()` -- `compose()` runs
  before the app is mounted and an exception there takes the whole app down
  with a traceback instead of a screen.
- After a write, refresh what is on screen from the database rather than
  patching the widget: clear the `DataTable` and re-add its rows. A terminal
  app has no page reload, and a table that disagrees with the database is the
  single most common way a generated TUI looks broken.

## Hard rules

1. Return COMPLETE file contents. Never a diff, never an ellipsis, never
   "... rest unchanged". Each file you return replaces its predecessor whole.
2. Write ONLY the paths you are told you may write. A path outside that list
   is rejected and the pass fails.
3. Every model class has a `display` property returning a short human label;
   screens and list rows use `row.display`.
4. Code must be importable at module scope with no side effects beyond
   defining things. In particular, no widget may be constructed at import
   time.
5. This is a prototype. Prefer the obvious implementation. No caching layers,
   no abstract base classes, no reactive attributes where a method call would
   do, no premature pagination. Do not add auth unless the spec asks for it.
"""


#: The archetype fragment, in this medium.
#:
#: `archetypes.brief_for()` cannot be reused here and that is a finding rather
#: than an inconvenience: both shipped fragments are written in web -- "in the
#: same browser", "a grid of plain submit buttons inside one form", "draw the
#: pieces as inline SVG". Handing either to a Textual pass would measure the
#: model's ability to ignore a contradiction, not its ability to write a
#: terminal app. So each archetype gets a terminal rewrite of the SAME content,
#: kept as close to the original sentence for sentence as the medium allows.
#:
#: What this costs the plan is in the report: `docs/TODO/terminal-target.md`
#: Phase 2 lists four things a target owns, and the archetype brief is a fifth.
TUI_ARCHETYPE_BRIEFS = {
    "crud": (
        "This is a tracking tool: a small number of things, each with a few\n"
        "fields, that a person adds to and looks through. The shape is a list\n"
        "screen, a form screen, and a record screen per entity.\n"
        "\n"
        "Make the list screen the one that earns its keep. It is where the app\n"
        "is actually used, so its `DataTable` should show enough per row to be\n"
        "scannable without opening anything, and it should say something when\n"
        "it is empty rather than showing an empty table. Prefer the user's own\n"
        "vocabulary for headings and labels: if they said 'gig', the screen\n"
        "says Gigs, not Events."
    ),
    "turn-based-game": (
        "This is a turn-based game two people play at one screen, taking turns\n"
        "at the same terminal. The centre of the app is the board screen.\n"
        "\n"
        "Build the board as a `Grid` of `Button` widgets, one button per\n"
        "square, each carrying the square it represents in its `id`. Pressing a\n"
        "button is a move; the screen redraws from the database after every\n"
        "one. That is the whole interaction model -- no mouse dragging, no\n"
        "animation, no timer.\n"
        "\n"
        "Draw the pieces as text. A piece is one or two characters -- a letter,\n"
        "or a Unicode glyph from the chess and playing-card blocks -- with the\n"
        "two sides told apart by colour through the stylesheet, never by shape\n"
        "alone. There is no SVG here and no image file; the terminal cell is\n"
        "the only thing you can draw in.\n"
        "\n"
        "State lives in one row: the board as a string, whose turn it is, and\n"
        "whether anyone has won. Never in an attribute on the screen, never in\n"
        "a module global -- quitting and restarting must show the same game.\n"
        "\n"
        "The board screen must say whose turn it is and announce a win when\n"
        "there is one."
    ),
}


def spec_block(spec) -> str:
    """The spec, rendered for a prompt.

    A deliberate mirror of `passes._shared.spec_block` -- same JSON, same
    human summary, same `PASS_HIDDEN` fields dropped -- differing in exactly
    one place: the archetype fragment comes from `TUI_ARCHETYPE_BRIEFS`. If
    this drifts from the web version in any other way the measurement stops
    comparing two targets and starts comparing two prompt styles.
    """
    visible = visible_spec(spec)
    parts = [
        "## The spec\n\n```json\n"
        + json.dumps(visible.model_dump(mode="json"), indent=2)
        + "\n```\n\n"
        + visible.summary()
    ]
    fragment = TUI_ARCHETYPE_BRIEFS.get(getattr(spec, "archetype", "") or "crud", "")
    if fragment:
        parts.append("## What kind of thing this is\n\n" + fragment)
    return "\n\n".join(parts)


@dataclass(frozen=True)
class Pass:
    """One pass, shaped like a `protopilot.passes` module.

    The same four attributes `run_pass` reads -- `NAME`, `WRITES`, `SCHEMA`,
    `build` -- so the spike's driver is the same shape as the real one and the
    two can be read side by side.
    """

    NAME: str
    WRITES: Tuple[str, ...]
    TASK: str
    user: Callable[[object, object], str]
    SCHEMA: dict = field(default_factory=lambda: FILES_SCHEMA)

    def build(self, spec, ctx) -> Tuple[str, str]:
        return TUI_BRIEF + self.TASK, self.user(spec, ctx)


SCHEMA_TASK = """\
## Your task

Write `app/models.py` -- and only that file.

- One `Base` subclass per entity, SQLAlchemy 2.0 declarative style with
  `Mapped[...]` annotations and `mapped_column(...)`.
- `id: Mapped[int] = mapped_column(primary_key=True)` on every model.
- A `belongs_to` becomes a nullable `ForeignKey` column named
  `<parent_snake>_id` plus a `relationship()` on both sides with
  `back_populates`. The parent side carries
  `cascade="all, delete-orphan"` -- deleting a parent must not leave orphans
  that every later query has to filter out.
- A field with `required: false` is `Mapped[Optional[T]]` and
  `nullable=True`; a required one is `Mapped[T]` and `nullable=False`.
- Every model gets a `display` property returning a short human label,
  falling back to `f"<Entity> {self.id}"`, and `__str__` returning it.
- `from __future__ import annotations` at the top, and `Optional` imported
  from `typing` -- SQLAlchemy resolves these annotations at class creation.
"""

SMOKE_TASK = """\
## Your task

Write `tests/test_smoke.py` -- and only that file.

The screens DO NOT EXIST YET. You are writing the target they will be
generated against. Test what the spec promises, not what you imagine the
implementation will look like.

`tests/conftest.py` already provides two fixtures:

- `app`: a fresh `TerminalApp` instance, not yet running. Start it with
  `async with app.run_test() as pilot:` -- that is what mounts it, creates the
  tables, seeds them and pushes the home screen.
- `db`: a `Session`. It is a DIFFERENT session from the app's, so after an
  interaction that writes, call `db.rollback()` before re-querying --
  otherwise the open transaction hides the row the app just committed.

`pytest.ini` sets `asyncio_mode = auto`, so an `async def test_...` runs with
no decorator and no fixture of your own.

Cover, per entity:

- the list screen can be reached and shows something: push to it, then assert
  its `DataTable` has more than zero rows
- seed data exists (`count > 0` through `db`) -- a prototype with empty tables
  cannot be demonstrated
- the record screen for a seeded row can be opened, and the screen that comes
  up mentions that row's `display` text (look the row up through `db` first;
  never hard-code an id)
- a create round trip: reach the form screen, fill its inputs through the
  pilot, submit it, then assert through `db` that the row count went up by
  exactly one

Plus one test that the app starts and its home screen is on the stack.

How to drive it, and stay inside what the framework guarantees:

- `await pilot.press("d")` for a key, `await pilot.click("#some-id")` for a
  widget, `await pilot.pause()` to let the app settle before asserting.
- Reach a screen through the app's own navigation -- press the key or click
  the button the spec implies -- rather than by calling `push_screen` from the
  test. A test that constructs the screen itself proves the screen works and
  says nothing about whether it can be got to.
- Read the state back with `app.screen.query_one("#some-id", DataTable)` and
  assert on `row_count`, or with `app.screen.query(Static)` and assert on the
  text. Assert on structure and counts, not on wording: an assertion about a
  heading's exact words makes the styling pass fail for choosing a different
  verb.

Rules: pytest functions, no classes, no fixtures of your own, no mocking. Put
the failure's context in every assertion's message -- when this fails in a
report it is the only traceback anybody gets.
"""

SEED_TASK = """\
## Your task

Write `app/seed.py` -- and only that file. It exports
`def seed(db: Session) -> None`.

- Roughly 5 rows per top-level entity and 2-3 children per parent. Enough to
  fill a table; few enough to read.
- Make the data PLAUSIBLE for this specific app. Real-sounding names, dates
  spread across the next few weeks, a mix of true and false booleans, numbers
  in a believable range. "Item 1 / Item 2 / Item 3" tells a viewer nothing
  about what the app is for.
- Keep the strings short. This is a terminal: a column is a few dozen cells
  wide, and a forty-character name is a truncated one.
- Idempotent, and the guard comes first: return immediately if the first
  entity already has any row. `seed()` runs every time the app mounts, and the
  test suite mounts it many times -- an unguarded seed is a duplicate-row
  factory.
- Insert parents, `db.flush()` to get their ids, then children referencing
  `parent.id`. One `db.commit()` at the end, so a failure part-way rolls the
  whole seed back rather than leaving half a fixture.
- No randomness. A regenerated seed should be a no-op diff.
"""

SCREENS_TASK = """\
## Your task

Write `app/screens.py` -- and only that file. It defines every screen class,
including `HomeScreen`, which `app.main` pushes by name.

You are given `tests/test_smoke.py`, which already exists and will be run
against your output. Satisfying it is the job. If a test presses a key, that
key is bound; if it clicks an id, a widget has that id.

Per entity: a list screen, a form screen for creating one, and a record
screen. Plus `HomeScreen`, which is the way in to all of them.

- Every screen subclasses `AppScreen` from `app.base` and yields `Header()`
  first and `Footer()` last from `compose()`.
- A screen that is about one row takes its id in `__init__` and calls
  `super().__init__()` -- store the id, and load the row in `on_mount`, not in
  `__init__` and not in `compose()`.
- Look rows up with `db.get(Model, row_id)` inside `with self.db() as db:`,
  and handle `None` by showing a message rather than raising.
- Query lists with `db.scalars(select(Model).order_by(Model.id)).all()`.
- Read every attribute you are going to display WHILE the session is open. A
  value read after the `with` block has closed is read off a detached
  instance, and that raises inside a render.
- A list screen is a `DataTable` with one column per spec field, populated in
  `on_mount`, plus a binding that opens the record screen for the highlighted
  row and one that opens the create form.
- A form screen is one labelled widget per field, with the widget matching the
  field type: `Input` for `str`, `int`, `float`, `date` and `datetime`,
  `TextArea` for `text`, `Checkbox` for `bool`. Textual has no date picker --
  a date is an `Input` whose placeholder shows the format, parsed with
  `datetime.date.fromisoformat` inside a `try`, and a value that will not
  parse leaves the form up with a message rather than raising.
- Coerce every form value defensively. A required column receiving an empty
  string is the terminal equivalent of a 500, except that here it is a
  traceback painted over the app.
- After a successful create, `pop_screen()` back to the list and refresh it
  from the database.
- Give every widget the test might look for a stable `id`.
- Every screen has a `BINDINGS` list and every binding has a description, so
  the `Footer` tells a person what the keys are. A screen whose keys are
  undiscoverable is the terminal version of a page with no links.
"""

UI_TASK = """\
## Your task

Write the presentation layer: `app/app.tcss` and, if the screens need one,
`app/widgets.py`.

`app/app.tcss` is the Textual stylesheet the app loads through
`CSS_PATH = "app.tcss"`. Read `app/screens.py` and style exactly the ids and
classes it uses -- a selector for a widget that does not exist is dead, and a
widget with no rule falls back to a default that is usually the reason a
screen looks like a wall of text.

Textual CSS is not web CSS. The properties that exist are: `layout`, `dock`,
`width`, `height`, `min-width`, `max-width`, `min-height`, `max-height`,
`padding`, `margin`, `border`, `outline`, `background`, `color`, `text-style`,
`text-align`, `content-align`, `align`, `grid-size`, `grid-columns`,
`grid-rows`, `grid-gutter`, `overflow`, `display`, `visibility`, `opacity`,
`scrollbar-size`. Sizes are in cells (`10`), fractions (`1fr`), percentages
(`50%`) or `auto`. There is no `float`, no `position: absolute`, no `z-index`,
no `flex`, no media query, and no `@import`.

- Colour with the theme variables (`$primary`, `$secondary`, `$accent`,
  `$surface`, `$panel`, `$boost`, `$success`, `$warning`, `$error`,
  `$text`, `$text-muted`) rather than hex literals wherever the meaning is
  semantic. A hard-coded hex is fine where the colour IS the information --
  the two sides of a board, a status marker.
- Give the screen a layout that uses the whole terminal: something docked or
  `1fr`, not a column of widgets at their natural height with a void beneath.
- Style the empty state. A `DataTable` with no rows and a `Static` saying so
  are two different screens, and the second is the one that does not look
  broken.

Write `app/widgets.py` only if `app/screens.py` imports from it. If it does,
define exactly the widgets it imports, nothing more. If it does not, do not
create the file: an unused module is a file the next pass has to read.
"""

REPAIR_TASK = """\
## Your task

The generated application does not work. You are given the stage that failed,
the output, and the current contents of every generated file. Fix it.

Return the COMPLETE contents of only the files you are changing. A file you do
not return is left alone -- do not return files you have not edited.

- Diagnose from the traceback, not from what the code looks like it should do.
  The failure has a specific cause; name it to yourself before you change
  anything.
- Make the SMALLEST change that fixes the cause. Do not refactor, do not
  rename, do not "also improve" something on the way past. A repair that
  rewrites a working file turns one red test into two.
- Never make a test pass by deleting it, weakening its assertion, or wrapping
  it in a skip. If a test genuinely contradicts the spec, say so in `notes`
  and fix the test to match the spec -- never to match the code.
- Common causes, in the order they actually occur: a widget id a test queries
  and no screen defines; an attribute read off a model after its session
  closed; a `compose()` that touches the database; a Textual CSS property that
  does not exist; a screen constructed with arguments its `__init__` does not
  take; a required column receiving an empty string from a blank `Input`.
"""


def _sources(ctx, *rels: str) -> str:
    chunks = []
    for rel in rels:
        body = ctx.read(rel)
        if not body.strip():
            continue
        lang = "css" if rel.endswith(".tcss") else "python"
        chunks.append(f"### `{rel}`\n\n```{lang}\n{body}\n```")
    return "\n\n".join(chunks)


def _theme_block(spec) -> str:
    """The look, in the one pass allowed to hear it.

    The terminal counterpart of `passes.ui.theme_block`, and shorter for a
    reason worth recording: half of that function is about SVG, which does not
    exist here. What survives is the wording and the colour, and colour in a
    terminal is a stylesheet rather than a `fill` attribute -- so unlike the
    web target, this pass genuinely does write the styles. The web UI pass may
    not, because its stylesheet is skeleton.
    """
    theme = getattr(spec, "theme", None)
    if theme is None or theme.is_empty():
        return ""
    lines = ["\n\n## The theme\n", "The user asked for a particular look. Apply it inside the rules above.\n"]
    if theme.subject:
        lines.append(
            f"- **Subject: {theme.subject}.** Where the screen shows a piece, a marker or an\n"
            "  icon, choose the character that depicts that subject rather than a generic one."
        )
    if theme.palette:
        lines.append(
            f"- **Palette: {theme.palette}.** This is what `app/app.tcss` is for. Put the\n"
            "  colours there, on the ids and classes the screens already use."
        )
    if theme.motif:
        lines.append(
            f"- **Motif: {theme.motif}.** A small repeated character or border style, used as\n"
            "  a marker or a divider -- not pasted into every cell."
        )
    if theme.tone:
        lines.append(
            f"- **Tone: {theme.tone}.** This is the wording: screen titles, binding\n"
            "  descriptions, and especially the empty states."
        )
    lines.append(
        "\nThe theme changes what is drawn and what things are called. It changes\n"
        "nothing else. Screen classes, widget ids, field names and bindings are already\n"
        "decided and are not yours to restyle -- a stylesheet that renames an id crashes\n"
        "nothing and silently styles nothing, which is worse."
    )
    return "\n".join(lines)


def _schema_user(spec, ctx) -> str:
    return spec_block(spec)


def _smoke_user(spec, ctx) -> str:
    return spec_block(spec) + "\n\n## Already generated\n\n" + _sources(ctx, "app/models.py")


def _seed_user(spec, ctx) -> str:
    user = spec_block(spec) + "\n\n## Already generated\n\n" + _sources(ctx, "app/models.py")
    if spec.direction:
        user += f"\n\nThe user's direction, which the sample data should reflect: {spec.direction}"
    return user


def _screens_user(spec, ctx) -> str:
    return spec_block(spec) + "\n\n## Already generated\n\n" + _sources(ctx, "app/models.py", "tests/test_smoke.py")


def _ui_user(spec, ctx) -> str:
    user = spec_block(spec) + "\n\n## Already generated\n\n" + _sources(ctx, "app/models.py", "app/screens.py")
    if spec.direction:
        user += f"\n\nThe user's direction for how this should look and feel: {spec.direction}"
    return user + _theme_block(spec)


def _repair_user(spec, ctx) -> str:
    return (
        "## What went wrong\n\n```\n"
        + ctx.failure.strip()
        + "\n```\n\n"
        + spec_block(spec)
        + "\n\n## Current source of every generated file\n\n"
        + _sources(ctx, *WRITABLE)
    )


#: Five passes, in the same order and with the same two invariants as the web
#: target: smoke is generated BEFORE the code it tests, from the spec, and each
#: pass is handed the previous pass's real source rather than a description of
#: it. Whether five is the right number for this medium is Phase 4's question,
#: and it is deliberately not answered here -- a spike that changed the split
#: as well as the target would produce a number nobody could attribute.
CODE_PASSES = (
    Pass("schema", ("app/models.py",), SCHEMA_TASK, _schema_user),
    Pass("smoke", ("tests/test_smoke.py",), SMOKE_TASK, _smoke_user),
    Pass("seed", ("app/seed.py",), SEED_TASK, _seed_user),
    Pass("screens", ("app/screens.py",), SCREENS_TASK, _screens_user),
    Pass("ui", ("app/app.tcss", "app/widgets.py"), UI_TASK, _ui_user),
)

REPAIR = Pass("repair", WRITABLE, REPAIR_TASK, _repair_user)
