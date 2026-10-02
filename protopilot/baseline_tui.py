"""The deterministic baseline generator for the terminal target.

The terminal half of `baseline.py`, and it exists for the same three reasons in
the same order: a fast free path to something runnable, the worked example each
terminal prompt is written against, and -- most importantly -- **it is what the
test suite runs**, so the whole pipeline is exercised on every commit with no
key, no Docker and no network.

## What is here and what is not

Only the three files whose content actually depends on the medium:

    app/screens.py     the terminal counterpart of app/routes.py + the templates
    tests/test_smoke.py  driven through App.run_test rather than a TestClient
    app/app.tcss       a stylesheet, which the web target's ui pass may not write

`app/models.py` and `app/seed.py` are **not** here. Both are pure SQLAlchemy --
they import from `app.db` and know nothing about whether a screen or a route is
going to read them -- so the terminal passes call `baseline.models_py` and
`baseline.seed_py` directly. A second copy would be a second answer to "what
does a model class look like", and the two would drift the first time either
target grew a field type.

## Why the generated code coerces its own form values

There is no `app/forms.py` in this skeleton. On the web side that module is
skeleton and the brief points at it; here the brief tells the model to parse
inline, inside a `try`, and to leave the form up with a message rather than
raising. So the baseline does exactly that, because the baseline is the worked
example the prompt is checked against -- a generator that solved the problem a
way the prompt does not describe is a worked example of the wrong thing.

That is also the shape of the defect the Phase 1 report found on the *web*
side: `STACK_BRIEF` promised every `app.forms` parser took a fallback,
`parse_bool` did not, and every run with a bool field burned a repair attempt
doing what it was told. A brief and a baseline that disagree cost one attempt
per generation, silently, forever.
"""

from __future__ import annotations

from protopilot.baseline import _blocks, children_of, ordered_entities  # noqa: F401
from protopilot.spec import Entity, Field_, Spec

#: How many entities get a digit binding on the home screen.
#:
#: Nine, because there are nine digits. An intake that produced a tenth entity
#: would leave it unreachable from home, and that is a stated limit rather than
#: an oversight: a prototype whose home screen needs a second page of shortcuts
#: has already stopped being a prototype.
HOME_KEYS = 9


def _apply(template: str, values: dict[str, str]) -> str:
    """`__TOKEN__` substitution, the same discipline `baseline.py` uses.

    Not f-strings: the output is Python containing f-strings of its own, and
    every brace-escaping scheme for generating brace-heavy text eventually
    produces a file that is wrong in a way nobody can read.
    """
    for token, value in values.items():
        template = template.replace(token, value)
    return template


def _safe(text: str) -> str:
    """One line of model-supplied prose, safe inside a double-quoted literal.

    `spec.name` and `spec.purpose` are written by the model and land in string
    literals and docstrings in generated Python. A stray quote or backslash
    there is a `SyntaxError` in a file nobody hand-wrote, at a stage whose
    error message is about the wrong thing entirely.
    """
    return text.replace("\\", " ").replace('"', "'").replace("\n", " ").strip()


def title_of(entity: Entity) -> str:
    return entity.plural.replace("_", " ").capitalize()


def screen_prefix(entity: Entity) -> str:
    """`Trip` -> `Trip`. The class-name stem for this entity's three screens."""
    return entity.name


# -- screens -----------------------------------------------------------

_HELPERS = '''\
def cell(value: object) -> str:
    """One column value, as text a terminal can put in a table.

    Booleans become words rather than `True`/`False`: a column reading "yes"
    is scannable and a column reading "True" is a debugger.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def as_int(raw: str, fallback: int = 0) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback


def as_float(raw: str, fallback: float = 0.0) -> float:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return fallback


def as_date(raw: str) -> date | None:
    """A date, or None. The caller decides whether None is allowed.

    Textual has no date picker, so a date arrives as whatever somebody typed
    into an `Input`. Parsing it inside a `try` is what keeps a typo a message
    on the form instead of a traceback painted over the app.
    """
    try:
        return date.fromisoformat(str(raw).strip())
    except (TypeError, ValueError):
        return None


def as_datetime(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).strip())
    except (TypeError, ValueError):
        return None
'''

