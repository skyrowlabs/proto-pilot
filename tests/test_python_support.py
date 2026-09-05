"""The versions CI tests, against the versions the package claims to support.

`pyproject.toml` publishes `requires-python = ">=3.11"`. That is a promise to
anyone who installs proto.pilot, and it is the kind of promise nothing checks:
metadata is not executed, so a floor that has quietly stopped working reads
exactly like one that works.

CI's matrix is what turns the promise into a check -- but only while the two
agree, and they are in different files with no link between them. The matrix
went from four versions to two on 2026-09-04 (the reasoning is in
`.github/workflows/ci.yml`, at the job), and a two-entry list is where the drift
starts to matter: with the interior gone, the floor job *is* the evidence for
the floor claim, and losing it silently would leave the claim standing with
nothing behind it.

So this is a contract between two source files, checked in the only place it is
visible -- the same shape as `test_forwarded_flags_are_accepted` in
`test_cli_smoke.py`, and for the same reason: neither file can be run to reveal
its disagreement with the other.

It fails in both directions on purpose:

* raise `requires-python` and leave CI testing the old floor -> red, because CI
  is now proving something narrower than the package claims;
* drop the floor from the matrix and leave the metadata -> red, because the
  claim has lost its evidence.

The ceiling is deliberately not asserted. "The newest Python that exists" is not
a fact this repo can look up offline, and a test that guesses it would go red on
release day for a reason that has nothing to do with this code.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

#: The matrix is a one-line flow sequence: `python: ['3.11', '3.14']`. Read with
#: `re` rather than PyYAML because PyYAML is not a dependency of this repo and
#: adding one to read a single line would be the larger change -- `allowlist.py`
#: parses its YAML the same way, for the same reason. Anchored on `python:` so
#: it cannot pick up the `python-version:` lines the single-version jobs use.
_MATRIX = re.compile(r"^\s*python:\s*\[(?P<versions>[^\]]+)\]\s*$", re.MULTILINE)


def _version(text: str) -> tuple[int, ...]:
    """`"3.11"` -> `(3, 11)`, so ordering is numeric.

    Sorting these as strings puts `"3.9"` above `"3.14"`, which would make a
    floor check quietly compare the wrong two versions.
    """
    return tuple(int(part) for part in text.strip().strip("'\"").split("."))


def _pretty(version: tuple[int, ...]) -> str:
    """`(3, 11)` -> `"3.11"`, for a failure message that names what to go edit."""
    return ".".join(str(part) for part in version)


def _matrix_versions() -> list[tuple[int, ...]]:
    found = _MATRIX.search(WORKFLOW.read_text(encoding="utf-8"))
    if not found:
        return []
    return sorted(_version(v) for v in found.group("versions").split(","))


def _declared_floor() -> tuple[int, ...]:
    metadata = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    requires = metadata["project"]["requires-python"]
    found = re.search(r">=\s*(\d+\.\d+)", requires)
    assert found, f"requires-python is {requires!r}, which states no floor"
    return _version(found.group(1))


def test_the_matrix_scan_found_something():
    """A scan that silently matches nothing is a test that always passes.

    Every assertion below is over `_matrix_versions()`, so an empty list would
    make the floor check vacuously true and this file would go green while
    reading nothing at all.
    """
    versions = _matrix_versions()
    assert versions, f"no `python: [...]` matrix found in {WORKFLOW} — the scan is wrong, not CI"
    assert len(versions) >= 2, (
        f"the matrix is {versions}, a single version. A one-entry matrix cannot "
        "prove a range; either add the ceiling back or narrow requires-python "
        "to that one version."
    )


def test_ci_tests_the_floor_the_package_claims():
    """The lowest tested version is the lowest supported version.

    Not "at most" and not "at least" -- exactly. Testing *below* the claimed
    floor is as wrong as testing above it: it spends a job proving support for a
    version the metadata tells installers they will not get.
    """
    declared = _declared_floor()
    tested = _matrix_versions()[0]
    assert tested == declared, (
        f'`pyproject.toml` claims `requires-python = ">={_pretty(declared)}"` but the '
        f"CI matrix in {WORKFLOW.relative_to(PROJECT_ROOT)} starts at {_pretty(tested)}.\n"
        "Change whichever one is wrong — they are a single decision written twice."
    )
