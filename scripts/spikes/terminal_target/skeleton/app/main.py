"""Application entry point. Generated code is imported here; this file is not.

The whole of what `main.py`, `compose.yml`, the Dockerfile and the `/healthz`
route do on the web side, in one class: create the tables, seed them, show the
first screen.
"""

from __future__ import annotations

import app.models  # noqa: F401  -- import registers tables on Base.metadata

#     ^ `import app.models` rather than the web skeleton's `from app import models`:
#       this tree lives under `scripts/`, which pyright type-checks, and `models` is
#       generated -- so the `from` form is an attribute pyright can see is missing
#       while the module form is an import it is configured not to resolve.
from app.db import Base, engine, session
from app.screens import HomeScreen
from app.seed import seed
from textual.app import App


class TerminalApp(App):
    """@@APP_NAME@@."""

    TITLE = "@@APP_NAME@@"
    SUB_TITLE = "@@APP_PURPOSE@@"
    CSS_PATH = "app.tcss"

    def on_mount(self) -> None:
        Base.metadata.create_all(bind=engine)
        with session() as db:
            seed(db)
        self.push_screen(HomeScreen())


def main() -> None:
    TerminalApp().run()


if __name__ == "__main__":
    main()
