"""What a terminal tree pins must be what proto.pilot verified with.

The failure this exists to prevent, and it shipped: `skeleton/tui/requirements.txt`
pinned `sqlalchemy==2.0.36`, which raises `TypeError` on import under Python
3.14. Every generated terminal app was unrunnable on this machine, and
**nothing anywhere went red** — because generation and verification run in
proto.pilot's own environment, which had 2.0.52, and the verifier boots the
tree with `sys.executable` and `PYTHONPATH` rather than installing its
`requirements.txt`. The producer and the consumer of that file never met.

That is the workspace rule in its purest form: *no repo's test suite can find a
disagreement about an artifact it publishes, because the writer and the reader
inside one repo agree by construction.* Here writer and reader were the same
repo and the same run, and the second consumer — `pip`, in the user's shell,
on the user's interpreter — was never asked.

## Why the terminal target and not the web one

The web skeleton pins exact versions too, and that is correct there: its
`Dockerfile` says `FROM python:3.12-slim`, so the interpreter is pinned
alongside them and the combination is reproducible. A terminal tree has no
container. It runs on whatever Python the person has, and it inherited a
pinning strategy from a target that controls that variable.

So the terminal pins are held to the one combination anything has ever actually
proven: the versions installed here, which are the versions every generated
tree is verified against.

## What this does not check

That the pins work on Python 3.11, or on a machine that is not this one. Only
an install can answer that, and an install needs a network. What it does answer
is the question that was silently unasked — *is what we ship what we tested?* —
which is the one that was wrong.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot import targets  # noqa: E402
from scanning import scanned  # noqa: E402

pytestmark = pytest.mark.unit

REQUIREMENTS = targets.SKELETON_ROOT / "tui" / "requirements.txt"


def pinned() -> dict:
    """`name -> version` from the shipped requirements file."""
    out = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        assert "==" in line, f"a terminal tree must pin exactly, not float: {line!r}"
        name, _, pin = line.partition("==")
        out[name.strip()] = pin.strip()
    return out


def test_every_pin_is_the_version_this_repo_verifies_with():
    """Derived from the file, compared against the environment. Neither side is
    a list somebody has to maintain, which is what let the two drift apart for
    however long they had."""
    for name, pin in scanned(pinned().items(), "pinned terminal requirements", least=2):
        try:
            installed = version(name)
        except PackageNotFoundError:  # pragma: no cover - a broken dev env
            pytest.fail(f"{name} is pinned for generated trees but not installed here; nothing verifies against it")
        assert pin == installed, (
            f"generated terminal trees pin {name}=={pin}, but every one of them is verified "
            f"against {name}=={installed} — the version in this environment. A tree is handed "
            f"to somebody who installs the pin, so the pin is what has to work."
        )


def test_the_makefile_does_not_assume_the_ambient_python_has_the_dependencies():
    """`make run` was `python -m app.main`.

    That works where the ambient interpreter happens to have this app's
    dependencies and nowhere else — and on a distribution whose system Python is
    externally managed, `make install` cannot fix it either, because pip refuses
    to write there. The hand-back then names a command that cannot work, which
    is the one thing a generated prototype must not do.
    """
    makefile = (targets.SKELETON_ROOT / "tui" / "Makefile").read_text(encoding="utf-8")
    assert "$(PY)" in makefile, "the Makefile hardcodes an interpreter instead of resolving one"
    assert ".venv/bin/python: requirements.txt" in makefile, (
        "there is no rule that builds a local environment, so a machine without "
        "the dependencies has no way to get them"
    )
    for target in ("run:", "test:"):
        line = next(line for line in makefile.splitlines() if line.startswith(target))
        assert "$(PY)" in line, f"`make {target[:-1]}` does not depend on a resolved interpreter: {line!r}"


@pytest.mark.parametrize("satisfied", [True, False], ids=["environment-satisfied", "fresh"])
@pytest.mark.parametrize("target", ["run", "test"])
def test_the_makefile_resolves_both_interpreter_paths(tmp_path, satisfied, target):
    """The assertion above reads the Makefile; this one asks make.

    It read correctly and failed anyway: when the ambient `python` already had
    the dependencies, `$(PY)` was `python`, which `run:` and `test:` named as a
    prerequisite with no file and no rule, so make stopped with "No rule to make
    target 'python'". A string check cannot see a missing rule. `make -n`
    resolves the graph without running a recipe, and a stub `python` on PATH
    decides which branch of `$(PY)` it takes.
    """
    make = shutil.which("make")
    if make is None:  # pragma: no cover - every supported host has make
        pytest.skip("make is not installed")
    shutil.copy(targets.SKELETON_ROOT / "tui" / "Makefile", tmp_path / "Makefile")
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    stub = stub_dir / "python"
    stub.write_text(f"#!/bin/sh\nexit {0 if satisfied else 1}\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    result = subprocess.run([make, "-n", target], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"`make {target}` cannot resolve its graph: {result.stderr.strip()}"
    expected = "python -m" if satisfied else ".venv/bin/python -m"
    last = result.stdout.strip().splitlines()[-1]
    assert last.startswith(expected), f"`make {target}` would run {last!r}, expected {expected!r}"
    assert (
        "python3 -m venv .venv" in result.stdout
    ) is not satisfied, "the local environment is built when it is not needed, or skipped when it is"
