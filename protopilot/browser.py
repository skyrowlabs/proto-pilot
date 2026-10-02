"""The stage that can see JavaScript.

Everything else proto-pilot checks is blind to the browser. `/healthz` returns
200 for a page that renders nothing, and the smoke suite runs through
FastAPI's in-process TestClient, which never executes a script tag. That was
fine while the stack had no JavaScript in it; the moment a prototype can paint
a canvas, "green" would have meant "the server did not crash" while the page
was a blank rectangle.

So this loads every screen in the spec in a real browser and asks the two
questions the other stages cannot: did anything throw, and did anything
actually appear.

The browser runs on the host, against the published port, not inside the app
image. The repair loop rebuilds that image on every attempt -- the Dockerfile
calls it the difference between 4s and 90s -- and a chromium layer would be
paid once per attempt per prototype rather than once per machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Chromium says a lot that is not a bug: a missing favicon on every page, and
# blocked requests the container was never going to serve.
IGNORED = (
    "favicon.ico",
    "net::ERR_",
    "Failed to load resource: the server responded with a status of 404",
)


@dataclass
class PageResult:
    path: str
    status: int | None = None
    # Kept apart from `errors`: a page that never loaded has no JavaScript
    # problem, and calling a connection refusal a script error sends the
    # repair pass looking for a bug that is not there.
    load_error: str = ""
    errors: list[str] = field(default_factory=list)
    painted: bool = False
    text_length: int = 0

    @property
    def ok(self) -> bool:
        return (
            not self.load_error and self.status is not None and self.status < 400 and not self.errors and self.painted
        )


@dataclass
class BrowserResult:
    ok: bool
    pages: list[PageResult] = field(default_factory=list)
    unavailable: str = ""

    def report(self) -> str:
        if self.unavailable:
            return f"browser check skipped: {self.unavailable}"
        lines = []
        for page in self.pages:
            if page.ok:
                continue
            why = []
            if page.load_error:
                why.append(page.load_error)
            elif page.status is None:
                why.append("did not load")
            elif page.status >= 400:
                why.append(f"HTTP {page.status}")
            if not page.painted:
                why.append("rendered nothing visible")
            if page.errors:
                why.append(f"{len(page.errors)} JavaScript error(s)")
            lines.append(f"{page.path}: {', '.join(why)}")
            for err in page.errors[:5]:
                lines.append(f"    js: {err}")
        return "\n".join(lines) or "every screen loaded and painted"


def _executable() -> str | None:
    """Prefer a system chromium; Playwright's own download is ~400MB."""
    override = os.environ.get("PROTOPILOT_CHROMIUM")
    if override:
        return override
    for candidate in (
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
    ):
        if Path(candidate).exists():
            return candidate
    return None  # let Playwright use its bundled build if it has one


def available() -> str:
    """Empty string when the check can run; otherwise why it cannot."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return 'playwright is not installed (`pip install -e ".[browser]"`)'
    return ""


def check(base_url: str, paths: list[str], timeout_ms: int = 15000) -> BrowserResult:
    """Load each path and report what threw and what painted."""
    why = available()
    if why:
        return BrowserResult(ok=False, unavailable=why)

    from playwright.sync_api import sync_playwright

    results: list[PageResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=_executable(),
            # No sandbox: this runs in CI and in containers as often as not,
            # and the pages it loads are ones we just generated ourselves.
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for path in paths:
                results.append(_load(browser, base_url, path, timeout_ms))
        finally:
            browser.close()

    return BrowserResult(ok=all(r.ok for r in results), pages=results)


def _load(browser, base_url: str, path: str, timeout_ms: int) -> PageResult:
    result = PageResult(path=path)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    def note(message: str) -> None:
        if not any(skip in message for skip in IGNORED):
            result.errors.append(message)

    page.on("console", lambda m: note(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: note(str(e)))

    try:
        response = page.goto(f"{base_url}{path}", wait_until="load", timeout=timeout_ms)
        result.status = response.status if response else None
        # Give a script that paints on load a moment to actually paint.
        page.wait_for_timeout(400)
        result.text_length = len((page.inner_text("body") or "").strip())
        result.painted = _painted(page, result.text_length)
    except Exception as exc:  # noqa: BLE001 - a failed load is a result
        # Playwright appends a multi-line call log; the first line is the
        # part that says what went wrong.
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        result.load_error = first[:200]
    finally:
        page.close()
    return result


PAINTED_JS = """
() => {
  const canvases = Array.from(document.querySelectorAll('canvas'));
  if (canvases.length === 0) return null;      // nothing to judge
  // A canvas that was never drawn on is the exact failure the server cannot
  // see: every test passes and the page shows a blank rectangle.
  return canvases.some(c => {
    if (!c.width || !c.height) return false;
    try {
      const ctx = c.getContext('2d');
      if (!ctx) return true;                    // webgl etc: assume drawn
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
      return false;
    } catch (e) { return true; }                // tainted: assume drawn
  });
}
"""


def _painted(page, text_length: int) -> bool:
    """Did the page put anything on screen?

    Text or an SVG is enough. A canvas is judged on its pixels, because an
    undrawn canvas is precisely the thing every other stage reports as fine.
    """
    canvas_drawn = page.evaluate(PAINTED_JS)
    if canvas_drawn is not None:
        return bool(canvas_drawn) or text_length > 0
    if text_length > 0:
        return True
    return page.locator("svg, img").count() > 0
