"""The skyrow.labs palette, as a Textual theme.

Copied, not imported. The values below are the ones `skyrowlabs.com/index.html`
declares on `:root`, transcribed on 2026-09-04 — including `--pp`, which is
proto.pilot's **own** accent in the company's palette rather than a colour
picked here to look like it.

**Deliberately a copy, and the reason is not laziness.** These repositories are
siblings under one workspace root and nothing else; a Python package reading a
sibling's CSS at import time would break the moment somebody clones this repo on
its own, and proto.pilot is meant to go public. A copy that drifts by a few
percent of a hue is a cost worth paying for a package that installs from PyPI
and renders correctly with no neighbours on disk. If the site's palette moves,
this is a one-line edit, and the site is the master copy either way.

## What a terminal can and cannot carry

The site's identity is three typefaces, a scroll-driven hero and per-product
accent rings. A terminal has none of that: no fonts, no opacity ramps, no
blur. What survives the translation is the **palette and the accent
discipline** — a near-black ground, three surface tiers a shade apart, one
product accent used sparingly, and status colours that are not the accent.
That is most of what makes the site recognisable at a glance, and it is the
part that costs nothing here.

## One value deliberately dropped

`--text-3: #617791` is not used. Measured against all three surfaces it lands
at 4.33 / 4.14 / 3.88 : 1 — under the 4.5:1 threshold everywhere, and worst on
the elevated panel where the console puts its quietest text.

jam.sense's design system already records this exact failure in its own
`skyrow` theme: *"in some themes `--text-muted` is tuned for the near-black page
void and drops below 4.5:1 on elevated surfaces."* Their remedy is a separate
`--text-caption` token that every theme must keep legible. Here there is one
elevated surface and one quiet text, so the simpler fix applies: use `--text-2`
(#7a8fa8, 5.38:1 on the panel) for everything quiet, and let the third tier go.

A palette borrowed from a web app is worth borrowing its contrast bugs' fixes
from too.
"""

from __future__ import annotations

from textual.theme import Theme

#: Straight from `skyrowlabs.com/index.html`, `:root`.
BACKGROUND = "#05090e"  # --bg
SURFACE = "#0b1016"  # --surface
PANEL = "#111820"  # --surface-2
TEXT = "#e8edf4"  # --text
TEXT_MUTED = "#7a8fa8"  # --text-2  (--text-3 dropped; see above)

ACCENT = "#2dd4bf"  # --pp   proto.pilot's own
BRAND = "#38bdf8"  # --brand company, and jam.sense's
SUCCESS = "#4ade80"  # --bb
WARNING = "#fb923c"  # --sf
ERROR = "#f9a8d4"  # --fail, which the site names for exactly this

NAME = "skyrow"

SKYROW = Theme(
    name=NAME,
    # The product's accent is `primary`, because Textual spends `primary` on
    # focus rings and active borders -- the places an accent belongs. `brand`
    # is the company blue and stays `secondary`, so the two never compete for
    # the same pixel.
    primary=ACCENT,
    secondary=BRAND,
    accent=BRAND,
    background=BACKGROUND,
    surface=SURFACE,
    panel=PANEL,
    foreground=TEXT,
    success=SUCCESS,
    warning=WARNING,
    error=ERROR,
    dark=True,
    variables={
        # Textual would otherwise derive this by fading the foreground, which
        # lands somewhere near the tier this palette measured as unreadable.
        "text-muted": TEXT_MUTED,
        "border": PANEL,
        "border-blurred": PANEL,
    },
)