_HOME = '''\
class HomeScreen(AppScreen):
    """__PURPOSE__

    The name `app/main.py` hard-codes: it is returned from
    `get_default_screen()`, so it is the bottom of the screen stack and Escape
    on it does nothing.
    """

    BINDINGS = [
__HOME_BINDINGS__
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("__NAME__", id="app-name")
        yield Static("__PURPOSE__", id="app-purpose")
        yield DataTable(id="sections")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "__PURPOSE__"
        table = self.query_one("#sections", DataTable)
        table.add_columns("Screen", "Rows", "Key")
        with self.db() as db:
            counts = [
__HOME_COUNTS__
            ]
        for label, count, key in counts:
            table.add_row(label, str(count), key)

__HOME_ACTIONS__'''

_LIST = '''\
class __PREFIX__ListScreen(AppScreen):
    """Every __LOWER_SINGULAR__, one row each. Enter opens one, `n` adds one."""

    BINDINGS = [
        Binding("n", "new_row", "New __NAME__"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("__TITLE__", id="heading")
        yield DataTable(id="rows")
        yield Static("", id="empty")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "__TITLE__"
        table = self.query_one("#rows", DataTable)
        table.cursor_type = "row"
        table.add_columns(__COLUMNS__)
        self.reload()

    def reload(self) -> None:
        """Redraw from the database.

        Cleared and re-added rather than patched. A terminal app has no page
        reload, and a table that disagrees with the database is the single most
        common way a generated TUI looks broken.
        """
        table = self.query_one("#rows", DataTable)
        table.clear()
        with self.db() as db:
            rows = [
                (str(row.id), __CELLS__)
                for row in db.scalars(select(__NAME__).order_by(__NAME__.id)).all()
            ]
        for row in rows:
            table.add_row(*row, key=row[0])
        self.query_one("#empty", Static).update(
            "" if rows else "No __LOWER_TITLE__ yet -- press n to add the first one."
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            self.app.push_screen(__PREFIX__RecordScreen(int(event.row_key.value)))

    def action_new_row(self) -> None:
        """Open the form, and redraw only if it says something was made.

        A callback rather than a `ScreenResume` handler: resume fires on the
        way in as well as the way back, before `on_mount` has given the table
        its columns, and `add_row` on a table with no columns raises.
        """
        self.app.push_screen(__PREFIX__FormScreen(), self._after_form)

    def _after_form(self, made: bool | None) -> None:
        if made:
            self.reload()'''

_FORM = '''\
class __PREFIX__FormScreen(AppScreen):
    """A new __LOWER_SINGULAR__. Ctrl+S saves; Escape goes back without saving.

    Ctrl+S rather than a letter, and that is not a style choice: a printable
    key is swallowed by whichever `Input` has focus, so a screen binding on one
    would never fire while somebody was typing -- which is the entire time this
    screen is on top.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("New __NAME__", id="heading")
        with VerticalScroll(id="fields"):
__INPUTS__
        yield Static("", id="message")
        yield Button("Save", id="save", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "New __NAME__"
__FORM_MOUNT__

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()

    def action_save(self) -> None:
__SAVE__
        with self.db() as db:
            db.add(__NAME__(**values))
            db.commit()
        self.dismiss(True)'''

_RECORD = '''\
class __PREFIX__RecordScreen(AppScreen):
    """One __LOWER_SINGULAR__, field by field."""

    def __init__(self, row_id: int) -> None:
        super().__init__()
        self.row_id = row_id

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="heading")
        yield DataTable(id="fields")
        yield Static("", id="related")
        yield Footer()

    def on_mount(self) -> None:
        """Everything displayed is read while the session is open.

        A value read after the `with` block has closed is read off a detached
        instance, and in a TUI that raises inside a render -- a traceback
        painted over the app rather than an error anybody can act on.
        """
        table = self.query_one("#fields", DataTable)
        table.add_columns("Field", "Value")
        with self.db() as db:
            row = db.get(__NAME__, self.row_id)
            if row is None:
                self.query_one("#heading", Static).update(f"__NAME__ {self.row_id} is not here any more.")
                return
            heading = row.display
            values = [
__RECORD_FIELDS__
            ]
            related = __RELATED__
        self.sub_title = heading
        self.query_one("#heading", Static).update(heading)
        for name, value in values:
            table.add_row(name, value)
        self.query_one("#related", Static).update(related)'''


