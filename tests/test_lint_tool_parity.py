"""The lint pins agree everywhere they are written down.

Two versions of a formatter disagree about real formatting. When
`.pre-commit-config.yaml` and CI hold different pins, a file passes locally and
fails in CI with a diff nobody can explain from the error message — the tool
name is the same, so the version never occurs to anyone.

**Three places decide, and none of them is canonical.** `.pre-commit-config.yaml`
pins the commit hook; `scripts/requirements.txt` pins what CI and your `.venv`
install; and what is actually installed is what `pp check` runs. This file
used to call the first one the source of truth, and both halves of that were
wrong.

It named a direction it cannot know. The governed tier's Dependabot updates
`/scripts` — pip cannot write `.pre-commit-config.yaml` — so every lint bump
arrives in `requirements.txt` first, the suite goes red, and the message said
*update requirements.txt*: revert the bot. sky.boss's pull request sat red for
six days on exactly that, `pyright 1.1.411` against `1.1.414`. Which side is
behind is a fact about the last commit, not about the files, so the message says
*make these agree* and names both.

And it compared two declarations while the value that decides the outcome sat
one call away. node-zero's two pins both said `isort==9.0.1` and this was green,
while the `.venv` that `pp check pre-push` runs held 8.0.1 — the tree
formatted under one isort in the hook and another in the check, both passed, and
the gate whose docstring is about exactly that could not see it. That is not the
account-level class that has no instrument: `importlib.metadata` answers it.
"""

from __future__ import annotations

import json
import re
import sys
from fnmatch import fnmatch
from importlib import metadata
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.paths import GITHUB_DIR, PROJECT_ROOT, REQUIREMENTS  # noqa: E402
from tests.scanning import scanned  # noqa: E402

PRECOMMIT = PROJECT_ROOT / ".pre-commit-config.yaml"

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
    assert not missing, f"Unpinned in .pre-commit-config.yaml: {missing}"


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
        "Make these agree — at whichever version you mean. If a bot just bumped one "
        "of them, that is usually the newer pin and the other file is the one behind; "
        "a pip updater can only ever write requirements.txt."
    )


def test_installed_tools_match_requirements():
    """What this interpreter has installed is what the pins say.

    Asked of the interpreter running the suite, which is the tree's `.venv` when
    the suite runs the way `pp test` runs it — the same environment
    `pp check` shells out of. A tool missing from it is reported rather than
    skipped: the question is whether the check and the hook run the same
    formatter, and "not installed here" is not a yes.
    """
    requirements = _requirements_pins()
    drift = {}
    for tool, pinned in sorted(requirements.items()):
        try:
            installed = metadata.version(tool)
        except metadata.PackageNotFoundError:
            installed = "not installed"
        if installed != pinned:
            drift[tool] = (pinned, installed)
    assert requirements, "found no lint tool pinned in scripts/requirements.txt, so this compared nothing"
    assert not drift, (
        f"{sys.executable} does not have what scripts/requirements.txt pins "
        f"(pinned, installed): {drift}\n"
        "Reinstall from scripts/requirements.txt. Until you do, the commit hook and "
        "the check format with different versions of one tool, and both pass. A "
        "major bump can reformat files, so give the reinstall its own commit if it "
        "does."
    )


def covers(entry: dict, directory: str, file: str = "requirements.txt") -> bool:
    """Whether a Dependabot entry updates `directory/file`: named there, or at an ancestor, and not excluded.

    An entry at `/` updates `scripts/requirements.txt` too (sky.boss, measured),
    so matching the directory exactly passed vacuously there. Its `exclude-paths`
    take it back out (mind-head), tried from the root and from the entry's own
    directory, which agree at `/`.
    """
    named = [entry["directory"]] if "directory" in entry else list(entry.get("directories") or [])
    path = f"{directory.strip('/')}/{file}"
    for spelled in named:
        root = "/" + str(spelled).strip("/")
        if not (root == "/" or directory == root or directory.startswith(root + "/") or fnmatch(directory, root)):
            continue
        inside = path[len(root.strip("/")) :].lstrip("/") if directory.startswith(root) else path
        excluded = any(
            fnmatch(candidate, str(pattern).strip("/")) or candidate.startswith(str(pattern).strip("/*") + "/")
            for pattern in entry.get("exclude-paths") or []
            for candidate in (path, inside)
        )
        if not excluded:
            return True
    return False


