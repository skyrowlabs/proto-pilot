"""The terminal target: its passes, its prompts, and the tree they produce.

Phase 4 of `docs/implementations/spec/terminal-target.md`. The skeleton already had tests
(`test_tui_skeleton.py`) and so did the base screen (`test_tui_base_screen.py`);
what arrives here is everything between them — five passes, a brief, a write
allowlist, an offline baseline, and a target module that ties them together.

Three groups, and the middle one is the reason this file is longer than it
looks like it should be.

* **The passes**, checked against the invariants `build.py` states for every
  target rather than against a list: smoke before the code it tests, each pass
  handed the previous pass's real source, and one shared brief that is
  byte-identical across all of them.
* **The brief against the skeleton.** The Phase 1 report found the web
  target's *entire* failure mode was one sentence: `STACK_BRIEF` promised every
  `app.forms` parser took a fallback, `parse_bool` did not, and every run with
  a bool field burned a repair attempt doing exactly what it was told. That is
  a producer and a consumer inside one repo disagreeing about a published
  artifact, and it cost three of three runs. These tests are the gate that
  class does not have on the web side.
* **The tree**, generated offline through the real pipeline and then made to
  run its own suite. There is no way to assert a prompt produced good code;
  there is a way to assert the deterministic half produces an app that starts,
  paints, and passes the tests it was given.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from protopilot import targets
from protopilot.build import generate
from protopilot.files import UnsafePath, banner_for, check_path
from protopilot.llm import OfflineLLM
from protopilot.passes import PassContext, run_pass
from protopilot.passes.tui import _brief
from protopilot.render import TOKEN_RE, render_skeleton
from protopilot.spec import Spec
from scanning import scanned
from tests.fakes import FakeLLM

# Host-side: no key, no Docker daemon, no browser, no port. That this whole
# file needs none of them is half of what the terminal target is for.
pytestmark = [pytest.mark.unit]

pytest.importorskip("textual")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pytest_asyncio")

TUI = targets.get("tui")
SKELETON = TUI.SKELETON_DIR


@pytest.fixture()
def tui_spec(spec) -> Spec:
    """The shared two-entity fixture, pointed at the terminal target."""
    spec.target = "tui"
    return spec


@pytest.fixture()
def tree(tui_spec, tmp_path) -> Path:
    """A terminal tree generated offline through the real pipeline.

    `build.generate` rather than calling the baseline directly: the write
    guard, the banner, the pass order and the target lookup are all things that
    can be wrong, and none of them are exercised by asking a generator for a
    string.
    """
    render_skeleton(tui_spec, tmp_path)
    tui_spec.save(tmp_path)
    generate(tui_spec, PassContext(project_dir=tmp_path), OfflineLLM(), log=lambda _: None)
    return tmp_path


# ── the target ───────────────────────────────────────────────────────────


def test_the_target_owns_a_skeleton_that_is_not_the_web_one():
    assert SKELETON == targets.SKELETON_ROOT / "tui"
    assert SKELETON != targets.get("web").SKELETON_DIR
    assert not (SKELETON / "compose.yml").exists(), "a one-process target has nothing to compose"


def test_the_writable_list_is_exactly_what_the_passes_produce():
    """Both directions, so neither can drift alone.

    A path in `WRITABLE` that no pass writes is dead permission; a pass whose
    `WRITES` is not in `WRITABLE` is a pass that fails at the write guard on
    every run. Neither shows up anywhere else.
    """
    produced = {path for module in TUI.CODE_PASSES for path in module.WRITES}
    assert produced == set(TUI.WRITABLE)


def test_the_repair_pass_may_write_everything_the_others_can():
    """`REPAIR.WRITES` is empty and that does not mean "writes nothing" — the
    real set is the target's, enforced by `run_pass`. Asserted here because the
    empty tuple is the one place a reader could take it literally."""
    assert TUI.REPAIR.WRITES == ()
    assert TUI.REPAIR.NAME == "repair"


def test_the_verifier_is_the_terminal_one(tui_spec, tmp_path):
    """The factory hands back a `Verifies`, and it is not the Docker one.

    `tests/test_tui_verify.py` covers what it does; this is the assertion that
    the registry points at it at all, which is what `cli._verifier` and the web
    front end both go through.
    """
    from protopilot.verify import Verifier
    from protopilot.verify_tui import TuiVerifier

    made = TUI.verifier(tmp_path, tui_spec)
    assert isinstance(made, TuiVerifier)
    assert not isinstance(made, Verifier)


def test_the_target_needs_nothing_to_be_running(tui_spec):
    """`preflight` is what `proto new` asks before it spends anything. For this
    target the answer is always yes, and that is the point: a terminal app on a
    machine with no Docker daemon is a generation that should happen."""
    ok, why = TUI.preflight(runner=None)
    assert ok and why


def test_every_declared_archetype_has_a_terminal_brief():
    """A pair this target claims it can build has to be sayable to the model.

    The reverse is deliberately not asserted: `ARCHETYPE_BRIEFS` may carry a
    fragment for a shape that has no terminal offline baseline yet, and holding
    the measured text is worth more than a symmetry.
    """
    for name in TUI.ARCHETYPES:
        assert name in _brief.ARCHETYPE_BRIEFS, f"the tui target claims {name!r} and cannot describe it"


def test_an_unsupported_pair_is_refused_naming_both_halves():
    """A shape this target does not build is refused at intake, by name.

    The matrix has no hole in it today — `ARCHETYPES` is every installed
    archetype, which it has to be now that this is `targets.DEFAULT`. So the
    refusal is exercised with a name no build will ever have, rather than by
    skipping when the hole closes: a skip is how a suite quietly stops testing,
    and this assertion is about the mechanism rather than about today's
    coverage.
    """
    with pytest.raises(targets.UnsupportedPair) as caught:
        targets.check_pair("tui", "holodeck")
    message = str(caught.value)
    assert "tui" in message and "holodeck" in message
    assert "crud" in message, "a refusal that does not say what it CAN build leaves nowhere to go"


def test_it_builds_every_installed_archetype():
    """No hole in the default target. `tests/test_targets.py` asserts this of
    whichever target is default; this says it of `tui` by name, so demoting it
    later does not silently take the coverage with it."""
    from protopilot import archetypes

    assert set(TUI.ARCHETYPES) == set(archetypes.names())


# ── the passes ───────────────────────────────────────────────────────────


def test_every_pass_declares_the_shape_run_pass_reads():
    for module in (*TUI.CODE_PASSES, TUI.REPAIR):
        for attr in ("NAME", "WRITES", "SCHEMA"):
            assert hasattr(module, attr), f"{module.__name__} does not declare {attr}"
        assert callable(module.build) and callable(module.offline)


def test_the_pass_names_are_the_ones_phase_one_measured():
    """`schema -> smoke -> seed -> screens -> ui`, in that order.

    The names are not cosmetic: the Phase 1 report's per-pass cost table is
    keyed by them, and a rename makes the two expensive ones — `smoke` at ~6.4x
    its web twin and `screens` at ~4.3x — unfindable in the record that
    justified building this target at all.
    """
    assert [m.NAME for m in TUI.CODE_PASSES] == ["schema", "smoke", "seed", "screens", "ui"]


def test_the_smoke_pass_runs_before_the_code_it_tests():
    """The invariant, computed from the tuple rather than restated.

    Tests written after the code describe whatever the code happened to do.
    Reordering these two silently turns the smoke suite from a target into a
    description, and nothing else in the repo would notice.
    """
    order = [m.NAME for m in TUI.CODE_PASSES]
    assert order.index("smoke") < order.index("screens")
    assert order.index("schema") < order.index("smoke"), "smoke is written against the models"
    assert order.index("ui") == len(order) - 1, "ui reads the real screens and so goes last"


def test_each_pass_is_handed_the_previous_passes_real_source(tui_spec, tmp_path):
    """Not a description of it. Driven by writing recognisable source into the
    tree and looking for it in the next pass's user message."""
    ctx = PassContext(project_dir=tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "models.py").write_text("MODELS_MARKER = 1\n")
    (tmp_path / "tests" / "test_smoke.py").write_text("SMOKE_MARKER = 1\n")
    (tmp_path / "app" / "screens.py").write_text("SCREENS_MARKER = 1\n")

    from protopilot.passes.tui import screens as screens_pass
    from protopilot.passes.tui import seed as seed_pass
    from protopilot.passes.tui import smoke as smoke_pass
    from protopilot.passes.tui import ui as ui_pass

    assert "MODELS_MARKER" in smoke_pass.build(tui_spec, ctx)[1]
    assert "MODELS_MARKER" in seed_pass.build(tui_spec, ctx)[1]
    assert "SMOKE_MARKER" in screens_pass.build(tui_spec, ctx)[1], "the screens pass is not given its target"
    assert "SCREENS_MARKER" in ui_pass.build(tui_spec, ctx)[1], "the stylesheet is written blind"


