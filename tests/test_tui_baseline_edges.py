"""The two spec shapes at the edges of the terminal baseline.

`protopilot/baseline_tui.py` has branches for both and neither had a test: the
shared fixture is two entities, and every terminal test in this suite runs on
it. The two edges are the ones the generator itself names.

**No entities.** Reachable — an intake that found nothing concrete produces
one, which is why `tests/test_baseline.py` already pins it for the web target
— and the generator carries three explicit fallbacks for it: a placeholder
binding, a commented-out counts list and an `action_noop`. A fallback that has
never run is a fallback nobody has seen the output of, and the output here is a
Python file that has to parse, import, mount and paint.

**More entities than there are digits.** `HOME_KEYS = 9` is a stated limit
rather than an oversight, and a spec with ten entities is not exotic. What a
stated limit needs is a test that says what it actually does to the tree,
because the honest answer is not "the tenth entity is dropped" — it is modelled
and seeded like every other one, and only the home screen's shortcut is gone.
Nothing anywhere said that, and the difference is what a person reading a
ten-entity generation would want to know.

Both edges are driven through the real pipeline and the real verifier: an
assertion about a generator's string cannot tell the difference between a file
that parses and an app that runs.
"""

from __future__ import annotations

import ast

import pytest

from protopilot.baseline_tui import HOME_KEYS
from protopilot.build import PassContext
from protopilot.build import generate as run_passes
from protopilot.llm import OfflineLLM
from protopilot.render import render_skeleton
from protopilot.spec import Entity, Field_, Spec
from protopilot.targets import tui as tui_target
from protopilot.verify_tui import TuiVerifier

# Host-side: no key, no Docker daemon, no browser, no port.
pytestmark = [pytest.mark.unit]

pytest.importorskip("textual")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pytest_asyncio")


def built_tree(spec: Spec, root):
    """One offline generation through the real pipeline, into `root`."""
    render_skeleton(spec, root)
    spec.save(root)
    run_passes(spec, PassContext(project_dir=root), OfflineLLM(), log=lambda _: None)
    return root


def built(tree, spec: Spec) -> TuiVerifier:
    """The registry's verifier, narrowed to the class it actually is.

    `verifier()` is annotated `-> Verifies` because `drive_to_green` must never
    learn which implementation it got. These tests reach past the Protocol for
    the boot payload, so the narrowing is stated once — the same helper, for the
    same reason, as `tests/test_tui_verify.py`.
    """
    made = tui_target.verifier(tree, spec)
    assert isinstance(made, TuiVerifier)
    return made


def numbered_spec(count: int) -> Spec:
    """`count` interchangeable entities, so the only variable is how many.

    Named `Thing1`…`Thing10` on purpose: the home screen labels them by their
    plural, so `Thing10s` cannot be mistaken for a substring of any other row.
    """
    return Spec(
        name="Many Things",
        slug="many_things",
        purpose="Track more things than there are digits.",
        target="tui",
        entities=[Entity(name=f"Thing{i}", fields=[Field_(name="title", type="str")]) for i in range(1, count + 1)],
    )


def home_screen_text(tree, spec: Spec) -> str:
    """Boot the generated app and read what its home screen is showing.

    The probe rather than the source: what matters is which shortcuts a person
    can actually see and press, and a `BINDINGS` list is a claim about that
    rather than the thing itself.
    """
    payload = built(tree, spec).boot()
    assert payload["ok"], payload.get("traceback", "")
    assert payload["screen"] == "HomeScreen"
    return payload["text"]


def home_binding_keys(tree) -> list[str]:
    """The keys `HomeScreen.BINDINGS` offers, in order, read out of the tree.

    Off the generated source rather than off a running app because a binding
    that cannot be pressed is exactly what is being looked for, and a key no
    keyboard sends is invisible from the other side.
    """
    module = ast.parse((tree / "app" / "screens.py").read_text())
    home = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "HomeScreen")
    bindings = next(
        node.value
        for node in home.body
        if isinstance(node, ast.Assign) and any(getattr(target, "id", "") == "BINDINGS" for target in node.targets)
    )
    assert isinstance(bindings, ast.List), "HomeScreen.BINDINGS stopped being a list of Binding(...) calls"
    keys = []
    for element in bindings.elts:
        assert isinstance(element, ast.Call), "a BINDINGS entry that is not a Binding(...) call"
        first = element.args[0]
        assert isinstance(first, ast.Constant), "a binding whose key is computed rather than written down"
        keys.append(str(first.value))
    return keys


# ── a spec with no entities at all ───────────────────────────────────────


@pytest.fixture()
def empty_tree(tmp_path):
    spec = Spec(name="Empty", slug="empty", purpose="Nothing concrete yet.", target="tui")
    return built_tree(spec, tmp_path), spec


def test_a_spec_with_no_entities_verifies_green(empty_tree):
    """The whole pipeline, end to end, on the shape with nothing in it.

    Not "the file parses": it imports, mounts, runs `create_all` and `seed`
    over no tables at all, paints, survives a keystroke and passes the tree's
    own suite. Every one of those is a separate way an empty spec could have
    produced a tree that only looked finished.
    """
    tree, spec = empty_tree
    result = built(tree, spec).verify()
    assert result.ok, f"{result.stage}: {result.summary}\n{result.output}"


def test_the_empty_home_screen_still_says_what_the_app_is(empty_tree):
    """The fallbacks exist to keep a screen readable, not merely importable.

    A home screen with no sections is the first thing a person sees for an app
    the intake could not pin down, and `test_boots.py` fails a tree whose first
    screen holds no text — so the placeholder path has to carry the name and
    the purpose or the generation is red for a spec that was merely vague.
    """
    tree, spec = empty_tree
    text = home_screen_text(tree, spec)
    assert "Empty" in text
    assert "Nothing concrete yet." in text


