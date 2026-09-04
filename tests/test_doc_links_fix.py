"""`check_doc_links.py --fix` repoints a fragment, and refuses to guess.

The refusals are the interesting half. A repair tool that is right most of the
time is worse than none: a fragment repointed to the wrong section reads as
correct forever, whereas a dead one announces itself on the next run. So the
cases below pin what it must **decline** to touch as hard as what it fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import check_doc_links as links  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A miniature docs tree the checker treats as the whole repo."""
    (tmp_path / "docs").mkdir()
    # Every path the checker reads, not just the root. They are bound at import
    # from `scripts.paths`, so patching the root alone would leave `_suggest`
    # rglobbing the real repository — see scripts/paths.py on why redirecting a
    # tree properly is a design decision rather than a variable.
    monkeypatch.setattr(links, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(links, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(links, "IGNORE_FILE", tmp_path / ".validate-ignore")
    monkeypatch.setattr(links, "SCAN_ROOTS", ["docs"])

    def write(name: str, body: str) -> Path:
        path = tmp_path / "docs" / name
        path.write_text(body, encoding="utf-8")
        return path

    return write


def test_repoints_a_heading_that_grew(tree):
    """The common case: somebody made a heading more specific."""
    source = tree("a.md", "# A\n\nSee [the reason](b.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert links.repoint_fragments() == [
        "docs/a.md: '#why-this-exists' → '#why-this-exists-as-its-own-checker' in docs/b.md"
    ]
    assert "b.md#why-this-exists-as-its-own-checker" in source.read_text(encoding="utf-8")


def test_repoints_a_heading_that_shrank(tree):
    source = tree("a.md", "# A\n\n[x](b.md#testing-rules-for-agents).\n")
    tree("b.md", "# B\n\n## Testing Rules\n")

    assert links.repoint_fragments()
    assert "b.md#testing-rules)" in source.read_text(encoding="utf-8")


def test_refuses_when_two_headings_match(tree):
    """Two candidates means a human chooses. Nothing is written."""
    source = tree("a.md", "# A\n\n[x](b.md#testing).\n")
    tree("b.md", "# B\n\n## Testing Rules\n\n## Testing Budgets\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before


def test_refuses_when_no_heading_matches(tree):
    """The section did not move, it went — that is a sentence to rewrite."""
    source = tree("a.md", "# A\n\n[x](b.md#deleted-entirely).\n")
    tree("b.md", "# B\n\n## Something Unrelated\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before


def test_never_rewrites_a_broken_path(tree):
    """Where a file went is a judgement call, so `--fix` does not make it."""
    source = tree("a.md", "# A\n\n[x](gone.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")
    before = source.read_text(encoding="utf-8")

    assert links.repoint_fragments() == []
    assert source.read_text(encoding="utf-8") == before
    assert links.scan()[0], "the broken path must still be reported"


def test_leaves_links_inside_code_fences_alone(tree):
    """A link in a fenced example is illustration, not a reference.

    This is what the offset-preserving mask buys: the fix rewrites by position
    in the original text, so a masked region must not be edited *and* must not
    shift the offsets of the links after it.
    """
    source = tree(
        "a.md",
        "# A\n\n```\n[example](b.md#why-this-exists)\n```\n\nReal: [x](b.md#why-this-exists).\n",
    )
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert len(links.repoint_fragments()) == 1
    body = source.read_text(encoding="utf-8")
    assert "[example](b.md#why-this-exists)" in body, "the fenced example was rewritten"
    assert "Real: [x](b.md#why-this-exists-as-its-own-checker)." in body


def test_fixes_a_same_file_fragment(tree):
    source = tree("a.md", "# A\n\n[jump](#the-old-name)\n\n## The Old Name Of This Section\n")

    assert links.repoint_fragments()
    assert "(#the-old-name-of-this-section)" in source.read_text(encoding="utf-8")


def test_fix_is_idempotent(tree):
    """A second run has nothing to do — the first one made the link valid."""
    tree("a.md", "# A\n\n[x](b.md#why-this-exists).\n")
    tree("b.md", "# B\n\n## Why This Exists As Its Own Checker\n")

    assert len(links.repoint_fragments()) == 1
    assert links.repoint_fragments() == []
    assert links.scan() == ([], [])


def test_the_scan_covers_every_markdown_file_at_the_repo_root() -> None:
    """Recomputed from the tree, never compared against a list.

    This gate scanned `docs/`, `.claude/`, `.github/` and a hand-written
    `EXTRA_FILES = ["AGENTS.md", "CLAUDE.md", "README.md"]`. The fourth root
    document is `NOTES.md` -- the live parking lot `README.md` tells a reader
    to open first -- and it was not in that list, so its links were never
    checked. Filing a plan on 2026-09-04 broke two of them and the gate printed
    `0 broken links (at the ceiling)`.

    That is this repository's own recurring class, arriving in the file that
    enforces links: a negative result from a matcher means either the thing is
    absent or the matcher is blind, and nothing in the output distinguishes
    them. Asserting the *set* rather than four names is what makes a fifth root
    document enrol by existing.
    """
    scanned = set(links.markdown_files())
    root_docs = set(links.PROJECT_ROOT.glob("*.md"))
    missing = sorted(p.name for p in root_docs - scanned)
    assert not missing, f"root-level markdown the link gate cannot see: {missing}"
    assert (links.PROJECT_ROOT / "NOTES.md") in scanned, "NOTES.md is the one that was missing"