def test_the_brief_is_byte_identical_across_every_pass(tui_spec, tmp_path):
    """The cache-prefix rule, checked rather than promised.

    `passes/_shared.py` states it for the web target and nothing enforces it
    there. Here it is also what makes the Phase 1 per-pass numbers addable, so
    a pass name interpolated into the prefix would cost money twice.
    """
    ctx = PassContext(project_dir=tmp_path)
    ctx.failure = "something went wrong"
    systems = [module.build(tui_spec, ctx)[0] for module in (*TUI.CODE_PASSES, TUI.REPAIR)]
    for system in systems:
        assert system.startswith(_brief.TUI_BRIEF), "a pass does not open with the shared brief"
    assert len({system[: len(_brief.TUI_BRIEF)] for system in systems}) == 1


#: Web-stack names that could only reach a terminal prompt as an instruction.
#:
#: The stack's *negations* are deliberately absent — "no Postgres", "no Jinja",
#: "no SVG" are the brief doing its job, and a checker that could not tell
#: those apart would forbid the brief from saying what is missing, which is
#: most of what a brief for a second medium is for.
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
    assert [word for word in WEB_INSTRUCTIONS if word in _brief.TUI_BRIEF] == []


def test_the_archetype_fragment_is_the_terminal_one(tui_spec):
    """The web fragments say "browser" and "inline SVG". Handing one to a
    Textual pass measures the model resolving a contradiction."""
    tui_spec.archetype = "turn-based-game"
    block = _brief.spec_block(tui_spec)
    assert "browser" not in block
    assert "inline SVG" not in block
    assert "Grid" in block, "the turn-based fragment should describe a terminal board"