def test_the_empty_home_screen_offers_no_shortcut_to_nowhere(empty_tree):
    """The placeholder binding is a no-op and it is bound to something that is
    not a digit — a `1` on an app with no first section is a keystroke that
    reads as broken."""
    tree, _ = empty_tree
    source = (tree / "app" / "screens.py").read_text()
    tree_ast = ast.parse(source)

    classes = {node.name for node in ast.walk(tree_ast) if isinstance(node, ast.ClassDef)}
    assert classes == {"HomeScreen"}, f"an entity-less spec produced entity screens: {sorted(classes)}"

    methods = {
        node.name
        for node in ast.walk(tree_ast)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("action_")
    }
    assert methods == {"action_noop"}
    assert "push_screen" not in source, "the home screen offers a way into a screen that does not exist"

    keys = home_binding_keys(tree)
    assert not [key for key in keys if key.isdigit()], f"a digit opens nothing on an empty home screen: {keys}"


def test_the_empty_smoke_suite_still_asserts_the_app_starts(empty_tree):
    """A generated suite with nothing in it is the one failure mode a green
    run cannot show you. With no entities there is exactly one thing left to
    assert, and it has to still be asserted."""
    tree, _ = empty_tree
    source = (tree / "tests" / "test_smoke.py").read_text()
    tests = [
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
    ]
    assert tests == ["test_the_app_starts_on_the_home_screen"]


# ── more entities than there are digits ──────────────────────────────────


@pytest.mark.parametrize("count", [HOME_KEYS, HOME_KEYS + 1])
def test_every_home_shortcut_is_one_keystroke(tmp_path, count):
    """`HOME_KEYS` is bound by the keyboard, not by taste, and this is the
    assertion that says so without restating the number.

    Raising the limit produces `Binding("10", ...)`. Textual accepts it, the
    footer shows it, the home table lists a tenth row — and nothing sends a key
    called "10", so the section is advertised and unreachable. Every shortcut
    being a single character is the property that fails the moment the limit
    stops being the digits there are.
    """
    tree = built_tree(numbered_spec(count), tmp_path)
    keys = home_binding_keys(tree)

    assert keys == [str(index) for index in range(1, min(count, HOME_KEYS) + 1)]
    assert all(len(key) == 1 for key in keys), f"a shortcut nobody can press: {keys}"


@pytest.mark.parametrize("count", [HOME_KEYS, HOME_KEYS + 1])
def test_the_home_screen_lists_one_section_per_digit_and_no_more(tmp_path, count):
    """Both sides of the boundary, so an off-by-one is caught in either
    direction: exactly `HOME_KEYS` entities all get a shortcut, and the one
    past it gets none.

    Read off a running app rather than off `BINDINGS`, because the row and the
    binding are generated from two different loops and could disagree.
    """
    spec = numbered_spec(count)
    text = home_screen_text(built_tree(spec, tmp_path), spec)

    listed = [entity for entity in spec.entities if entity.plural.capitalize() in text]
    assert len(listed) == min(count, HOME_KEYS)
    for index in range(1, min(count, HOME_KEYS) + 1):
        assert f"Thing{index}s" in text, f"Thing{index} has a digit and is not on the home screen"
    if count > HOME_KEYS:
        assert f"Thing{count}s" not in text, "an entity past the digits was listed with no key to press"


def test_the_entity_past_the_limit_is_still_modelled_and_seeded(tmp_path):
    """The limit is on the home screen and nowhere else.

    This is the assertion the stated limit was missing: a tenth entity is not
    dropped from the spec, from the schema or from the seed — it is built and
    filled exactly like the other nine, and what it lacks is one keystroke.
    Reading "9 sections" off a screen and concluding the tenth table is gone is
    the mistake this makes impossible.
    """
    count = HOME_KEYS + 1
    spec = numbered_spec(count)
    tree = built_tree(spec, tmp_path)
    last = f"Thing{count}"

    models = (tree / "app" / "models.py").read_text()
    seed = (tree / "app" / "seed.py").read_text()
    screens = (tree / "app" / "screens.py").read_text()

    assert f"class {last}(" in models
    assert last in seed, "the entity past the limit is never given a row"
    for kind in ("ListScreen", "FormScreen", "RecordScreen"):
        assert f"class {last}{kind}(" in screens, f"{last} lost its {kind}"


def test_the_tree_past_the_limit_boots_and_paints(tmp_path):
    """Ten entities is thirty-one screen classes in one module. That it still
    imports, mounts and paints is not implied by any of the assertions above."""
    count = HOME_KEYS + 1
    spec = numbered_spec(count)
    tree = built_tree(spec, tmp_path)

    verifier = built(tree, spec)
    assert verifier.check_import().ok, "a ten-entity screens module does not import"
    payload = verifier.boot()

    assert payload["ok"] and payload["painted"], payload.get("traceback", "")
    assert payload["depth"] == 1, "the home screen is not the bottom of the stack"


def test_the_generated_suite_covers_what_can_be_reached_and_says_nothing_else(tmp_path):
    """A smoke test for the tenth entity would press a key that does not exist
    and fail against a working app. The suite stops where the navigation does,
    which is the honest shape — and it is why the assertion above about the
    model and the seed is the one that has to carry the tenth entity."""
    count = HOME_KEYS + 1
    spec = numbered_spec(count)
    tree = built_tree(spec, tmp_path)

    source = (tree / "tests" / "test_smoke.py").read_text()
    covered = {
        entity.name
        for entity in spec.entities
        if f"select({entity.name})" in source or f"count()).select_from({entity.name})" in source
    }

    assert covered == {f"Thing{i}" for i in range(1, HOME_KEYS + 1)}
    assert f"Thing{count}" not in covered
