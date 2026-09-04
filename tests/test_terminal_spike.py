"""The Phase 1 spike's own instrument check.

`scripts/spikes/terminal_target/` produces a number that gets quoted in a
report and decides whether `docs/TODO/terminal-target.md` proceeds. Everything
here is about the harness being trustworthy before it is pointed at a live
model, because every one of these failures is silent and expensive:

- a spec whose screens are not the archetype's would measure an app the tool
  would never have generated;
- a brief that varies per pass would make the runs incomparable and the number
  unquotable;
- a blank-screen check that cannot tell a painted screen from an empty one
  would report the target as working when it is not -- and that check is the
  whole of the plan's claim that terminal verification is cheaper and more
  deterministic than the browser stage.

These are cheap and use no API calls. Delete this file with the spike.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protopilot import archetypes  # noqa: E402
from protopilot.files import UnsafePath  # noqa: E402
from protopilot.passes import PassContext  # noqa: E402
from scripts.spikes.terminal_target import brief, writer  # noqa: E402
from scripts.spikes.terminal_target.boot_probe import buffer  # noqa: E402
from scripts.spikes.terminal_target.run import SPECS_DIR, load_spec, render_tui_skeleton, spec_names  # noqa: E402

textual = pytest.importorskip("textual", reason="the spike's boot check needs textual")


# ── the specs ────────────────────────────────────────────────────────────────


def test_there_are_three_specs_spanning_both_archetypes():
    names = spec_names()
    assert len(names) == 3, f"the plan asks for three specs; found {names}"
    kinds = {load_spec(name).archetype for name in names}
    assert kinds == set(archetypes.names()), f"the specs must span every archetype; they cover {kinds}"


@pytest.mark.parametrize("name", spec_names())
def test_spec_screens_are_the_archetypes_own_rule(name):
    """A hand-assembled spec is only a fair input if the tool would accept it.

    `screens_for` is what `spec_from_idea` runs, so re-running it must be a
    no-op. If it is not, the spike is measuring a screen list nobody's pipeline
    would ever have produced.
    """
    spec = load_spec(name)
    proposed = [s.model_dump(mode="json") for s in spec.screens]
    assert archetypes.screens_for(spec, proposed) == proposed


@pytest.mark.parametrize("name", spec_names())
def test_spec_files_are_committed_and_load(name):
    assert (SPECS_DIR / f"{name}.json").exists()
    assert load_spec(name).entities, "a spec with no entities generates nothing"


# ── the prompts ──────────────────────────────────────────────────────────────


def test_the_brief_is_byte_identical_across_every_pass():
    """The cache-prefix rule, checked rather than promised.

    `passes/_shared.py` states it for the web target and nothing enforces it
    there either -- but here it is also what makes six runs addable, so it is
    worth a test that fails when somebody interpolates a pass name into it.
    """
    spec = load_spec("field_notes")
    ctx = PassContext(project_dir=Path("."))
    ctx.failure = "something went wrong"
    systems = [p.build(spec, ctx)[0] for p in (*brief.CODE_PASSES, brief.REPAIR)]
    for system in systems:
        assert system.startswith(brief.TUI_BRIEF), "a pass does not open with the shared brief"
    assert len({s[: len(brief.TUI_BRIEF)] for s in systems}) == 1


#: Web-stack names that could only get into a terminal prompt as an
#: instruction. The stack's *negations* are deliberately not here -- "no
#: Postgres", "no Jinja", "no SVG" are the brief doing its job, and a checker
#: that could not tell those apart would forbid the brief from saying what is
#: absent, which is most of what a brief for a second target is for.
WEB_INSTRUCTIONS = (
    "APIRouter",
    "TemplateResponse",
    "app/routes.py",
    "app/templates",
    "Depends(get_db)",
    "RedirectResponse",
    'extends "base.html"',
)


def test_the_brief_instructs_nothing_the_web_target_owns():
    """The terminal brief must not carry the web stack in by accident."""
    assert [word for word in WEB_INSTRUCTIONS if word in brief.TUI_BRIEF] == []


#: Free text a person wrote, which the prompt shows the model verbatim. Nothing
#: else in a spec is prose.
PROSE_FIELDS = ("purpose", "direction")


@pytest.mark.parametrize("name", spec_names())
def test_no_spec_describes_its_own_medium(name):
    """The same spec drives both halves, so its prose has to fit both.

    This is not tidiness. `limits` is written by intake against *the fixed
    stack*, and the fixed stack is exactly what the target axis changes -- so
    the real kitten-chess spec said "both players take turns at the same
    browser", and handing that to a Textual pass is telling the model the app
    it is building is a web page. Reworded in the committed copy, and the
    reason recorded in `specs/README.md`.
    """
    spec = load_spec(name)
    prose = " ".join([getattr(spec, f) for f in PROSE_FIELDS] + list(spec.limits)).lower()
    leaked = [word for word in ("browser", "web page", "javascript", "html", "svg") if word in prose]
    assert not leaked, f"{name} describes the web medium in its own prose: {leaked}"


def test_the_archetype_fragment_is_the_terminal_one():
    """The web fragments say "browser" and "SVG"; handing one to a Textual pass
    would measure the model resolving a contradiction."""
    spec = load_spec("kitten_chess")
    block = brief.spec_block(spec)
    assert "browser" not in block
    assert "inline SVG" not in block
    assert "Grid" in block, "the turn-based fragment should describe a terminal board"


def test_every_archetype_has_a_terminal_fragment():
    assert set(brief.TUI_ARCHETYPE_BRIEFS) == set(archetypes.names())


# ── the write guard ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", brief.WRITABLE)
def test_the_allowed_paths_are_allowed(path):
    assert writer.check_path(path)


@pytest.mark.parametrize(
    "path",
    ["app/main.py", "app/db.py", "app/base.py", "tests/conftest.py", "/etc/passwd", "../escape.py", "pytest.ini"],
)
def test_the_skeleton_is_not_writable(path):
    with pytest.raises(UnsafePath):
        writer.check_path(path)


# ── the skeleton ─────────────────────────────────────────────────────────────


def test_the_skeleton_renders_with_no_placeholder_left(tmp_path):
    spec = load_spec("field_notes")
    written = render_tui_skeleton(spec, tmp_path)
    assert {str(p) for p in written} >= {"app/db.py", "app/base.py", "app/main.py", "tests/conftest.py", "pytest.ini"}
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "@@" not in path.read_text(), f"{path} still has a placeholder"


# ── the blank-screen check, which is the instrument ──────────────────────────


def _buffers():
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    class Blank(App):
        pass

    class Painted(App):
        def compose(self) -> ComposeResult:
            yield Label("a thing worth looking at")

    async def go():
        out = {}
        for key, cls in (("blank", Blank), ("painted", Painted)):
            app = cls()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                out[key] = buffer(app)
        return out

    return asyncio.run(go())


def test_the_blank_screen_check_tells_the_two_apart():
    """The plan's claim, demonstrated rather than asserted.

    This is also a guard against the specific way it silently breaks:
    `Screen.render_lines` renders the screen widget and returns blank rows for
    an app whose content is all in its children -- which is every app -- so a
    buffer taken that way reports a working app as empty and the whole
    measurement reads as a competence failure.
    """
    buffers = _buffers()
    assert buffers["blank"].strip() == "", "an app with nothing in it should render nothing"
    assert buffers["painted"] != buffers["blank"], "a painted screen must differ from an empty one"
    assert "a thing worth looking at" in buffers["painted"]


# ── calibrating the verifier against a tree no model wrote ───────────────────
#
# The point of these two is that they cost nothing and they answer the question
# "is a red run the model's fault or mine?" before a single live call is spent.
# A skeleton that cannot boot a hand-written app would report six failures and
# they would all be attributed to the target.

REFERENCE = {
    "app/models.py": """
