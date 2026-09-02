"""A reference doc may not name a callable this repo used to have and no longer does.

The narrow, decidable half of a problem whose useful half is not. skeletor's
framing, after we each found an instance in the same afternoon: **when you fix a
defect, everything justified by it is now justified by nothing**, and the
dangerous case is where the conclusion survives, because then nothing goes red.

No test can read "because X is broken" and go check whether X is still broken —
that is semantic, the input is prose, and it belongs to something that reads
across the repo periodically and reports. What a test *can* do is catch the
mechanical cousin: a doc that tells you to use a function that has been renamed
or deleted.

## Why the predicate is "it was ours, and now it isn't"

The obvious version — every backticked `foo()` in the docs must resolve — has a
false-positive rate that makes it useless. Run on this repo it flagged five
things, and four were correct: `cross_check()` and `reset_to_base()` belong to
skeletor, `os.getenv()` and `datetime.utcnow()` are stdlib. A gate you have to
allowlist four things into is describing the wrong shape.

Asking git instead makes it exact. A name this repository once defined and no
longer defines is unambiguously ours and unambiguously gone. Everything that was
never ours is excluded by construction rather than by exemption, and the
allowlist is empty because there is nothing to put in it.

## Why narrative documents are out of scope

A plan in `docs/TODO/` says "this phase takes `standard_screens()` and moves
it". That sentence is *correct* and naming a dead symbol is the whole point of
it. Same for the archive, the reports, and `NOTES.md`'s resolved section —
their job is to describe what happened, not what is.

So those lifecycle directories are excluded by role, and everything else is
enrolled by default. That direction matters: a new reference doc is covered by
existing, which is the same reason the test suites are marker-based and the
archetype registry is discovered rather than listed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]

#: Lifecycle stages whose job is to narrate what happened. `docs/rules/docs.md`
#: defines them; naming a since-removed mechanism is correct usage there.
NARRATIVE = ("docs/TODO/", "docs/implementations/", "docs/reports/", "NOTES.md")

#: A backticked call. The parentheses are the whole signal -- they are what
#: separates a code reference from a word that happens to be in a code span.
CALL = re.compile(r"`([A-Za-z_][\w.]*)\(\)`")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def _tracked(pattern: str) -> list[Path]:
    return [REPO / line for line in _git("ls-files", pattern).split() if line.strip()]


def reference_docs() -> list[Path]:
    return [p for p in _tracked("*.md") if not _label(p).startswith(NARRATIVE)]


def defined_now() -> set[str]:
    """Every callable this repo currently defines."""
    names: set[str] = set()
    for path in _tracked("*.py"):
        source = path.read_text(encoding="utf-8", errors="replace")
        names.update(re.findall(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", source, re.M))
    return names


def was_ever_ours(symbol: str) -> bool:
    """Did this repository ever define `symbol`?

    `-S` on the definition line rather than the bare name: a symbol merely
    *mentioned* in a commit is not one we owned.
    """
    return bool(_git("log", "--all", "-S", f"def {symbol}", "--oneline", "--", "*.py").strip())


def _label(path: Path) -> str:
    """Repo-relative where possible. The negative-case test drives a file from
    a tmp directory, and a reporting helper must not be the thing that raises."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def dead_references() -> list[tuple[str, str]]:
    live = defined_now()
    found: list[tuple[str, str]] = []
    for path in reference_docs():
        for match in CALL.finditer(path.read_text(encoding="utf-8")):
            symbol = match.group(1).rsplit(".", 1)[-1]
            if symbol in live:
                continue
            if was_ever_ours(symbol):
                found.append((_label(path), match.group(1)))
    return sorted(set(found))


def test_history_is_available():
    """The check is worthless against a shallow clone -- `git log --all` would
    find nothing and every reference would look like it was never ours, so the
    test would pass by seeing nothing rather than by finding nothing.

    That is the "worked fine, told nobody" shape, so it is asserted rather than
    assumed. CI checks out with `fetch-depth: 0` for this.
    """
    assert not (
        REPO / ".git" / "shallow"
    ).exists(), "shallow clone: this test needs history and would silently pass without it"


def test_no_reference_doc_names_a_callable_we_removed():
    dead = dead_references()
    assert not dead, "docs naming a callable this repo used to define:\n" + "\n".join(
        f"  {where}: {symbol}()" for where, symbol in dead
    )


def test_the_check_would_actually_catch_one(tmp_path, monkeypatch):
    """A gate nobody has seen fail is a gate nobody knows works.

    `standard_screens` is the real case: it lived in `baseline.py` until Phase 2
    of the archetypes plan moved it to `crud.screens()`. A reference doc still
    saying to call it would be wrong, and this proves the predicate says so.
    """
    doc = tmp_path / "REFERENCE.md"
    doc.write_text("Call `standard_screens()` to get the screen set, and `os.getenv()` for config.\n")
    monkeypatch.setattr("test_docs_name_live_code.reference_docs", lambda: [doc])

    found = dead_references()

    assert [s for _, s in found] == ["standard_screens"], f"expected exactly the removed symbol, got {found}"
