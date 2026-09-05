"""`ui` is unscheduled here because it is empty — so keep it empty, or fix it.

`cli/test_cmds.py` departs from the template on one row: upstream ships
`"ui": Suite(..., scheduled=True)` plus a CI job, and this repo declares
`scheduled=False` with no job. `tests/test_ci_runs_every_suite.py` accepts
that — its two directions ask only that the registry and the workflows agree,
and with no job and no schedule they do.

They agree about a suite with nothing in it, which is the whole basis of the
claim and is not something either direction checks.

## Why that is a hole rather than pedantry

`scheduled=False` carries two justifications that look identical in the source
and behave nothing alike:

* **`manual` cannot run unattended** — it costs money or needs a person. True
  today, true after it gains fifty tests, true forever. The row is a fact about
  the suite's nature.
* **`ui` is empty here** — a fact about the suite's *contents*, and contents
  change. Mark one test `ui` and the row becomes false with no edit to it, no
  workflow change, and nothing red anywhere.

The second case is exactly the defect proto.pilot reported upstream and skeletor
fixed in v0.4.3: a marker that no job selects deselects its tests from the job
that would otherwise have run them, so CI reports green over a smaller set. We
reintroduce it the moment we mark something `ui` — under our own exemption, and
therefore past the gate that was built to catch it.

So the departure has to carry its own guard. This is that guard, and it is the
`scanned()` rule turned on a claim rather than on a scan: an exemption whose
stated reason nothing rechecks is an exemption that outlives its reason.

The fix when this goes red is not to delete this file. It is one of:

* the test does not need a display — put it on `unit`, where the console tests
  already are, or
* it does — restore the template's `ui` job (skeletor's
  `template/core/.github/workflows/ci.yml`) and set `scheduled=True` back.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cli.test_cmds import SUITES  # noqa: E402

#: pytest's exit code for "the marker selected nothing". The CI job the template
#: ships treats it as a reported non-run rather than a pass; here it is the
#: assertion itself.
NO_TESTS_COLLECTED = 5


def _collect(marker: str) -> subprocess.CompletedProcess:
    """Ask pytest what `-m <marker>` selects, without running any of it."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-m", marker, "--collect-only", "-q"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_row_this_file_guards_still_says_what_it_says():
    """If the row goes back to `scheduled=True`, this guard is the stale one.

    Without this, restoring the template's job and schedule would leave a file
    behind demanding the suite stay empty — which is the opposite of what that
    row would then mean, and it would fail the first `ui` test somebody wrote
    while pointing at a comment that no longer exists.
    """
    row = SUITES.get("ui")
    assert row is not None, "the `ui` row is gone from cli/test_cmds.py; this file guards nothing"
    assert not row.scheduled, (
        "`ui` is `scheduled=True` again, so a workflow is obliged to run it and "
        "the suite is allowed to have tests. Delete this file — its premise is gone."
    )


def test_nothing_is_marked_ui():
    """The claim in the registry row, rechecked against the tree.

    Collection rather than a text search for `pytest.mark.ui`: a marker can be
    applied by `pytestmark`, by a decorator, by `pytest_collection_modifyitems`
    or through a fixture, and only pytest knows the answer for all of them.
    """
    result = _collect("ui")
    assert result.returncode == NO_TESTS_COLLECTED, (
        "`cli/test_cmds.py` declares the `ui` suite `scheduled=False` on the stated "
        "grounds that it is EMPTY, and no workflow selects `-m ui`. Something is now "
        f"marked `ui`, so it runs nowhere in CI:\n\n{result.stdout[-1500:]}\n"
        "Either move it to `unit` (a headless Textual pilot needs no display and "
        "belongs there), or restore the template's `ui` job and set `scheduled=True`."
    )
