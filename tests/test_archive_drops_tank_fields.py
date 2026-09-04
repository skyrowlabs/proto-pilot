"""A filed plan may not still describe itself as unfinished.

`docs/implementations/` holds **only completed** plans -- that is the whole
distinction between the archive and the holding tank. So a doc in there
carrying `shelf_status: in-progress`, a `> **Shelf-Status**:` header or a
`> **Queue-Order**:` line is stating two contradictory things at once, and the
one a reader believes is whichever they happened to read.

**Nothing in `pp check docs` could see this**, by construction. The five gates
ask whether the *generated* artifacts match their sources, and
`gen_impl_index.py` deliberately pops these three keys when it builds the index
-- its own comment says a stale `shelf_status: ready` in the archive is
"actively misleading". That fix went into the derived artifact: the index comes
out clean while the document keeps the lie. `regen.py --check` can never go red
on a field it never renders.

Two layers made it stick. `add_frontmatter.py` skipped any doc that already had
frontmatter, and a plan being filed always has some -- so `_derive`'s archive
strip was unreachable for every real doc. And even reached, it would not have
been enough: `plans.py` reads the body header `> **Shelf-Status**:` *before*
frontmatter, and nothing rewrites body headers. Stripping the frontmatter alone
cannot change the value the code returns.

Hence a test rather than one more careful command. The header half has no
generator to fix, so the only durable check is one that reads the filed
document and asks what it claims.

It recomputes the offending set from the archive on every run instead of naming
the doc that was wrong. Listing today's one plan would pin that one and stay
silent on the second, which is the failure this repo's own rule about structural
gates exists to prevent.

**This is the ratchet, not the mechanism.** `pp docs file` strips the headers as
part of the move, and `test_docs_lifecycle.py` proves it does by filing a plan
through the real command and reading the document back. What is left for this
file is the route that bypasses the command entirely: a plan moved by hand with
`git mv`. So an empty archive passing is *correct* here, and there is no
non-empty guard -- an earlier version had one, and skeletor was right that it is
wrong. It makes the file red on arrival in a tree that has filed nothing yet,
and a gate whose first act is to fail an innocent repo is a gate people learn to
delete. The end-to-end belongs where the corpus is constructed rather than
assumed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Host-side: reads files, runs nothing.
pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.docs.plans import TANK_ONLY  # noqa: E402
from scripts.paths import IMPL_DIR  # noqa: E402

#: The same keys as a `> **Header**:` line, which is what `plans.py` reads
#: *first* and therefore what actually decides the value. Derived from
#: `TANK_ONLY` rather than respelled, so a fourth key cannot be added to the
#: generators and silently missed here.
_HEADER = re.compile(
    r"^>\s*\*\*(" + "|".join(k.replace("_", "-") for k in TANK_ONLY) + r")\*\*\s*:",
    re.I | re.M,
)

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def archived() -> list[Path]:
    return sorted(p for p in IMPL_DIR.rglob("*.md") if p.name != "README.md")


def test_no_filed_plan_carries_a_tank_field_in_frontmatter() -> None:
    offenders = []
    for path in archived():
        block = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not block:
            continue
        for key in TANK_ONLY:
            if re.search(rf"^{key}\s*:", block.group(1), re.M):
                offenders.append(f"{path.relative_to(REPO)}: {key}")
    assert not offenders, (
        "filed plans still carry holding-tank frontmatter:\n  "
        + "\n  ".join(offenders)
        + "\n\nRun `python scripts/docs/add_frontmatter.py`, which strips these "
        "from the archive. Reaching this usually means the plan was moved by "
        "hand -- `pp docs file` does it as part of the move."
    )


def test_no_filed_plan_carries_a_tank_header() -> None:
    offenders = []
    for path in archived():
        for match in _HEADER.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(REPO)}: > **{match.group(1)}**")
    assert not offenders, (
        "filed plans still carry holding-tank headers:\n  "
        + "\n  ".join(offenders)
        + "\n\nDelete the line, or re-file with `pp docs file`, which strips "
        "them. The header outranks frontmatter in `plans.py`, so it is the "
        "value the code reads -- clean frontmatter does not save it."
    )