def test_the_theme_reaches_the_ui_pass_and_no_other(tui_spec, tmp_path):
    """`PASS_HIDDEN` drops the theme from every spec block; the ui pass is the
    one that puts it back. The same rule the web target has, and it has to hold
    per target because each one builds its own prompt."""
    from protopilot.passes.tui import screens as screens_pass
    from protopilot.passes.tui import ui as ui_pass
    from protopilot.spec import Theme

    tui_spec.theme = Theme(palette="high-contrast neon", tone="playful")
    ctx = PassContext(project_dir=tmp_path)

    assert "neon" in ui_pass.build(tui_spec, ctx)[1]
    assert "neon" not in screens_pass.build(tui_spec, ctx)[1]


# ── the brief against the skeleton it describes ──────────────────────────
#
# The gate the web target does not have. Every entry is a promise the brief
# makes about a file the model cannot see, and a promise that is not true costs
# a repair attempt on every single generation -- silently, because the model
# does exactly what it was told and the failure looks like incompetence.

#: What `TUI_BRIEF` says exists, and where it says it lives.
#:
#: Checked in both directions per entry: the name has to be IN the brief, and
#: it has to be DEFINED in that skeleton file. One direction alone rots -- a
#: table that only checks the skeleton stays green when the brief stops
#: mentioning something, and a table that only checks the brief stays green
#: when the skeleton stops providing it.
PROMISED = {
    "app/db.py": ("Base", "engine", "SessionLocal", "session"),
    "app/base.py": ("AppScreen",),
    "app/main.py": ("TerminalApp",),
    "tests/screen.py": ("visible", "screen_text", "buffer", "mentions", "where"),
}


def defined_in(rel: str) -> set[str]:
    """Every top-level name a skeleton file defines."""
    module = ast.parse((SKELETON / rel).read_text(), rel)
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return names