def test_dependabot_never_bumps_a_lint_pin_alone():
    """A pip update reaching the requirements file ignores every tool above.

    pip writes `requirements.txt` only, so a lint bump arrives red against
    `.pre-commit-config.yaml` and never merges (mind-head's ruff and mypy, added
    to `TOOLS` and not to the ignore list). No dependabot.yml, or no pip entry
    reaching that file, means nothing bumps these pins, and there is nothing to ask.
    """
    import yaml

    config = GITHUB_DIR / "dependabot.yml"
    if not config.exists():
        return
    directory = "/" + REQUIREMENTS.parent.relative_to(PROJECT_ROOT).as_posix()
    entries = [
        entry
        for entry in (yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("updates") or []
        if entry.get("package-ecosystem") == "pip" and covers(entry, directory)
    ]
    for entry in entries:
        ignored = {rule.get("dependency-name") for rule in entry.get("ignore") or []}
        unignored = sorted(set(TOOLS.values()) - ignored)
        assert not unignored, (
            f".github/dependabot.yml's pip update for {entry.get('directory') or entry.get('directories')} "
            f"would bump {unignored} alone; add each to its `ignore:` list, since a bump of one pin is red "
            "against the other"
        )


def test_an_entry_reaches_the_requirements_file_from_an_ancestor():
    scanned(
        [d for d in ("/", "/scripts", "scripts/", "/scr*") if covers({"directory": d}, "/scripts")],
        "spellings reaching /scripts",
        least=4,
    )
    assert covers({"directories": ["/app", "/"]}, "/scripts")
    assert not covers({"directory": "/app"}, "/scripts")


def test_an_excluded_path_is_not_reached():
    assert not covers({"directory": "/", "exclude-paths": ["scripts/**"]}, "/scripts")
    assert not covers({"directory": "/", "exclude-paths": ["scripts/requirements.txt"]}, "/scripts")
    assert covers({"directory": "/", "exclude-paths": ["app/**"]}, "/scripts")


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


def test_no_pyright_caller_resolves_its_interpreter_from_path() -> None:
    """No caller may take its interpreter from `PATH`. One place may satisfy this.

    Either the **config** pins — `venvPath` + `venv`, or `pythonPath` — or
    **every** caller passes `--pythonpath`. Stated as a disjunction because a
    tree that genuinely pins at every call site is correct, and a gate that
    forbids a working arrangement is one somebody deletes.

    `reportMissingImports` is `none`, so an interpreter without this tree's
    packages raises no import error at all: the packages become `Unknown` and
    cascade into errors in files the commit never touched. The root cause is the
    suppressed one, so what you see is a pile of plausible consequences reading
    as a broken tree rather than a broken environment. skeletor measured a
    scaffold of this template on 2026-09-07, same pyright and same project file,
    differing only in which interpreter `PATH` offered first: **27 errors**
    unpinned, **0** pinned, every one of the 27 `click` resolving to `Unknown`.

    ## Why this is here rather than arriving with the template

    The template ships this in a file this tree deletes on purpose — its other
    half duplicates `test_pyright_has_something_to_analyse` above. At the
    v0.24.0 upgrade that deletion was re-examined and held, on the finding that
    the interpreter half was already covered by the pre-flight wrapper. **That
    finding was wrong**, and the pre-flight is exactly why it looked right:
    `scripts/lint_pyright_gate.py::resolve_interpreter` prefers the config's
    venv and *falls through to `PATH`* when nothing pins, so its tests assert
    the resolution order rather than that this repository pins. Deleting
    `venvPath` and `venv` from `pyrightconfig.json` left all 725 unit tests
    green — measured on 2026-09-10, which is how this hole was found rather
    than argued.

    The general form is worth more than the fix: **a mechanism that centralises
    a decision is not a mechanism that makes it.** The wrapper made interpreter
    resolution uniform, legible and fail-closed, and none of that is the same as
    requiring the pin — but it reads as the same when you are looking for
    coverage rather than for the assertion.
    """
    from tests.test_pyright_gate_preflight import _present_callers

    config = PROJECT_ROOT / "pyrightconfig.json"
    if not config.exists():
        pytest.skip("no pyrightconfig.json")

    # JSONC: the file carries `//` line comments on purpose, so strip them.
    raw = re.sub(r"^\s*//.*$", "", config.read_text(encoding="utf-8"), flags=re.MULTILINE)
    parsed = json.loads(raw)
    if parsed.get("pythonPath") or (parsed.get("venvPath") and parsed.get("venv")):
        return

    # The caller set has an owner; this does not define a second one.
    unpinned = sorted(name for name, text in _present_callers().items() if "--pythonpath" not in text)
    assert not unpinned, (
        "pyrightconfig.json pins no interpreter and these callers do not pass "
        f"--pythonpath: {unpinned}\n"
        "Restore `venvPath` + `venv` in pyrightconfig.json, or pass --pythonpath at every "
        "call site. Unpinned, pyright checks whatever python PATH offered first and reports "
        "the fallout as errors in files your commit never touched."
    )
