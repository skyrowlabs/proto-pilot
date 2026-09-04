"""Every byte of the web skeleton, as it stood before `skeleton/` grew targets.

Phase 3 of `docs/TODO/terminal-target.md` moves `skeleton/` to `skeleton/web/`
so `skeleton/tui/` can sit beside it. The move is mechanical and the plan says
it must be **byte-identical for the web target** — proved by a characterisation
test, the way Phase 2 of the archetypes plan proved the `crud` extraction, and
not by looking at the diff.

So this is a characterisation test, not a specification. It asserts nothing
about whether the skeleton is *good* — only that it is the same file set with
the same contents at a different path. The golden manifest was generated from
the tree at `51f1b31`, before a single `git mv` ran, which is the only ordering
that makes it evidence.

## Why this and not `test_crud_characterisation.py`

That test hashes a *rendered* tree, so it would have caught the move too — and
it is one indirection away from what is being claimed. It substitutes
`@@TOKEN@@`s, normalises two files for the absolute path they embed, and only
sees the skeleton files that survive rendering. This one hashes the **source
bytes on disk**, unrendered and unnormalised, which is the actual subject of
the sentence "the move is byte-identical". Both are kept: they fail for
different reasons and only one of them would have noticed a file that was
copied rather than moved.

## Regenerating

Do not, for a move. If this is red after a deliberate edit to a skeleton file:

    PROTOPILOT_REGOLD=1 python -m pytest tests/test_skeleton_move_characterisation.py

and read the diff before committing it. A golden file updated without reading
the diff is a golden file that asserts nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from protopilot import targets

# Host-side: no key, no Docker daemon, no network.
pytestmark = pytest.mark.unit

GOLDEN = Path(__file__).resolve().parent / "golden" / "web_skeleton_manifest.json"

SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def manifest(root: Path) -> dict[str, str]:
    """posix relative path -> sha256 of the raw bytes.

    Bytes rather than text, and unnormalised: a skeleton file has no per-run
    content — the `@@TOKEN@@`s are still tokens here — so anything that differs
    is a real difference. Reading as text would also hide a line-ending change,
    which is exactly the kind of thing a bulk move does.
    """
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or SKIP_PARTS & set(rel.parts):
            continue
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


@pytest.fixture()
def current() -> dict[str, str]:
    return manifest(targets.get("web").SKELETON_DIR)


def test_the_web_skeleton_is_byte_identical_after_the_move(current):
    if os.environ.get("PROTOPILOT_REGOLD"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        pytest.skip("regenerated the golden manifest — read the diff before committing")

    assert GOLDEN.exists(), f"no golden manifest at {GOLDEN}; run with PROTOPILOT_REGOLD=1"
    golden = json.loads(GOLDEN.read_text())

    removed = sorted(set(golden) - set(current))
    added = sorted(set(current) - set(golden))
    changed = sorted(p for p in set(golden) & set(current) if golden[p] != current[p])

    assert not removed, f"skeleton files that did not survive the move: {removed}"
    assert not added, f"skeleton files that appeared during the move: {added}"
    assert not changed, f"skeleton files whose bytes changed during the move: {changed}"


def test_the_manifest_covers_the_files_that_matter(current):
    """A manifest that silently stopped covering the tree would pass forever.

    These five are the load-bearing ones: the two that stand the stack up, the
    protected template, the non-generated conftest, and a dotfile — because a
    bulk move done with a bare glob is exactly how `.env.example` and
    `.gitignore` get left behind, and nothing else in this file would say so.
    """
    for path in ("compose.yml", "Dockerfile", "app/templates/base.html", "tests/conftest.py", ".env.example"):
        assert path in current, f"{path} is missing from the skeleton being characterised"


def test_the_old_flat_skeleton_is_gone():
    """The move is a move. A tree left behind at the old path is the copy that
    quietly stays in service the day somebody re-adds a `SKELETON_DIR`."""
    assert not (targets.SKELETON_ROOT / "app").exists(), "skeleton/app/ is still at the pre-move path"
    assert not (targets.SKELETON_ROOT / "compose.yml").exists(), "skeleton/compose.yml is still at the pre-move path"


def test_every_skeleton_directory_belongs_to_a_target():
    """`skeleton/` is one directory per target and nothing else.

    Recomputed from what is on disk rather than listed, so a tree added without
    a target — or a target renamed without its tree — fails here rather than at
    the first `proto new` that reaches for it.
    """
    on_disk = {p.name for p in targets.SKELETON_ROOT.iterdir() if p.is_dir() and p.name not in SKIP_PARTS}
    owned = {targets.get(name).SKELETON_DIR.name for name in targets.names()}
    assert on_disk >= owned, f"a target points at a skeleton that is not there: {sorted(owned - on_disk)}"
    unclaimed = on_disk - owned
    # `tui/` is the one legitimate unclaimed tree today: Phase 3 built the
    # skeleton, and Phases 4 and 5 build the passes and the verifier that a
    # target module needs before it can honestly be registered.
    assert unclaimed <= {"tui"}, f"skeleton trees with no target and no reason: {sorted(unclaimed - {'tui'})}"
