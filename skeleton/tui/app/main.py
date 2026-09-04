"""Application entry point. Generated code is imported here; this file is not.

The whole of what `main.py`, `compose.yml`, the Dockerfile and the `/healthz`
route do on the web side, in one class: create the tables, seed them, show the
first screen.
"""

from __future__ import annotations

import app.models  # noqa: F401  -- import registers tables on Base.metadata
from app.db import Base, engine, session
from app.screens import HomeScreen
from app.seed import seed
from textual.app import App


class TerminalApp(App):
    """@@APP_NAME@@."""

    TITLE = "@@APP_NAME@@"
    SUB_TITLE = "@@APP_PURPOSE@@"
    CSS_PATH = "app.tcss"

    def get_default_screen(self) -> HomeScreen:
        """`HomeScreen` **is** the bottom of the stack, rather than sitting on it.

        This used to be `self.push_screen(HomeScreen())` in `on_mount`, and the
        difference is not stylistic. `App` always keeps a screen of its own at
        the bottom, so anything pushed on mount sits at depth two -- and
        `AppScreen.action_back`, whose whole job is to refuse to pop the last
        screen, then saw a stack it was allowed to pop. Escape on the home
        screen popped to Textual's blank default and the app went empty, which
        is exactly what that guard exists to prevent.

        Fixed here rather than by counting to two in `base.py`: the depth of
        the stack is Textual's business, and `Static`'s text attribute has
        moved three times in this file's lifetime already. A screen that is the
        default screen is one deep whatever the framework does next.

        Ordering, which is the one thing this costs: Textual calls this before
        `App.on_mount`, and the screen's own `compose()` and `on_mount()` after
        it -- so the tables below still exist before any screen queries them.
        `tests/test_boots.py` holds that, and the terminal brief already forbids
        a screen from touching the database in `__init__` or `compose()`.
        """
        return HomeScreen()

    def on_mount(self) -> None:
        Base.metadata.create_all(bind=engine)
        with session() as db:
            seed(db)


def main() -> None:
    TerminalApp().run()


if __name__ == "__main__":
    main()