def _column_labels(entity: Entity) -> str:
    labels = ['"Id"'] + [f'"{f.human_label()}"' for f in entity.fields]
    return ", ".join(labels)


def _row_cells(entity: Entity) -> str:
    return ", ".join(f"cell(row.{f.name})" for f in entity.fields) or '""'


#: Which Textual widget carries which spec field type, and how its state is
#: read back. The same table the brief states in prose, in the one place the
#: baseline can be checked against it -- a generator that solved the problem a
#: way the prompt does not describe is a worked example of the wrong thing.
WIDGETS = {
    "str": ("Input", "value"),
    "text": ("TextArea", "text"),
    "int": ("Input", "value"),
    "float": ("Input", "value"),
    "bool": ("Checkbox", "value"),
    "date": ("Input", "value"),
    "datetime": ("Input", "value"),
}

PLACEHOLDERS = {
    "date": "YYYY-MM-DD",
    "datetime": "YYYY-MM-DDTHH:MM",
    "int": "whole number",
    "float": "number",
}


def widget_names(spec: Spec, extra: tuple[str, ...] = ()) -> list[str]:
    """Every Textual widget class the generated screens actually import."""
    used = {WIDGETS[f.type][0] for e in spec.entities for f in e.fields}
    return sorted(used | set(extra))


def _widget_for(field: Field_) -> str:
    """The `yield` expression composing one field's widget."""
    ident = f"field-{field.name}"
    label = _safe(field.human_label())
    if field.type == "bool":
        return f'Checkbox("{label}", id="{ident}")'
    if field.type == "text":
        return f'TextArea(id="{ident}")'
    placeholder = PLACEHOLDERS.get(field.type, label)
    return f'Input(id="{ident}", placeholder="{placeholder}")'


def _read_line(field: Field_) -> str:
    """Pull one widget's state into a local, so `values` stays readable."""
    widget, attribute = WIDGETS[field.type]
    return f'        {field.name} = self.query_one("#field-{field.name}", {widget}).{attribute}'


def _value_expr(field: Field_) -> str:
    """That local, coerced to what the column wants.

    A required column gets a fallback so an empty submit is a form somebody can
    fix rather than a traceback painted over the app; an optional one gets
    `None`, which is what the column is declared to accept.
    """
    name = field.name
    if field.type == "bool":
        return f"bool({name})"
    if field.type in {"str", "text"}:
        return name if field.required else f"({name} or None)"
    if field.type == "int":
        return f"as_int({name})" if field.required else f"(as_int({name}) if {name}.strip() else None)"
    if field.type == "float":
        return f"as_float({name})" if field.required else f"(as_float({name}) if {name}.strip() else None)"
    if field.type == "date":
        return f"(as_date({name}) or date.today())" if field.required else f"as_date({name})"
    return f"(as_datetime({name}) or datetime.now())" if field.required else f"as_datetime({name})"


