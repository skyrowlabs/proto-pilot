"""Probe for `skeleton/tui/app/base.py`, run INSIDE a rendered terminal tree.

**Not collected by this repository's suite**, and the filename is what keeps it
out: it does not match `test_*.py`, so neither pytest nor
`tests/test_marker_coverage.py` sees it. It imports `app.base`, which does not
exist until the skeleton has been rendered somewhere.

`tests/test_tui_base_screen.py` copies this file into a rendered tree and runs
that tree's own pytest. That is the same discipline `tests/test_tui_skeleton.py`
uses for `tests/screen.py` and it is here for the same reason: a copied fixture
stays green while the shipped file rots. It also gets the tree's `conftest.py`
for free, which is the only thing that redirects `APP_DB` before `app.db` is
imported — running these assertions in the outer suite would either break that
ordering or prove nothing about it.
"""

from __future__ import annotations

import pytest
from app.base import AppScreen
from app.db import Base, engine
from sqlalchemy import text
from textual.app import App, ComposeResult, ScreenStackError
from textual.widgets import Static

from tests.screen import screen_text

pytestmark = pytest.mark.asyncio


class Root(AppScreen):
    """The bottom of the stack."""

    def compose(self) -> ComposeResult:
        yield Static("ROOT SCREEN", id="root")


class Leaf(AppScreen):
    """Pushed on top of `Root`, and the thing Escape is supposed to remove."""

    def compose(self) -> ComposeResult:
        yield Static("LEAF SCREEN", id="leaf")


class OneScreen(App):
    """An app whose only screen is an `AppScreen` — the last-screen case.

    `get_default_screen` rather than `push_screen`, because that is the only
    way a Textual stack is ever one deep: `App` always puts a screen at the
    bottom, and anything pushed on mount sits above it.
    """

    CSS = ""

    def get_default_screen(self) -> Root:
        return Root()


class TwoScreens(OneScreen):
    def on_mount(self) -> None:
        self.push_screen(Leaf())


# ── action_back ──────────────────────────────────────────────────────────


async def test_popping_the_last_screen_is_what_the_guard_is_for() -> None:
    """The reason the branch exists, demonstrated rather than described.

    If Textual ever stops raising here, the guard's justification is gone and
    somebody should be told — a workaround outliving the thing it worked
    around is how a defence becomes a decoration.
    """
    app = OneScreen()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert len(app.screen_stack) == 1
        with pytest.raises(ScreenStackError):
            app.pop_screen()


async def test_back_on_the_last_screen_leaves_the_app_where_it_was() -> None:
    """Escape on the only screen does nothing at all — it does not crash, it
    does not exit, and it does not leave a screen with nothing on it. A global
    binding that fails any of those three fails the boot check for a reason
    that has nothing to do with the generated app."""
    app = OneScreen()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 1
        assert isinstance(app.screen, Root)
        assert "ROOT SCREEN" in screen_text(app.screen)
        assert app.is_running


async def test_back_pops_one_screen_when_there_is_somewhere_to_go() -> None:
    app = TwoScreens()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert "LEAF SCREEN" in screen_text(app.screen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, Root)
        assert "ROOT SCREEN" in screen_text(app.screen)
        assert "LEAF SCREEN" not in screen_text(app.screen)


async def test_back_pops_exactly_one_screen_per_press() -> None:
    """Two pushes and one Escape leaves one push standing. A binding that
    unwound the whole stack would look identical on a two-screen app."""
    app = TwoScreens()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(Leaf())
        await pilot.pause()
        assert len(app.screen_stack) == 3

        await pilot.press("escape")
        await pilot.pause()

        assert len(app.screen_stack) == 2
        assert "LEAF SCREEN" in screen_text(app.screen)


async def test_quit_ends_the_app_from_any_screen() -> None:
    """The other binding every screen inherits."""
    app = TwoScreens()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running


# ── db() ─────────────────────────────────────────────────────────────────


async def test_db_hands_a_screen_a_usable_session() -> None:
    """A handler asks for a session and gets one that can talk to the file the
    rest of the app is using — not a second engine of its own."""
    Base.metadata.create_all(bind=engine)
    app = OneScreen()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, Root)
        with screen.db() as db:
            assert db.execute(text("select 1")).scalar() == 1
            assert str(db.get_bind().url) == str(engine.url)


async def test_db_gives_the_connection_back_when_the_handler_returns() -> None:
    """The whole reason it is a context manager. A screen that leaks a
    connection per keypress exhausts the pool in a session nobody would think
    to blame on the base class.
    """
    Base.metadata.create_all(bind=engine)
    app = OneScreen()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, Root)
        before = engine.pool.checkedout()

        with screen.db() as db:
            db.execute(text("select 1"))
            assert engine.pool.checkedout() == before + 1

        assert engine.pool.checkedout() == before


async def test_db_gives_the_connection_back_when_the_handler_raises() -> None:
    """The case that actually leaks. A screen handler that throws mid-write is
    the normal way a prototype fails, and it must not also take the pool with
    it."""
    Base.metadata.create_all(bind=engine)
    app = OneScreen()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, Root)
        before = engine.pool.checkedout()

        with pytest.raises(RuntimeError):
            with screen.db() as db:
                db.execute(text("select 1"))
                raise RuntimeError("a handler blew up")

        assert engine.pool.checkedout() == before
