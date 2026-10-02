"""Not generated. If this fails, the skeleton is broken rather than the app.

The terminal counterpart of the web skeleton's `test_health.py`, and it checks
the same two things one medium over: the application starts, and the fixed
parts of the tree are wired to each other.
"""

from __future__ import annotations

import pytest

from tests.screen import buffer, screen_text, where

pytestmark = pytest.mark.asyncio


async def test_the_app_starts_and_paints_something(app) -> None:
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        drawn = buffer(app)
        assert drawn.strip(), f"the app started and rendered an empty screen; {where(app)}"


async def test_the_first_screen_has_readable_text(app) -> None:
    """Not the same assertion as the one above, and the difference is the point.

    A screen can paint chrome — a header, a footer, a border — and hold no text
    at all. `screen_text` reads the widgets rather than the pixels, so this
    fails for an app that draws a frame around nothing.
    """
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert screen_text(app.screen).strip(), f"nothing on the first screen holds any text; {where(app)}"


async def test_the_database_file_is_created_on_mount(app) -> None:
    """`on_mount` runs `create_all` and `seed`. There are no migrations, so this
    is the whole of the schema story, and it happens at start or not at all."""
    from app.db import DB_PATH

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert DB_PATH.exists(), f"the app mounted but never created {DB_PATH}"