def screens_py(spec: Spec) -> str:
    """Every screen class, plus the coercion helpers they share.

    One home screen and three per entity -- list, form, record -- which is the
    terminal reading of the same CRUD spread `crud.screens()` describes. The
    class names are derived from the entity name rather than the screen path,
    because a path is an identifier here and not an address.
    """
    entities = list(spec.entities)
    widgets = widget_names(spec, extra=("Button", "DataTable", "Footer", "Header", "Static"))
    header = [
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime  # noqa: F401",
        "",
        "from app.base import AppScreen",
        "from sqlalchemy import func, select",
        "from textual.app import ComposeResult",
        "from textual.binding import Binding",
        "from textual.containers import VerticalScroll",
        f"from textual.widgets import {', '.join(widgets)}",
    ]
    if entities:
        header.insert(5, f"from app.models import {', '.join(sorted(e.name for e in entities))}")

    blocks: list[str] = [_HELPERS]

    keyed = entities[:HOME_KEYS]
    bindings = (
        "\n".join(f'        Binding("{i + 1}", "open_{e.plural}", "{title_of(e)}"),' for i, e in enumerate(keyed))
        or '        Binding("h", "noop", "Home"),'
    )
    counts = (
        "\n".join(
            f'                ("{title_of(e)}", db.scalar(select(func.count()).select_from({e.name})) or 0, "{i + 1}"),'
            for i, e in enumerate(keyed)
        )
        or "                # no entities in this spec"
    )
    actions = (
        "\n\n".join(
            f"    def action_open_{e.plural}(self) -> None:\n"
            f"        self.app.push_screen({screen_prefix(e)}ListScreen())"
            for e in keyed
        )
        or "    def action_noop(self) -> None:\n        return None"
    )
    blocks.append(
        _apply(
            _HOME,
            {
                "__NAME__": _safe(spec.name),
                "__PURPOSE__": _safe(spec.purpose),
                "__HOME_BINDINGS__": bindings,
                "__HOME_COUNTS__": counts,
                "__HOME_ACTIONS__": actions,
            },
        )
    )

    for entity in entities:
        base = {
            "__NAME__": entity.name,
            "__PREFIX__": screen_prefix(entity),
            "__TITLE__": title_of(entity),
            "__LOWER_TITLE__": title_of(entity).lower(),
            "__LOWER_SINGULAR__": entity.name.lower(),
        }
        blocks.append(
            _apply(
                _LIST,
                base | {"__COLUMNS__": _column_labels(entity), "__CELLS__": _row_cells(entity)},
            )
        )
        blocks.append(_apply(_FORM, base | _form_parts(spec, entity)))
        blocks.append(_apply(_RECORD, base | _record_parts(spec, entity)))

    return _blocks(header, blocks)


def _form_parts(spec: Spec, entity: Entity) -> dict[str, str]:
    inputs: list[str] = []
    reads: list[str] = []
    assigns: list[str] = []
    mount: list[str] = []

    for field in entity.fields:
        if field.type != "bool":
            inputs.append(f'            yield Static("{_safe(field.human_label())}", classes="label")')
        inputs.append(f"            yield {_widget_for(field)}")
        reads.append(_read_line(field))
        assigns.append(f'            "{field.name}": {_value_expr(field)},')

    parent = spec.entity(entity.belongs_to) if entity.belongs_to else None
    if parent is not None:
        ident = f"field-{parent.var}_id"
        inputs.append(f'            yield Static("{parent.name}", classes="label")')
        inputs.append(f'            yield Input(id="{ident}", placeholder="{parent.name} id")')
        reads.append(f'        parent_id = self.query_one("#{ident}", Input).value')
        assigns.append(f'            "{parent.var}_id": (as_int(parent_id) if parent_id.strip() else None),')
        # Prefilled in `on_mount` rather than in `compose`: it is a database
        # read, and `compose` runs before the app is mounted.
        mount += [
            "        with self.db() as db:",
            f"            first = db.scalars(select({parent.name}).order_by({parent.name}.id).limit(1)).first()",
            '            suggestion = str(first.id) if first is not None else ""',
            f'        self.query_one("#{ident}", Input).value = suggestion',
        ]

    save = reads + ["        values = {"] + (assigns or ["            # nothing to fill in"]) + ["        }"]
    return {
        "__INPUTS__": "\n".join(inputs) or '            yield Static("Nothing to fill in.")',
        "__FORM_MOUNT__": "\n".join(mount) or "        return None",
        "__SAVE__": "\n".join(save),
    }


