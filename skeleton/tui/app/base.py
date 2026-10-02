"""The base screen every generated screen subclasses.

The counterpart of `base.html`: it owns the chrome (header, footer, the keys
that are the same on every screen) so a generated screen writes only what is
its own. Unlike `base.html` it is a class rather than a set of blocks, so the
generated code `super()`s into it instead of filling it in.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.db import session
from sqlalchemy.orm import Session
from textual.binding import Binding
from textual.screen import Screen


class AppScreen(Screen):
    """Header, footer, and the two keys that mean the same thing everywhere."""

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("escape", "back", "Back"),
    ]

    @contextmanager
    def db(self) -> Iterator[Session]:
        """A database session for the duration of a handler."""
        with session() as db:
            yield db

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_back(self) -> None:
        """Pop back one screen, or do nothing when this is the only one.

        Doing nothing is the point: `pop_screen` on the last screen raises,
        and a global Escape binding that crashes the app on the home screen is
        the most reliable way to fail the boot check for a reason that has
        nothing to do with the app.

        The comparison is to one because `app/main.py` returns `HomeScreen`
        from `get_default_screen()` rather than pushing it. That is the half of
        this guard that is not in this file, and it was wrong for a while:
        `App` always keeps a screen of its own at the bottom, so a home screen
        that is *pushed* sits at depth two, this branch never fires, and Escape
        pops to a blank default screen -- precisely the failure the paragraph
        above says it prevents. Do not "fix" that by counting to two here. The
        depth of Textual's stack is Textual's business; a screen that is the
        default screen is one deep whatever the framework does next.
        """
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
