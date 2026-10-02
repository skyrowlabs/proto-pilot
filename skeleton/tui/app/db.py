"""Engine, session, declarative base -- SQLite in one file, no server.

The web skeleton's analogue talks to Postgres in a second container. This one
opens a file. That difference is most of the argument for the terminal target
and it is the reason `compose.yml`, the health wait and the port allocation
have no counterpart here.

There are no migrations, for the same reason as on the web side: the schema is
generated whole every time it changes, so `create_all()` against a fresh file
is the entire story.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

#: Overridable so the test suite gets a fresh database per run without the
#: application knowing it is under test. The default sits next to the tree.
DB_PATH = Path(os.environ.get("APP_DB") or (Path(__file__).resolve().parent.parent / "@@APP_SLUG@@.sqlite3"))

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

# expire_on_commit=False so a widget can still read attributes off an object
# after the screen committed it -- the default expires them and the next
# attribute access raises inside a render, which in a TUI shows up as a
# stack trace over the top of the app.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass


@contextmanager
def session() -> Iterator[Session]:
    """A session, closed on the way out. The terminal analogue of `get_db`.

    A context manager rather than a generator dependency because there is no
    framework here to resolve one: a screen opens a session when it needs the
    database and closes it before it returns.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