def _record_parts(spec: Spec, entity: Entity) -> dict[str, str]:
    """The field rows, and the one line of related-record text beneath them.

    The parent's `display` and the children's are read INSIDE the session that
    loaded the row -- `row.trip.display` after the `with` block has closed is a
    lazy load on a detached instance, which raises inside a render.
    """
    fields = (
        "\n".join(f'                ("{f.human_label()}", cell(row.{f.name})),' for f in entity.fields)
        or "                # this entity has no fields"
    )

    parts: list[str] = []
    parent = spec.entity(entity.belongs_to) if entity.belongs_to else None
    if parent is not None:
        parts.append(f'(f"{parent.name}: {{row.{parent.var}.display}}" if row.{parent.var} else "No {parent.name}")')
    for child in children_of(spec, entity):
        parts.append(f'("{title_of(child)}: " + (", ".join(c.display for c in row.{child.plural}) or "none yet"))')

    if not parts:
        expression = '""'
    elif len(parts) == 1:
        expression = parts[0]
    else:
        joined = '\n                + "   "\n                + '.join(parts)
        expression = "(\n                " + joined + "\n            )"
    return {"__RECORD_FIELDS__": fields, "__RELATED__": expression}


# -- the stylesheet ----------------------------------------------------

_TCSS = """\
/* The terminal stylesheet. Every selector here is an id or a class that
   `app/screens.py` actually uses -- a rule for a widget that does not exist is
   dead, and a widget with no rule falls back to a default that is usually the
   reason a screen reads as a wall of text. */

Screen {
    layout: vertical;
}

#app-name {
    text-style: bold;
    color: $primary;
    padding: 1 2 0 2;
}

#app-purpose, #heading {
    color: $text-muted;
    padding: 0 2 1 2;
}

#heading {
    text-style: bold;
    color: $text;
}

DataTable {
    height: 1fr;
    margin: 0 2;
}

#empty, #message, #related {
    color: $warning;
    padding: 1 2;
}

#fields {
    height: 1fr;
    padding: 0 2;
}

.label {
    color: $text-muted;
    padding: 1 0 0 0;
}

Input, Checkbox {
    margin: 0 0 1 0;
}

Button {
    margin: 0 2 1 2;
}
"""


def tcss(spec: Spec) -> str:
    """A stylesheet for the screens above. Fixed rather than derived.

    It selects ids the generator always emits, so there is nothing per-spec in
    it -- and a function that takes a spec and ignores it is the honest shape
    here, because `archetypes.generator(spec, "tui_tcss")` has to be able to
    replace it with one that does not.
    """
    return _TCSS


# -- smoke tests -------------------------------------------------------

_SMOKE_HEADER = """\
from __future__ import annotations

from sqlalchemy import func, select
from textual.widgets import __WIDGETS__
"""

_SMOKE_BOOT = '''\
async def test_the_app_starts_on_the_home_screen(app) -> None:
    """One screen deep, with something on it.

    `HomeScreen` is the app's default screen rather than something pushed onto
    one, which is what makes Escape on it a no-op instead of a way to empty the
    app.
    """
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert type(app.screen).__name__ == "HomeScreen", where(app)
        assert len(app.screen_stack) == 1, where(app)
        assert visible(app).strip(), f"the home screen holds no readable text; {where(app)}"'''

_SMOKE_SEEDED = '''\
async def test___VAR___is_seeded(app, db) -> None:
    """A prototype with empty tables cannot be demonstrated.

    The app is started first because that is what runs `seed()` -- there is no
    lifespan here and no container, so mounting the app IS the setup.
    """
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
    db.rollback()
    count = db.scalar(select(func.count()).select_from(__NAME__))
    assert count and count > 0'''

_SMOKE_LIST = '''\
async def test_the___VAR___list_screen_can_be_reached(app) -> None:
    """Reached through the app's own navigation, not by pushing the screen.

    A test that constructs the screen itself proves the screen works and says
    nothing about whether anybody can get to it.
    """
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("__KEY__")
        await pilot.pause()
        assert type(app.screen).__name__ == "__PREFIX__ListScreen", where(app)
        table = app.screen.query_one("#rows", DataTable)
        assert table.row_count > 0, f"the __LOWER_TITLE__ table is empty; {where(app)}"'''

_SMOKE_RECORD = '''\
async def test_a___VAR___record_screen_opens(app, db) -> None:
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        db.rollback()
        row = db.scalars(select(__NAME__).order_by(__NAME__.id).limit(1)).first()
        assert row is not None, "no seeded __NAME__ to open"
        label = row.display

        await pilot.press("__KEY__")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert type(app.screen).__name__ == "__PREFIX__RecordScreen", where(app)
        assert mentions(app, label), f"the record screen does not mention {label!r}; {where(app)}"'''

