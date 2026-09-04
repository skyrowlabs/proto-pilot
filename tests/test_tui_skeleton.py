"""The terminal skeleton: it renders, it boots, and its harness can see it.

Phase 3 of `docs/implementations/spec/terminal-target.md`. `skeleton/tui/` is a fixed Textual +
SQLite tree — one process, one file, no compose file, no port — and this is
what holds it up until Phase 4 gives it passes and Phase 5 gives it a verifier.

The test that matters most here is the last group. Phase 1 measured three
terminal generations and **all three failed their own smoke suite while the app
underneath was correct**, because the helper each one wrote read a `Static`'s
text off `.renderable`, which current Textual does not have. The skeleton now
ships `tests/screen.py` so nothing has to write it a fourth time, and the tests
below **demonstrate** that it sees a `Static` rather than asserting that it
does — on a hand-written app, the same discipline the blank-screen check uses.

There is deliberately no `protopilot/targets/tui.py` yet. A registered target
whose `CODE_PASSES` and `verifier()` do not exist is a `proto new --target tui`
that half-works, and the plan's own Phase 6 note says exactly why that is the
wrong order. The tree is data; the module arrives with the passes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scanning import scanned

from protopilot import targets
from protopilot.render import TOKEN_RE, render_skeleton, substitutions

# Host-side: no key, no Docker daemon, no browser, no network. That this suite
# needs none of them is half of what the terminal target is for.
pytestmark = pytest.mark.unit

pytest.importorskip("textual")
pytest.importorskip("sqlalchemy")

TUI_SKELETON = targets.SKELETON_ROOT / "tui"

#: Files a pass is expected to rewrite, by the banner they carry.
GENERATED = (
    "app/models.py",
    "app/screens.py",
    "app/seed.py",
    "app/widgets.py",
    "app/app.tcss",
    "tests/test_smoke.py",
)


def _source_files() -> list[Path]:
    """Every real file in the skeleton.

    `__pycache__` is excluded by name rather than by suffix, and that is not
    fussiness: running the rendered tree's suite leaves bytecode inside the
    SOURCE tree if anything ever runs there, and a `.pyc` read as text is a
    `UnicodeDecodeError` in a test whose failure message is then about nothing.
    """
    return [
        path
        for path in sorted(TUI_SKELETON.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]


@pytest.fixture()
def tree(spec, tmp_path) -> Path:
    """A rendered terminal tree. `skeleton=` is explicit because there is no
    `tui` target module to resolve it from yet — see this file's docstring."""
    render_skeleton(spec, tmp_path, skeleton=TUI_SKELETON)
    return tmp_path


# ── the tree ─────────────────────────────────────────────────────────────


def test_the_skeleton_is_there_and_is_small():
    """Five files became nineteen, and the smallness is a finding in the
    target's favour rather than a coincidence: the web skeleton is 24 files and
    most of the difference is Docker."""
    assert TUI_SKELETON.is_dir()
    assert (TUI_SKELETON / "app" / "main.py").exists()
    assert (TUI_SKELETON / "app" / "db.py").exists()
    assert (TUI_SKELETON / "app" / "base.py").exists()
    assert (TUI_SKELETON / "tests" / "conftest.py").exists()


def test_the_terminal_tree_has_none_of_the_web_machinery():
    """No compose file, no Dockerfile, no port. Asserted rather than assumed,
    because the reason to have this target at all is that a single process with
    a SQLite file has nothing to boot, wait for, publish or orphan."""
    for absent in ("compose.yml", "Dockerfile", ".env.example"):
        assert not (TUI_SKELETON / absent).exists(), f"{absent} has no business in a one-process tree"
    bodies = "\n".join(path.read_text() for path in _source_files())
    assert "@@PORT@@" not in bodies, "a terminal app does not listen on anything"


def test_every_token_has_a_value(spec):
    values = set(substitutions(spec))
    for path in _source_files():
        found = {m.group(1) for m in TOKEN_RE.finditer(path.read_text())}
        assert found <= values, f"{path} uses unknown placeholder(s) {found - values}"


def test_the_rendered_tree_has_no_placeholders_left(tree):
    checked = scanned(
        (p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts),
        "placeholders in the rendered skeleton",
    )
    for path in checked:
        assert not TOKEN_RE.search(path.read_text()), f"{path} still contains a placeholder"


def test_the_generated_files_are_the_ones_that_carry_the_banner():
    """Both directions, so neither list can drift alone.

    A skeleton file that grows a banner would be silently rewritten by a pass;
    a generated file that loses one would be hand-editable and then quietly
    overwritten. Both are invisible until it happens to somebody.
    """
    bannered = {
        path.relative_to(TUI_SKELETON).as_posix()
        for path in _source_files()
        if "GENERATED by proto-pilot" in path.read_text().split("\n", 3)[0]
    }
    assert bannered == set(GENERATED)


