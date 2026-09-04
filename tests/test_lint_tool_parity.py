"""The lint pins agree everywhere they are written down.

Two versions of a formatter disagree about real formatting. When
`.pre-commit-config.yaml` and CI hold different pins, a file passes locally and
fails in CI with a diff nobody can explain from the error message — the tool
name is the same, so the version never occurs to anyone.

`.pre-commit-config.yaml` is the source of truth. Everything else mirrors it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import PROJECT_ROOT, SCRIPTS_DIR  # noqa: E402

PRECOMMIT = PROJECT_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS = SCRIPTS_DIR / "requirements.txt"

#: repo slug fragment -> the name it goes by in requirements.txt
TOOLS = {"flake8": "flake8", "black": "black", "isort": "isort", "pyright": "pyright"}


def _precommit_pins() -> dict:
    text = PRECOMMIT.read_text(encoding="utf-8")
    pins = {}
    # `rev:` for hosted repos; `pyright@X.Y.Z` for the local node-hosted hook.
    for repo, rev in re.findall(r"- repo: https://\S*?/([\w.-]+)\n\s+rev: v?([\d.]+)", text):
        for tool in TOOLS:
            if tool in repo.lower():
                pins[tool] = rev
    for tool, version in re.findall(r"'(\w+)@([\d.]+)'", text):
        if tool in TOOLS:
            pins[tool] = version
    return pins


def _requirements_pins() -> dict:
    pins = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([\d.]+)", line.strip())
        if match and match.group(1) in TOOLS.values():
            pins[match.group(1)] = match.group(2)
    return pins


def test_every_lint_tool_is_pinned_in_precommit():
    pins = _precommit_pins()
    missing = sorted(set(TOOLS) - set(pins))
    assert not missing, f"Unpinned in .pre-commit-config.yaml (the source of truth): {missing}"


def test_requirements_match_precommit():
    precommit, requirements = _precommit_pins(), _requirements_pins()
    mismatched = {
        tool: (precommit[tool], requirements.get(tool))
        for tool in precommit
        if requirements.get(tool) != precommit[tool]
    }
    assert not mismatched, (
        "scripts/requirements.txt disagrees with .pre-commit-config.yaml "
        f"(pre-commit, requirements): {mismatched}\n"
        ".pre-commit-config.yaml is the source of truth — update requirements.txt."
    )


def test_pyright_has_something_to_analyse() -> None:
    """A type checker over zero files prints `0 errors` and passes.

    `pyright` reports its verdict and its scope in the same breath -- "0 errors,
    0 warnings, 0 informations" is what a clean run and an empty run both look
    like, and `pp check lint` reads only the exit code. Rename or move a
    directory named in `include` and the gate stays green having checked
    nothing, with no line of output that differs.

    This asserts the precondition instead of the result, so it stays fast: every
    path in `include` resolves and holds at least one `.py`. The realistic way
    this check silently empties is a directory that moved, which is exactly what
    that catches -- and it needs no pyright installed, unlike asserting
    `filesAnalyzed` from `--outputjson` (72 here, at the time of writing).

    The class is skeletor's framing, and it generalises past this one tool: a
    negative result from a matcher means either the thing is absent or the
    matcher is blind, and nothing in the output distinguishes them. The same
    shape put `check docs` at "4 doc(s), all registered" in a tree holding 24.
    """
    config = PROJECT_ROOT / "pyrightconfig.json"
    if not config.exists():
        pytest.skip("no pyrightconfig.json")

    # JSONC: the file carries `//` line comments on purpose, so strip them.
    raw = re.sub(r"^\s*//.*$", "", config.read_text(encoding="utf-8"), flags=re.MULTILINE)
    included = json.loads(raw).get("include", [])
    assert included, "pyrightconfig.json names no include paths — it would check nothing"

    empty = [
        name for name in included if not (PROJECT_ROOT / name).exists() or not any((PROJECT_ROOT / name).rglob("*.py"))
    ]
    assert not empty, (
        "pyright `include` paths that resolve to no Python:\n  "
        + "\n  ".join(empty)
        + "\n\npyright would report 0 errors over 0 files and `pp check lint` would pass."
    )
