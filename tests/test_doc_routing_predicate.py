"""A folder is routed by a row for **itself**, never by a row for something inside it.

The predicate `check_doc_tables.py` enforces:

    A subfolder is routed by its own `README.md` or its own path. A routed
    folder is not descended into, because its row owns everything below it.

Two properties of it are subtle enough to regress silently, and neither is
visible in the pass/fail of a tree that happens to be correct today.

**The exactness rule.** `docs/reports/regular/README.md` must not vouch for
`docs/reports/`. It is the reason the directory pattern is a second regex with a
lookahead rather than a branch of the file one, and getting it wrong makes the
check green for a folder nobody routed -- the exact failure it exists to catch.

**Not descending into a routed folder.** This is what keeps `docs/implementations/spec/`
out of scope with no special case, and it must hold at any depth: a depth cutoff
gets the same answer here by accident and the wrong one for a future
`docs/reports/releases/v1.2/`.

Both halves came from skeletor, who built this check for their template after we
reported the folder-registration hole. The narrow `_DOC_PATH` that made every
nested row invisible was theirs to find -- we had looked straight at it and
called it harmless.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.check_doc_tables import _DOC_DIR, _DOC_PATH, unrouted  # noqa: E402


@pytest.mark.parametrize(
    "text",
    [
        "`docs/reports/regular/README.md`",
        "`docs/rules/docs.md`",
        "| **Rules** | rules/testing.md | `docs/rules/testing.md` |",
    ],
)
def test_a_row_for_a_file_never_routes_its_folder(text: str) -> None:
    assert _DOC_DIR.findall(text) == [], "a file row vouched for its parent folder"


@pytest.mark.parametrize(
    "text,expected",
    [("`docs/rules/`", "docs/rules/"), ("(`docs/reports/regular/`)", "docs/reports/regular/")],
)
def test_a_row_for_a_folder_routes_it(text: str, expected: str) -> None:
    assert _DOC_DIR.findall(text) == [expected]


def test_nested_documents_are_seen_at_all(tmp_path: Path) -> None:
    """The bug that made the reverse check decorative below the top level."""
    assert _DOC_PATH.findall("`docs/rules/testing.md`") == ["docs/rules/testing.md"]
    assert _DOC_PATH.findall("`docs/reports/releases/v1.2/audit.md`") == ["docs/reports/releases/v1.2/audit.md"]


def _tree(root: Path, *relative: str) -> None:
    for rel in relative:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# doc\n", encoding="utf-8")


def test_an_unrouted_folder_is_reported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.check_doc_tables.PROJECT_ROOT", tmp_path)
    _tree(tmp_path, "docs/parked/idea.md")
    assert unrouted(tmp_path / "docs", set(), set()) == ["docs/parked"]


def test_a_routed_folder_owns_everything_below_it(tmp_path: Path, monkeypatch) -> None:
    """No depth cutoff: the walk stops at the routed folder, however deep it goes."""
    monkeypatch.setattr("scripts.check_doc_tables.PROJECT_ROOT", tmp_path)
    _tree(tmp_path, "docs/archive/README.md", "docs/archive/spec/one.md", "docs/archive/spec/deep/two.md")

    by_readme = unrouted(tmp_path / "docs", {"docs/archive/README.md"}, set())
    assert by_readme == [], "a routed folder was descended into"

    by_path = unrouted(tmp_path / "docs", set(), {"docs/archive/"})
    assert by_path == [], "routing by path did not stop the walk"


def test_routing_a_child_does_not_route_its_parent(tmp_path: Path, monkeypatch) -> None:
    """The exactness rule, end to end rather than at the regex."""
    monkeypatch.setattr("scripts.check_doc_tables.PROJECT_ROOT", tmp_path)
    _tree(tmp_path, "docs/reports/regular/README.md", "docs/reports/stray.md")

    found = unrouted(tmp_path / "docs", {"docs/reports/regular/README.md"}, set())
    assert found == ["docs/reports"], "the child's row vouched for the parent"
