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
        """
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
