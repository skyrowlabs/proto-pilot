"""One idiom for "this check actually looked at something".

A test that enumerates a tree and asserts a **negative** — no file kept a
placeholder, no module outside the owner names the constant — is a tautology
over an empty set. It passes when the thing it guards is absent, and it passes
when the *enumeration* is absent, and nothing in the output distinguishes the
two. Renaming a directory disarms it silently, which is the failure mode these
checks exist to prevent, arriving inside the check.

Two of this repository's suites already knew that — `test_cli_smoke.py` has
`test_the_walk_found_commands`, `test_docs_name_real_commands.py` has
`test_the_scan_finds_the_docs` — and eight other places did not. The rule was
held, not applied; skeletor found the same distribution in their tree on the
same day and named the settling question, which is not *does a guard exist* but
**does it still pass with the enumeration emptied**.

A helper rather than a companion test per site, because a companion test is a
second thing to remember and the sites that lacked one are the evidence that it
gets forgotten. Wrapping the enumeration puts the guard where it cannot be
omitted without also removing the loop.
"""

from __future__ import annotations

from typing import Iterable, List, TypeVar

T = TypeVar("T")


def scanned(items: Iterable[T], what: str, *, least: int = 1) -> List[T]:
    """Materialise an enumeration, refusing an empty one.

    `what` names the thing being looked for, because the failure this catches
    reads as "the check found nothing wrong" and has to be made to read as
    "the check looked at nothing".

    `least` is for the cases where one item cannot discriminate — a filter
    tested against a single file is unobservable, since "everything" and "the
    one match" are the same set. A fixture that cannot tell the fix from the
    bug is not a fixture, it is a demonstration.
    """
    out = list(items)
    assert len(out) >= least, (
        f"nothing to check: the scan for {what} found {len(out)} item(s), "
        f"needed at least {least}. The assertions below would have passed over "
        f"an empty set — which is not a green result, it is an absent one."
    )
    return out
