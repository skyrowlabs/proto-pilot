#!/usr/bin/env python3
"""Every `docs/*.md` is registered in both agent-facing index tables.

`AGENTS.md` and `.github/DOCS_INDEX.md` are how an agent decides what to read.
A document in neither is a document that will not be loaded — which is the same,
from the agent's point of view, as a document that does not exist. The failure
is silent and permanent: nothing ever surfaces the omission.

The reverse direction matters as much. A table row pointing at a deleted file
sends a reader to a dead path and, worse, implies the subject is still covered.

Usage:  python scripts/check_doc_tables.py [--json]

`--json` is additive, never a second code path: the payload goes to stdout and
the explanation to stderr, so `... --json | jq` and a human run are the same run.
See `scripts/output.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set

# Bootstrap only: put the package on sys.path so `scripts.paths` — which
# owns every path below — can be imported. See scripts/paths.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output import detail, emit, fail, item, ok  # noqa: E402
from scripts.paths import DOCS_DIR, GITHUB_DIR, PROJECT_ROOT  # noqa: E402

#: The agent-facing index tables. `AGENTS.md` is where the rules live and
#: `CLAUDE.md` is a pointer to it, but both are read: a tree adopted from
#: somewhere else may still keep its table in `CLAUDE.md`, and a doc registered
#: in a file that exists is registered. A table that is absent contributes
#: nothing rather than failing.
TABLES = [
    PROJECT_ROOT / "AGENTS.md",
    PROJECT_ROOT / "CLAUDE.md",
    GITHUB_DIR / "DOCS_INDEX.md",
]

#: Docs that are indexes themselves, or generated. Registering an index in an
#: index is noise, and a generated file's registration would be regenerated away.
EXEMPT = {"README.md"}

#: A reference to one document, at any depth. The `/` in the character class is
#: the whole point: it used to be absent, so `docs/rules/testing.md` matched
#: nothing and a nested row was invisible in **both** directions — it could not
#: satisfy a registration, and a row left pointing at a deleted nested doc could
#: never be reported dangling. The reverse half of this check had never once
#: worked below the top level. (Found by skeletor, whose template shares it.)
_DOC_PATH = re.compile(r"docs/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.md")

#: A reference to a *folder*. Deliberately a second pattern rather than a branch
#: of the first, because the rule it enforces is an exactness one: a folder is
#: routed by a row for **itself**, never by a row for something inside it. A row
#: for `docs/reports/regular/README.md` must not vouch for `docs/reports/`.
#: The lookahead is what draws that line — it refuses to match the `docs/rules/`
#: prefix sitting inside `docs/rules/docs.md`.
_DOC_DIR = re.compile(r"docs/(?:[A-Za-z0-9_.-]+/)+(?![A-Za-z0-9_.-])")


def _tables_text() -> str:
    return "\n".join(t.read_text(encoding="utf-8") for t in TABLES if t.exists())


def referenced() -> Set[str]:
    return set(_DOC_PATH.findall(_tables_text()))


def routed_dirs() -> Set[str]:
    return set(_DOC_DIR.findall(_tables_text()))


def unrouted(directory: Path, files: Set[str], dirs: Set[str]) -> List[str]:
    """Folders holding docs that no routing row reaches.

    > A subfolder is routed by its own `README.md` **or its own path**. A routed
    > folder is not descended into, because its row owns everything below it.

    That second clause is what keeps `docs/implementations/spec/` out of scope
    without a special case: its parent is routed, so the walk stops above it. A
    depth cutoff would get the same answer here by accident and the wrong one
    for `docs/reports/releases/v1.2/`.

    Routing by *path* is what lets a flat shelf like `docs/rules/` work with no
    README. Per-file rows there would go stale the next time a rule is added,
    which is the registry this whole check exists to avoid.
    """
    found: List[str] = []
    for child in sorted(d for d in directory.iterdir() if d.is_dir()):
        rel = child.relative_to(PROJECT_ROOT).as_posix()
        if f"{rel}/README.md" in files or f"{rel}/" in dirs:
            continue
        if any(child.glob("*.md")):
            found.append(rel)
        found += unrouted(child, files, dirs)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    on_disk = {f"docs/{p.name}" for p in DOCS_DIR.glob("*.md") if p.name not in EXEMPT}
    listed = referenced()
    dirs = routed_dirs()

    unregistered = sorted(on_disk - listed)
    unrouted_dirs = sorted(unrouted(DOCS_DIR, listed, dirs))
    dangling = sorted(ref for ref in listed if not (PROJECT_ROOT / ref).exists())

    # Every doc a routing row now reaches, which is the number worth printing.
    # The old count was of loose `docs/*.md` only and read as total coverage:
    # it said "4 doc(s), all registered" in a tree holding 24.
    reachable = sum(1 for _ in DOCS_DIR.rglob("*.md"))

    if args.json:
        emit(
            {
                "docs": reachable,
                "unregistered": unregistered,
                "unrouted_dirs": unrouted_dirs,
                "dangling": dangling,
            }
        )

    status = 0
    if unregistered:
        fail("docs not registered in AGENTS.md or .github/DOCS_INDEX.md:")
        for ref in unregistered:
            item(ref)
        detail("An unregistered doc is one no agent will load. Add it to both tables.")
        status = 1
    if unrouted_dirs:
        fail("doc folders no routing row reaches:")
        for ref in unrouted_dirs:
            item(f"{ref}/")
        detail("A subfolder is routed by its own README.md or its own path, and a")
        detail("routed folder owns everything below it. Give it one row — not a row")
        detail("per doc, which goes stale the next time one is added.")
        status = 1
    if dangling:
        fail("index rows pointing at files that no longer exist:")
        for ref in dangling:
            item(ref)
        status = 1
    if not status:
        ok(f"{reachable} doc(s) reachable; {len(on_disk)} top-level, every folder routed")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
