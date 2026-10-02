"""The stage that can see JavaScript.

Every other stage is blind to the browser: /healthz returns 200 for a page
that paints nothing, and the smoke suite runs through an in-process
TestClient that never executes a script tag. Once a prototype can paint a
canvas, that gap is the difference between "green" meaning a person can click
through it and "green" meaning the server did not crash.

These tests use the result objects rather than a live browser, so the suite
still runs with no chromium and no network.
"""

from __future__ import annotations

import pytest

from protopilot.browser import BrowserResult, PageResult
from protopilot.spec import Screen, checkable_paths

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


def test_a_page_that_loaded_and_painted_is_ok():
    assert PageResult(path="/", status=200, painted=True).ok


def test_a_blank_canvas_fails_even_though_the_server_was_fine():
    # HTTP 200, no exception, nothing on screen: the exact failure /healthz
    # and the smoke suite both report as success.
    page = PageResult(path="/board", status=200, painted=False)
    assert not page.ok
    assert "rendered nothing visible" in BrowserResult(False, [page]).report()


def test_a_javascript_error_fails_a_page_that_returned_200():
    page = PageResult(path="/board", status=200, painted=True, errors=["drawBoard is not defined"])
    assert not page.ok
    report = BrowserResult(False, [page]).report()
    assert "JavaScript error" in report and "drawBoard is not defined" in report


def test_a_load_failure_is_not_reported_as_a_script_error():
    # Calling a connection refusal a JavaScript error sends the repair pass
    # hunting a bug that does not exist.
    page = PageResult(path="/", load_error="net::ERR_CONNECTION_REFUSED")
    assert not page.ok
    report = BrowserResult(False, [page]).report()
    assert "ERR_CONNECTION_REFUSED" in report
    assert "JavaScript error" not in report


def test_a_4xx_fails_the_page():
    assert not PageResult(path="/games/1", status=404, painted=True).ok


def test_report_is_quiet_when_everything_passed():
    good = [PageResult(path="/", status=200, painted=True)]
    assert "every screen loaded" in BrowserResult(True, good).report()


def test_unavailable_is_reported_rather_than_passed():
    # A machine without a browser has not verified the browser. Saying so is
    # the difference between an unchecked run and a green one.
    result = BrowserResult(ok=False, unavailable="playwright is not installed")
    assert not result.ok
    assert "skipped" in result.report()


@pytest.fixture()
def screens_spec(spec):
    spec.screens = [
        Screen(name="Home", path="/", kind="custom"),
        Screen(name="Trips", path="/trips", kind="list"),
        Screen(name="Trip", path="/trips/{row_id}", kind="detail"),
        Screen(name="Board", path="/games/{row_id}/board/{side}", kind="custom"),
    ]
    return spec


def test_checkable_paths_fills_row_id_and_drops_what_it_cannot_fill(screens_spec):
    # A made-up value for {side} would 404 and be reported as a broken screen,
    # which is worse than not checking it.
    assert checkable_paths(screens_spec) == ["/", "/trips", "/trips/1"]