def test_the_smoke_helper_is_skeleton_and_not_generated():
    """The whole point of Phase 1's finding. `tests/screen.py` is copied
    byte-for-byte like everything else that is known to work — a helper the
    model rewrites per prototype is a helper it gets wrong per prototype, which
    is precisely what was measured happening three times out of three."""
    helper = TUI_SKELETON / "tests" / "screen.py"
    assert helper.exists()
    assert "GENERATED by proto-pilot" not in helper.read_text()
    assert helper.name not in {Path(p).name for p in GENERATED}


# ── it boots, and its own suite is green ─────────────────────────────────


def test_the_bare_skeleton_passes_its_own_tests(tree):
    """The tree's three non-generated tests, run as the tree runs them.

    A subprocess rather than in-process: `tests/conftest.py` redirects `APP_DB`
    before `app.db` is imported anywhere, and that ordering is the only fragile
    thing in the file. Importing it into this suite would either break it or
    prove nothing about it.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "tests/"],
        cwd=str(tree),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"the bare terminal skeleton is red:\n{result.stdout}\n{result.stderr}"


# ── the helper can see what the app is showing ───────────────────────────
#
# The `helper` fixture moved to `tests/conftest.py` when the console tests
# needed the same reader: `Static.renderable` does not exist on the Textual
# installed here, and two answers to "how do you read a widget's text" is how
# one of them goes stale unnoticed. It still loads `skeleton/tui/tests/screen.py`
# from the skeleton rather than copying it, for the reason its docstring gives.


def test_text_attrs_is_a_module_level_tuple(helper):
    """The shape one Phase 1 run settled on, carried forward deliberately: the
    one thing to change when Textual moves again is a value in a tuple."""
    assert isinstance(helper.TEXT_ATTRS, tuple)
    for name in ("renderable", "_content", "content"):
        assert name in helper.TEXT_ATTRS, f"{name} is one of the three names Static's text has had"


@pytest.mark.asyncio
async def test_the_helper_reads_a_static_that_renderable_cannot(helper):
    """Demonstrated on a real app, not asserted.

    The first assertion is the one that documents the bug: on the Textual
    installed here, `.renderable` does not exist at all, so a harness reading
    only that sees an empty screen and reports a working app as broken.
    """
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class OnlyAStatic(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield Static("PLEASE FIND ME", id="only")

    app = OnlyAStatic()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        widget = app.query_one("#only", Static)

        naive = helper.flatten(getattr(widget, "renderable", None))
        assert "PLEASE FIND ME" not in naive, "if this passes, `.renderable` is back and the comment above is stale"

        assert "PLEASE FIND ME" in helper.widget_text(widget)
        assert "PLEASE FIND ME" in helper.visible(app)
        assert helper.mentions(app, "please find me")
        assert "PLEASE FIND ME" in helper.buffer(app), "and it is genuinely drawn, not only held"


@pytest.mark.asyncio
async def test_the_helper_reads_a_data_table_and_a_button(helper):
    """The two widgets that worked in Phase 1 keep working. A fix for `Static`
    that broke the widgets already being read would have been a bad trade."""
    from textual.app import App, ComposeResult
    from textual.widgets import Button, DataTable

    class Mixed(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield DataTable(id="rows")
            yield Button("SAVE IT", id="save")

        def on_mount(self) -> None:
            table = self.query_one("#rows", DataTable)
            table.add_columns("Trip")
            table.add_row("Cairngorms")

    app = Mixed()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        text = helper.visible(app)
        assert "Cairngorms" in text and "Trip" in text
        assert "SAVE IT" in text


@pytest.mark.asyncio
async def test_the_helper_says_nothing_about_an_empty_screen(helper):
    """The other direction, and the one that decides whether any of this is
    worth having: a helper that finds text on a blank screen makes every
    assertion above vacuous."""
    from textual.app import App

    app = App()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert not helper.visible(app).strip()
        assert not helper.mentions(app, "anything at all")


@pytest.mark.asyncio
async def test_where_names_the_screen_and_its_ids(helper):
    """A failure message is the whole value of a smoke suite that goes red."""
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class Named(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield Static("x", id="the-thing")

    app = Named()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        report = helper.where(app)
        assert "#the-thing" in report
        assert "Screen" in report


# ── what the helper does when a widget will not answer ───────────────────
#
# Every branch below is a tolerance rather than a feature, and a tolerance is
# the thing nobody notices has stopped working. The helper's job is to be the
# one part of a generated smoke suite that cannot itself be the reason a test
# is red: a widget mid-rebuild, a property that throws, or an attribute holding
# something that is not text must each cost the harness that one widget and
# never the screen.


def unreadable_store():
    """A `DataTable.columns` store that cannot be read right now.

    A dict subclass, because that is what the attribute holds and what
    `table_text` iterates — the point is a store caught mid-rebuild, not a
    widget of an unusual class.
    """

    class Unreadable(dict):
        def values(self):
            raise RuntimeError("the row store is being rebuilt")

    return Unreadable()


def test_flatten_reads_a_rich_renderable(helper):
    """Neither of these is a `str`, and both are what a `Static` actually
    holds depending on the Textual version — which is the reason the `.plain`
    branch exists at all."""
    from rich.text import Text
    from textual.content import Content

    assert helper.flatten(Text("RICH TEXT")) == "RICH TEXT"
    assert helper.flatten(Content("TEXTUAL CONTENT")) == "TEXTUAL CONTENT"


def test_flatten_will_not_read_text_out_of_a_container(helper):
    """A list of options is not screen text, and `str()` on one would put every
    element plus its quotes and brackets into the haystack — so `mentions(app,
    "packed")` would match a widget that merely *knows* the word rather than
    one showing it. False positives are worse here than misses: the harness
    exists to catch a screen that renders nothing."""
    for container in (["packed", "unpacked"], ("packed",), {"packed": 1}, {"packed"}):
        assert helper.flatten(container) == ""


def test_flatten_never_raises_on_something_that_is_not_text(helper):
    """The fourth case the docstring names. A helper that throws here turns
    "this screen has no button" into an error nobody can read."""

    class Renderable:
        def __str__(self) -> str:
            return "STRINGIFIED"

    assert helper.flatten(None) == ""
    assert helper.flatten(Renderable()) == "STRINGIFIED"
    assert helper.flatten(7) == "7"
    # Booleans are excluded before the `str()` fallback on purpose: `True`
    # would otherwise put the word "true" on every screen holding a flag.
    assert helper.flatten(True) == ""
    assert helper.flatten(False) == ""


@pytest.mark.asyncio
async def test_a_table_mid_rebuild_says_nothing_rather_than_raising(helper):
    """A `DataTable` whose row store cannot be read right now.

    The generated list screen is usually a `DataTable`, and it is repopulated
    on every screen change — so "read while being rebuilt" is the normal
    hazard, not an exotic one.
    """
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    class WithATable(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield DataTable(id="rows")

        def on_mount(self) -> None:
            table = self.query_one("#rows", DataTable)
            table.add_columns("Trip")
            table.add_row("Cairngorms")

    app = WithATable()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#rows", DataTable)
        assert "Cairngorms" in helper.table_text(table), "the readable case first, or the next assertion is free"

        # The row store, replaced with one that will not be read right now.
        # `setattr` rather than a subclass: what breaks mid-rebuild is the
        # store, not the widget class, and a `DataTable` has to stay a
        # `DataTable` or `widget_text` never reaches this branch at all.
        setattr(table, "columns", unreadable_store())

        assert helper.table_text(table) == ""
        assert helper.widget_text(table) == ""


@pytest.mark.asyncio
async def test_one_unreadable_widget_does_not_blind_the_whole_screen(helper):
    """The assertion the two tolerances are actually for.

    A screen holding one widget that throws must still report the text on
    every other widget. The failure this prevents is the expensive one Phase 1
    measured three times: a correct app reported blank, which is
    indistinguishable from the app being broken.
    """
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable, Static

    class Moody(Static):
        """A widget whose text attribute throws when it is read."""

    def raises(_self):
        raise RuntimeError("not ready")

    # Installed with `setattr` for the same reason as above: `Moody` has to
    # stay a plain `Static` as far as the helper is concerned.
    setattr(Moody, "content", property(raises, lambda _self, _value: None))

    class Mixed(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield Static("STILL HERE", id="fine")
            yield DataTable(id="rows")
            yield Moody("MOODY BUT READABLE", id="moody")

        def on_mount(self) -> None:
            setattr(self.query_one("#rows", DataTable), "columns", unreadable_store())

    app = Mixed()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        text = helper.visible(app)

        assert "STILL HERE" in text, "one broken widget took the whole screen with it"
        # And the throwing property costs that widget only that attribute --
        # `TEXT_ATTRS` keeps reading, so its text still comes through.
        assert "MOODY BUT READABLE" in text
        assert helper.mentions(app, "still here", "moody but readable")
