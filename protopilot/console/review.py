"""The spec review, as a screen you can read.

`proto new` has always had this checkpoint: after intake it prints the spec and
asks `Generate this? [Y/n]`. The console needs the same decision at the same
point, and a modal is the honest shape for it — the question blocks, because
the answer changes whether the next twenty minutes happen at all.

**What declining saves, stated exactly.** Intake has already run by the time
there is a spec to show, so declining is not free: one model call is spent. What
it saves is the five generation passes and the verify loop, which is the whole
of the wall clock and nearly all of the tokens. That is why the checkpoint sits
here and not one step earlier, where there would be nothing to review, or one
step later, where there would be nothing to save.

No view code is shared with the web front end's review, deliberately. Two front
ends over one seam is the design; an abstraction over a Jinja template and a
Textual screen would be invented before either had settled.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ReviewScreen(ModalScreen[bool]):
    """Approve or decline one assembled spec. Returns the answer."""

    BINDINGS = [
        ("enter", "approve", "Generate"),
        ("escape", "decline", "Cancel"),
    ]

    def __init__(self, summary: str, destination: str) -> None:
        super().__init__()
        self._summary = summary
        self._destination = destination

    def compose(self) -> ComposeResult:
        with Vertical(id="review"):
            yield Static("Generate this?", id="review-title")
            # **The buttons are outside the scroll region, and that is not a
            # layout preference.** A spec summary is as long as the spec: five
            # entities with eight fields each is a screen and a half. With the
            # buttons inside the scroll they sit below the fold on a short
            # terminal, and the only way to answer a blocking question is to
            # find them first. Here the summary scrolls and the answer does not
            # move.
            with VerticalScroll(id="review-body"):
                # The spec's own summary, not a second rendering of it. The
                # same string `proto new` prints, so the two front ends cannot
                # drift into describing one spec differently.
                yield Static(self._summary, id="review-spec")
                yield Static(f"→ {self._destination}", id="review-dest")
            with Horizontal(id="review-buttons"):
                yield Button("Generate", variant="primary", id="approve")
                yield Button("Cancel", id="decline")

    def on_mount(self) -> None:
        self.query_one("#approve", Button).focus()

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_decline(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")
