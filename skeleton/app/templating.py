"""One Jinja environment, shared.

`app_name` is registered as a global rather than passed by each route: a
generated route that forgets it would render a page with a blank header, and
that is a bug class worth deleting rather than testing for.
"""

from __future__ import annotations

from pathlib import Path

from app.settings import settings
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["app_purpose"] = settings.app_purpose
