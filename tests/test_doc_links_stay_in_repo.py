"""No markdown link may point outside this repository.

The gate that caught this lives in CI and could not have caught it locally.
`check_doc_links` asks the filesystem whether a relative link resolves -- and on
a development machine `../skeletor` and `../../<another repo>/...` resolve
perfectly, because every skyrow.labs repo is a sibling checkout under one root.
A CI runner clones one repository. So does every stranger.

That is the divergence: `./pp check pre-push` was green while CI was red, three
commits running, and nothing local could tell the difference. This test closes
it by asking a question that has the same answer in both places -- *does this
link escape the repo root* -- rather than *does this path exist here*.

It recomputes the offending set from the tracked files on every run rather than
listing the sites that were wrong. That is not a stylistic preference: CI named
four, and this predicate immediately found two more in `NOTES.md` that
`check_doc_links` does not look at. Listing the four would have pinned exactly
the four and stayed silent on the rest -- the workspace guide's rule being that
a structural gate you have to allowlist things into is describing the wrong
shape.

The fix for a violation is never to delete the reference. Name the sibling repo
and its path in prose or a code span; a reader inside the workspace still finds
it, and a reader outside gets a fact instead of a 404.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]

# `[text](target)`. Reference-style links and bare autolinks are deliberately
# not matched: neither can carry a relative filesystem path, which is the only
# thing that can escape the tree.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# A target that is not a filesystem path at all. Anchors and URLs cannot escape
# a repository, so they are not this test's business.
NOT_A_PATH = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", re.I)


def tracked_markdown() -> list[Path]:
    """Every markdown file git knows about.

    Tracked rather than globbed: `prototypes/` is gitignored generator output
    full of links we did not write, and a test that fails because of a
    throwaway prototype is a test people learn to ignore.
    """
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line.strip()]


def escaping_links() -> list[tuple[str, str]]:
    """(file, target) for every relative link resolving outside the repo."""
    offenders = []
    for path in tracked_markdown():
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            target = target.split()[0].strip("<>")  # drop an optional title
            if not target or NOT_A_PATH.match(target):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if REPO not in resolved.parents and resolved != REPO:
                offenders.append((str(path.relative_to(REPO)), target))
    return offenders


def test_no_markdown_link_points_outside_the_repository():
    offenders = escaping_links()
    assert not offenders, "links that resolve only because of sibling checkouts:\n" + "\n".join(
        f"  {where}: {target}" for where, target in offenders
    )


def test_the_detector_would_actually_catch_one(tmp_path, monkeypatch):
    """A gate nobody has seen fail is a gate nobody knows works.

    The real check passes on a clean tree, so on its own it proves only that it
    ran. This drives a known-bad file through the same predicate.
    """
    doc = tmp_path / "sub" / "doc.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("see [sibling](../../elsewhere/thing.md) and [ok](./local.md)\n")
    # The module object, not a dotted string: `tests/` has no __init__.py, so
    # this module is imported as `test_doc_links_stay_in_repo` and a
    # `tests.`-prefixed target would patch a second, unrelated import of it --
    # silently leaving the real globals in place.
    here = sys.modules[__name__]
    monkeypatch.setattr(here, "REPO", tmp_path)
    monkeypatch.setattr(here, "tracked_markdown", lambda: [doc])

    assert escaping_links() == [("sub/doc.md", "../../elsewhere/thing.md")]