@pytest.mark.parametrize("rel,promised", sorted(PROMISED.items()))
def test_the_brief_only_promises_things_the_skeleton_has(rel, promised):
    available = defined_in(rel)
    for name in promised:
        assert name in _brief.TUI_BRIEF, f"the brief no longer mentions {name}; is this table stale?"
        assert name in available, f"the brief tells every pass to import {name} from {rel}, and it is not there"


def test_the_base_screen_binds_the_keys_the_brief_says_it_does():
    source = (SKELETON / "app" / "base.py").read_text()
    assert '"q"' in source and '"escape"' in source
    assert "def db(" in source, "the brief promises `self.db()` on every screen"


def test_the_brief_describes_how_the_home_screen_is_reached():
    """`app/main.py` returns `HomeScreen` from `get_default_screen()`; it used
    to push it, which put it at depth two and made Escape empty the app. A
    brief still describing the push would be the `parse_bool` defect again."""
    assert "get_default_screen" in (SKELETON / "app" / "main.py").read_text()
    assert "push" not in _brief.TUI_BRIEF.split("`app.main`")[1].split("- `app.models`")[0]


# ── the write guard, on this target's list ───────────────────────────────


@pytest.mark.parametrize("path", TUI.WRITABLE)
def test_a_generated_path_is_allowed(path):
    assert check_path(path, TUI.WRITABLE, TUI.PROTECTED)


@pytest.mark.parametrize(
    "path",
    ["app/main.py", "app/db.py", "app/base.py", "tests/conftest.py", "tests/screen.py", "pytest.ini", "../escape.py"],
)
def test_the_skeleton_is_not_writable(path):
    with pytest.raises(UnsafePath):
        check_path(path, TUI.WRITABLE, TUI.PROTECTED)


def test_a_web_path_returned_into_a_terminal_tree_is_refused(tui_spec, tmp_path):
    """The seam Phase 2 built, exercised from the other side. `run_pass`
    resolves the target from the spec at the moment of writing, so a pass
    returning `app/routes.py` into a terminal tree is refused with the terminal
    list named in the error."""
    from protopilot.passes.tui import schema as schema_pass

    rogue = FakeLLM([{"files": [{"path": "app/routes.py", "content": "x = 1\n"}], "notes": ""}])
    with pytest.raises(UnsafePath) as caught:
        run_pass(schema_pass, tui_spec, PassContext(project_dir=tmp_path), rogue)
    assert "app/screens.py" in str(caught.value)
    assert not (tmp_path / "app" / "routes.py").exists()


def test_a_stylesheet_gets_a_stylesheet_comment():
    """`app/app.tcss` is the first generated file that is neither Python nor
    Jinja. A `#` banner on it is a parse error at app construction time, which
    Textual raises before a single screen is drawn."""
    assert banner_for("app/app.tcss", "ui").startswith("/*")
    assert banner_for("app/models.py", "schema").startswith("#")


# ── the generated tree ───────────────────────────────────────────────────


def test_no_placeholder_survives_generation(tree):
    checked = scanned(
        sorted(p for p in tree.rglob("*") if p.is_file() and p.suffix in {".py", ".tcss", ".md", ".txt", ".ini"}),
        "placeholders in the generated tree",
    )
    for path in checked:
        assert not TOKEN_RE.search(path.read_text()), f"{path} kept a placeholder"


def test_every_python_file_parses(tree):
    for path in scanned(sorted(tree.rglob("*.py")), "python files in the generated tree"):
        ast.parse(path.read_text(), str(path))


def test_the_generated_files_carry_a_banner(tree):
    for rel in ("app/models.py", "app/screens.py", "app/seed.py", "tests/test_smoke.py"):
        assert "GENERATED by proto-pilot" in (tree / rel).read_text().split("\n", 2)[0]
    assert (tree / "app" / "app.tcss").read_text().startswith("/* GENERATED by proto-pilot")


