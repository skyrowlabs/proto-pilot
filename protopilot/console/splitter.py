"""Draggable dividers, because Textual 8.2.8 does not ship one.

A `Splitter` is a one-cell rule between two regions that resizes the one it is
told to when dragged. Textual has `Rule`, which draws a line and does nothing,
and no widget that resizes a sibling — so this is the smallest thing that does.

## What it resizes, and why it is told rather than asked

A splitter names its target by selector and sets one dimension on it. It does
**not** work out "the widget before me" from the layout, which is the obvious
design and the wrong one: it would silently retarget when somebody reorders
`compose()`, and the failure — a divider that resizes the wrong pane — reads
as a rendering bug rather than as a consequence of moving a line.

## Both roads to the same place

Dragging is discoverable and keyboard resizing is reliable; a terminal UI over
ssh, in a multiplexer, or in a terminal with mouse reporting off gets one of
those and not the other. So the app binds `ctrl+arrow` to the same `nudge()`
this uses, and neither is the only way in.

Sizes are clamped here rather than by the caller. A pane dragged to zero is a
pane nobody can find again, and a keyboard chord held down is exactly how that
happens.
"""

from __future__ import annotations

from textual import events
from textual.widgets import Static


class Splitter(Static):
    """A divider that resizes `target` along one axis."""

    DEFAULT_CSS = """
    Splitter {
        background: $panel;
    }
    Splitter.-vertical { width: 1; height: 1fr; }
    Splitter.-horizontal { height: 1; width: 1fr; }
    Splitter:hover { background: $primary; }
    Splitter.-dragging { background: $primary; }
    """

    def __init__(
        self,
        target: str,
        axis: str = "width",
        minimum: int = 20,
        maximum: int = 160,
        **kwargs,
    ) -> None:
        super().__init__("", **kwargs)
        self.target = target
        self.axis = axis
        self.minimum = minimum
        self.maximum = maximum
        self._origin = 0
        self._start = 0
        self.add_class("-vertical" if axis == "width" else "-horizontal")

    # -- the size it owns -------------------------------------------------

    def current(self) -> int:
        """The size **including** padding and border, because that is what
        `styles.width` sets.

        `size` is the content box. Reading one and writing the other makes a
        nudge smaller than the padding a no-op: the input pane has two cells of
        padding a side, so `apply(current() + 4)` set the width it already had
        and the divider looked broken rather than clamped.
        """
        widget = self.screen.query_one(self.target)
        outer = widget.outer_size
        return outer.width if self.axis == "width" else outer.height

    def apply(self, value: int) -> None:
        widget = self.screen.query_one(self.target)
        clamped = max(self.minimum, min(self.maximum, value))
        if self.axis == "width":
            widget.styles.width = clamped
        else:
            widget.styles.height = clamped

    def nudge(self, delta: int) -> None:
        """Move the divider by `delta` cells. What the keyboard bindings call."""
        self.apply(self.current() + delta)

    # -- dragging ---------------------------------------------------------

    def on_mouse_down(self, event: events.MouseDown) -> None:
        # Captured, so the drag survives the pointer leaving a one-cell-wide
        # widget -- which it does immediately, on the first pixel of movement.
        self.capture_mouse()
        self.add_class("-dragging")
        self._origin = event.screen_x if self.axis == "width" else event.screen_y
        self._start = self.current()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self.has_class("-dragging"):
            return
        now = event.screen_x if self.axis == "width" else event.screen_y
        self.apply(self._start + (now - self._origin))

    def on_mouse_up(self, _event: events.MouseUp) -> None:
        if self.has_class("-dragging"):
            self.remove_class("-dragging")
            self.release_mouse()