_SMOKE_CREATE = '''\
async def test_creating_a___VAR___adds_exactly_one_row(app, db) -> None:
    """The round trip, and the one test a static screen could not pass."""
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        db.rollback()
        before = db.scalar(select(func.count()).select_from(__NAME__)) or 0

        await pilot.press("__KEY__")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert type(app.screen).__name__ == "__PREFIX__FormScreen", where(app)

__FILL__
        # Ctrl+S rather than a letter: a printable key goes to whichever Input
        # has focus and never reaches the screen's own bindings.
        await pilot.press("ctrl+s")
        await pilot.pause()

    db.rollback()
    after = db.scalar(select(func.count()).select_from(__NAME__)) or 0
    assert after == before + 1, f"expected one new __NAME__, went from {before} to {after}"'''


_SMOKE_VALUES = {
    "str": "proto-pilot smoke",
    "text": "written by the smoke suite",
    "int": "7",
    "float": "1.5",
    "date": "2030-01-02",
    "datetime": "2030-01-02T03:04",
}


def _fill_lines(spec: Spec, entity: Entity) -> str:
    """Set each input's value, then submit through a real key press.

    The values are assigned rather than typed one character at a time. Typing
    is what a person does and `pilot.press` can do it, but a date typed key by
    key is eleven awaited keystrokes whose only failure mode is the harness's
    -- and the assertion this test exists for is about the row that appears in
    the database, not about the keyboard.
    """
    lines: list[str] = []
    for field in entity.fields:
        ident = f"field-{field.name}"
        widget, attribute = WIDGETS[field.type]
        if field.type == "bool":
            lines.append(f'        app.screen.query_one("#{ident}", {widget}).{attribute} = True')
        else:
            value = _SMOKE_VALUES[field.type]
            lines.append(f'        app.screen.query_one("#{ident}", {widget}).{attribute} = "{value}"')
    parent = spec.entity(entity.belongs_to) if entity.belongs_to else None
    if parent is not None:
        lines.append(f"        parent = db.scalars(select({parent.name}).order_by({parent.name}.id).limit(1)).first()")
        lines.append(f'        assert parent is not None, "no seeded {parent.name} to attach to"')
        lines.append(f'        app.screen.query_one("#field-{parent.var}_id", Input).value = str(parent.id)')
    return "\n".join(lines) or "        # this entity has no fields to fill in"


def smoke_py(spec: Spec) -> str:
    """Generated from the spec, and generated BEFORE the screens.

    Every assertion here is about what the spec promised: the app starts and
    paints, each entity is seeded, each list screen is reachable through the
    app's own navigation, a record screen shows the row it was opened for, and
    a create round trip adds exactly one row. None of it reads a widget's text
    attribute by hand -- `tests/screen.py` does that, and it is skeleton
    precisely because three Phase 1 generations wrote it wrong.
    """
    entities = list(spec.entities)
    widgets = widget_names(spec, extra=("DataTable",))
    header = _apply(_SMOKE_HEADER, {"__WIDGETS__": ", ".join(widgets)})
    if entities:
        header += f"\nfrom app.models import {', '.join(sorted(e.name for e in entities))}\n"
    # Last, and its own group: `tests/screen.py` is the skeleton's text reader
    # and the one import in this file that is not the application's.
    header += "from tests.screen import mentions, visible, where\n"

    blocks = [_SMOKE_BOOT]
    for index, entity in enumerate(entities[:HOME_KEYS]):
        values = {
            "__NAME__": entity.name,
            "__VAR__": entity.var,
            "__PREFIX__": screen_prefix(entity),
            "__KEY__": str(index + 1),
            "__LOWER_TITLE__": title_of(entity).lower(),
        }
        blocks.append(_apply(_SMOKE_SEEDED, values))
        blocks.append(_apply(_SMOKE_LIST, values))
        blocks.append(_apply(_SMOKE_RECORD, values))
        blocks.append(_apply(_SMOKE_CREATE, values | {"__FILL__": _fill_lines(spec, entity)}))
    return _blocks([header.rstrip("\n")], blocks)
