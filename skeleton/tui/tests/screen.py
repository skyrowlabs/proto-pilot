"""Not generated. Reading what a Textual app is actually showing.

**This file exists because three separate generations wrote it wrong, in the
same way, and each diagnosed it from scratch.** The Phase 1 measurement behind
`docs/implementations/spec/terminal-target.md` ran three terminal generations and all three
failed their own smoke suite while the app underneath was correct: the smoke
helper each one wrote read a `Static`'s text off `.renderable`, which current
Textual does not have. Every `Static` on every screen therefore read as empty,
while `DataTable` rows and `Button` labels came through normally.

So the helper is skeleton rather than generated. That is the same rule the rest
of this tree follows — the parts known to work are the parts the model must not
have to rewrite — and it is the whole of the fix: a fourth independent
rediscovery is waste, and the fifth would arrive the next time Textual moves.

## Why a tuple of attributes and not one

Because the attribute has moved at least three times and the version a
prototype runs against is not knowable when the prompt is written:

    Textual 0.x   Static.renderable
    Textual 2.x   Static._content, a Content object
    Textual 8.x   Static.content, a str (and `__content` behind the mangling)

`TEXT_ATTRS` is read in order and everything that answers is kept, so a version
that has two of them costs a duplicate line of text and never a false negative.
The failure this prevents — a working screen reported blank — is silent,
expensive, and indistinguishable from the app being broken.

The alternative the plan also allows is to require generated screens to carry
their text through `Screen.sub_title`, a `DataTable` or a `Button`. That is a
constraint on every future prompt; this is one file. Both are done here, in
fact: `app/screens.py` uses a `Static` **and** a `sub_title`, so the skeleton
demonstrates the fix from both ends.
"""

from __future__ import annotations

from typing import Any

from textual.widgets import DataTable

#: Where a widget might be keeping text a person can read, most specific first.
#:
#: Module level, and a tuple, deliberately: it is the one thing in this file a
#: reader needs to change when Textual moves again, and a value in a tuple is a
#: smaller change than a branch in a function.
TEXT_ATTRS = (
    "renderable",  # Textual 0.x
    "_content",  # Textual 2.x, a Content
    "content",  # Textual 8.x, a str
    "_Static__content",  # ...and the name-mangled private behind it
    "label",  # Button, Checkbox, ListItem
    "text",  # TextArea and friends
    "value",  # Input, Select, Digits
    "placeholder",  # Input, before anything is typed
    "border_title",  # a titled container
    "title",  # Screen
    "sub_title",  # Screen
)


def flatten(value: Any) -> str:
    """Whatever a widget is holding, as plain text.

    Tolerant on purpose. A widget can hold a `str`, a Textual `Content`, a rich
    renderable, or something with no text in it at all, and a helper that
    raises on the fourth case turns "this screen has no button" into an error
    nobody can read.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value
    plain = getattr(value, "plain", None)  # rich.text.Text, Textual's Content
    if isinstance(plain, str):
        return plain
    if isinstance(value, (list, tuple, dict, set)):
        return ""
    return str(value)


def table_text(table: DataTable) -> str:
    """Every cell of a `DataTable`, one row per line.

    Its content is not on any attribute in `TEXT_ATTRS` — it is in the row
    store — so it is read separately. A generated list screen is usually a
    `DataTable`, which makes this the half that most often carries the thing a
    test is looking for.
    """
    lines: list[str] = []
    try:
        lines.append(" | ".join(flatten(column.label) for column in table.columns.values()))
        for index in range(table.row_count):
            lines.append(" | ".join(flatten(cell) for cell in table.get_row_at(index)))
    except Exception:  # noqa: BLE001 -- a table mid-rebuild has nothing to say
        pass
    return "\n".join(lines)


def widget_text(widget: Any) -> str:
    """Everything readable on one widget, from every attribute that answers."""
    parts: list[str] = []
    for attr in TEXT_ATTRS:
        try:
            value = getattr(widget, attr, None)
        except Exception:  # noqa: BLE001 -- a property that raises is not text
            continue
        text = flatten(value)
        if text.strip():
            parts.append(text)
    if isinstance(widget, DataTable):
        parts.append(table_text(widget))
    return "\n".join(part for part in parts if part.strip())


def screen_text(screen: Any) -> str:
    """All the text a person could read on this screen, including its own."""
    parts = [widget_text(screen)]
    parts.extend(widget_text(widget) for widget in screen.query("*"))
    return "\n".join(part for part in parts if part.strip())


def visible(app: Any) -> str:
    """The text on whatever screen is on top."""
    return screen_text(app.screen)


def buffer(app: Any) -> str:
    """The composited screen, as a terminal would receive it.

    `screen._compositor.render_strips()` and not `Screen.render_lines`: the
    second renders the screen widget itself and returns blank rows for an app
    whose content is all in its children, which is every app here. Getting that
    wrong reports a working app as blank.

    Use this to assert something is *drawn*; use `visible()` to assert
    something is *there*. They disagree when a widget is scrolled out of a small
    test screen, and that disagreement is usually the test's fault, not the
    app's.
    """
    return "\n".join(strip.text for strip in app.screen._compositor.render_strips())


def mentions(app: Any, *needles: str) -> bool:
    """Whether every needle appears somewhere on the top screen, case-folded."""
    haystack = " ".join(visible(app).split()).lower()
    return all(needle.lower() in haystack for needle in needles)


def where(app: Any) -> str:
    """Screen stack plus the ids on top -- the context a failure needs.

    Put this in an assertion message. "expected 'Trip' on screen" is unusable;
    the same message naming the screen stack and the ids that are there is a
    diagnosis.
    """
    stack = " -> ".join(type(screen).__name__ for screen in app.screen_stack)
    ids = sorted({f"#{w.id}" for w in app.screen.walk_children() if w.id})
    return f"screen stack: {stack}; ids on top screen: {', '.join(ids) or '(none)'}"