from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)

    @property
    def display(self) -> str:
        return self.title
""",
    "app/seed.py": """
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Note


def seed(db: Session) -> None:
    if db.scalars(select(Note)).first():
        return
    db.add_all([Note(title="a heron"), Note(title="two swifts")])
    db.commit()
""",
    "app/screens.py": """
from __future__ import annotations

from sqlalchemy import select
from textual.app import ComposeResult
from textual.widgets import DataTable, Footer, Header

from app.base import AppScreen
from app.models import Note


class HomeScreen(AppScreen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="notes")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#notes", DataTable)
        table.add_columns("Title")
        with self.db() as db:
            for note in db.scalars(select(Note).order_by(Note.id)).all():
                table.add_row(note.display)
""",
    "app/app.tcss": "Screen { layout: vertical; }\n",
}

BLANK_SCREENS = '''
from __future__ import annotations

from textual.app import ComposeResult

from app.base import AppScreen


class HomeScreen(AppScreen):
    """A screen that renders nothing. The failure the plan wants demonstrated."""

    def compose(self) -> ComposeResult:
        return iter(())
'''


def _reference_tree(tmp_path, screens: str = "") -> Path:
    from scripts.spikes.terminal_target.run import render_tui_skeleton

    render_tui_skeleton(load_spec("field_notes"), tmp_path)
    for rel, body in REFERENCE.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.lstrip())
    if screens:
        (tmp_path / "app/screens.py").write_text(screens.lstrip())
    return tmp_path


def test_the_skeleton_boots_a_hand_written_app(tmp_path):
    """Green on a tree nobody generated, so a red run indicts the model."""
    from scripts.spikes.terminal_target.tui_verify import TuiVerifier

    verifier = TuiVerifier(project_dir=_reference_tree(tmp_path))
    assert verifier.check_import().ok, "the skeleton plus a trivial app does not import"
    probe = verifier.boot()
    assert probe.get("ok"), probe.get("traceback", "")
    assert probe["painted"], "a table with two seeded rows in it rendered as an empty screen"
    assert "a heron" in probe["buffer"], probe["buffer"]


def test_a_screen_that_renders_nothing_fails_verify(tmp_path):
    """The plan's acceptance criterion, demonstrated by building one."""
    from scripts.spikes.terminal_target.tui_verify import TuiVerifier

    verifier = TuiVerifier(project_dir=_reference_tree(tmp_path, screens=BLANK_SCREENS))
    probe = verifier.boot()
    assert probe.get("ok"), probe.get("traceback", "")
    assert not probe["painted"], "an app that composes no widgets should not count as painted"
