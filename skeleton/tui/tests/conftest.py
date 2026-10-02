"""Not generated.

The terminal analogue of the web skeleton's conftest, and deliberately the same
shape: one database for the run, an application object per test, and a `db`
session that is a *different* session from the one the app uses -- so a test
that reads after the app wrote has to `rollback()` first, exactly as it does on
the web side.

The database is redirected before `app.db` is imported anywhere. That ordering
is the only fragile thing in this file: `app.db` resolves `APP_DB` at import
time, and pytest imports this module before any test module, which is what
makes it work.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_DB", str(Path(tempfile.mkdtemp(prefix="apptest-")) / "test.sqlite3"))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import TerminalApp  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


@pytest.fixture()
def app() -> TerminalApp:
    """A fresh application object.

    Not a running one: `async with app.run_test() as pilot:` is what starts it,
    and a test that never starts it is a test that never touched the app.
    """
    return TerminalApp()


@pytest.fixture()
def db() -> Iterator[Session]:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db_session:
        yield db_session