def test_the_skeleton_was_not_touched(tree, tui_spec, tmp_path):
    """The whole point of the write guard, checked on the product rather than
    on the guard.

    Compared against a freshly RENDERED skeleton rather than against the source
    tree: `@@APP_NAME@@` and friends are substituted on the way in, so the
    source bytes are the wrong control and would fail here for the one reason
    that is not a defect.
    """
    control = tmp_path / "control"
    render_skeleton(tui_spec, control)
    for rel in ("app/main.py", "app/db.py", "app/base.py", "tests/conftest.py", "tests/screen.py", "pytest.ini"):
        assert (tree / rel).read_text() == (control / rel).read_text(), f"{rel} was rewritten"


def test_the_generated_app_passes_its_own_smoke_suite(tree):
    """The tree IS the test.

    proto-pilot cannot assert that a prompt produced good code. It can assert
    that skeleton plus five passes plus the write guard yields an app that
    starts, paints, navigates and stores a row — with no key, no daemon, no
    browser and no port, which is the whole argument for this target.

    A subprocess, because the tree's `conftest.py` redirects `APP_DB` before
    `app.db` is imported anywhere and that ordering is the only fragile thing
    in it.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "tests/"],
        cwd=str(tree),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"the generated terminal app is red:\n{result.stdout}\n{result.stderr}"


def test_the_generated_suite_actually_drives_the_app(tree):
    """A smoke suite that only booted the app would pass against a screen with
    nothing on it. These are the three things it has to do beyond starting:
    reach a screen by keypress, open a record, and store a row."""
    source = (tree / "tests" / "test_smoke.py").read_text()
    assert "pilot.press" in source, "nothing in the generated suite touches the keyboard"
    assert "mentions(" in source, "nothing reads what is actually on screen"
    assert "before + 1" in source, "no create round trip; a read-only app would pass"


def test_the_generation_is_byte_stable(tui_spec, tmp_path):
    """The characterisation discipline: the same spec generates the same tree.

    Without this the golden manifests churn on every unrelated run and stop
    being evidence of anything.
    """
    first, second = tmp_path / "one", tmp_path / "two"
    for target in (first, second):
        render_skeleton(tui_spec, target)
        generate(tui_spec, PassContext(project_dir=target), OfflineLLM(), log=lambda _: None)

    for path in sorted(first.rglob("*.py")):
        rel = path.relative_to(first)
        assert path.read_text() == (second / rel).read_text(), f"{rel} differs between two identical generations"


# ── the characterisation ─────────────────────────────────────────────────


GOLDEN = Path(__file__).resolve().parent / "golden" / "tui_offline_manifest.json"


def manifest(tree: Path) -> dict:
    """Every file in a generated terminal tree, hashed.

    Nothing is normalised, and nothing needs to be: unlike the web tree this
    one embeds no absolute path and no port anywhere — the only substitutions
    it makes are the app's name, purpose and slug. The absence of a
    normalisation step here is itself a fact about the target.
    """
    out = {}
    for path in sorted(tree.rglob("*")):
        if not path.is_file() or {"__pycache__", ".pytest_cache", ".git"} & set(path.parts):
            continue
        out[str(path.relative_to(tree))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_the_offline_terminal_generation_is_unchanged(tree):
    """A characterisation, not a specification. It asserts nothing about
    whether the output is good — only that it is the same as last time, so a
    change to a generator that was meant to be cosmetic has to be looked at.

    Regenerate deliberately, and read the diff before committing it:

        PROTOPILOT_REGOLD=1 python -m pytest tests/test_tui_target.py

    A golden file updated without reading the diff asserts nothing.
    """
    current = manifest(tree)
    if os.environ.get("PROTOPILOT_REGOLD"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        pytest.skip("regenerated the golden manifest")

    expected = json.loads(GOLDEN.read_text())
    assert sorted(current) == sorted(expected), "the set of files in a generated terminal tree changed"
    changed = sorted(name for name in expected if current[name] != expected[name])
    assert not changed, f"generated output changed for: {changed}"


def test_the_golden_manifest_covers_the_files_that_matter():
    """A manifest that silently stopped covering the tree would pass forever."""
    expected = json.loads(GOLDEN.read_text())
    for path in (
        "app/main.py",
        "app/screens.py",
        "app/app.tcss",
        "tests/screen.py",
        "tests/test_smoke.py",
        ".gitignore",
    ):
        assert path in expected, f"{path} is missing from the tree being characterised"
