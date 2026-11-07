"""The fixed ways of looking at an idea, because "give me ideas" returns the same five.

Data, so a lens is added here and nowhere else. `slug` is what `--lens` takes and
what a dream records; the words a person reads are the slug with its hyphens gone.
"""

from __future__ import annotations

from typing import NamedTuple


class Lens(NamedTuple):
    slug: str
    ask: str


LENSES = (
    Lens("who-else", "Who else could this serve, beyond the people it was meant for?"),
    Lens("the-opposite", "What is the idea turned around: the reverse of its main assumption?"),
    Lens("ten-times-bigger", "What does it become at ten times the size?"),
    Lens("the-smallest-version", "What is the least of it that would still be worth having?"),
    Lens("remove-the-main-constraint", "What opens up if its hardest stated limit stopped applying?"),
    Lens("borrow-from-another-field", "What would another field, far from this one, do here?"),
)
LENS_SLUGS = tuple(lens.slug for lens in LENSES)


def chosen(slugs: tuple[str, ...]) -> tuple[Lens, ...]:
    """The lenses `slugs` name, in `LENSES` order; none named means all of them."""
    return tuple(lens for lens in LENSES if lens.slug in slugs) or LENSES


def words(slug: str) -> str:
    return slug.replace("-", " ")
