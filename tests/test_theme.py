"""The look axis, and the one claim that makes it worth having.

`theme` is orthogonal to `archetype` on purpose: a theme costs one prompt
fragment and no offline baseline at all, which is only true while it cannot
reach anything but the templates. The moment a theme can change a route, a
column or a test, it is an archetype wearing the wrong name and the work
becomes |archetypes| x |themes|.

So the load-bearing test here is `test_the_theme_reaches_the_ui_pass_and_no_other`.
Everything else is about it staying cheap: the baseline ignoring themes is what
keeps them free to add.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from protopilot.passes import PassContext, models, repair, routes, seed, smoke, ui
from protopilot.spec import Screen, Spec, Theme

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit

#: Distinctive enough that a match cannot be a coincidence, and each word is
#: one a generated app might plausibly contain -- which is the point: the test
#: must fail on a leak, not on a shared adjective.
THEME = Theme(
    subject="capybaras in raincoats",
    palette="washed-out seaside pastels",
    motif="tiny umbrellas",
    tone="deadpan",
)
FINGERPRINTS = ("capybaras in raincoats", "washed-out seaside pastels", "tiny umbrellas", "deadpan")

#: Every pass that is handed a spec. `intake` is absent because it is handed an
#: idea string and has no spec to leak; `clarify` is absent because it is what
#: *produces* the theme.
SPEC_PASSES = (models, seed, routes, smoke, ui)


def themed_spec() -> Spec:
    """`plain_spec()` and nothing else changed.

    Identical but for the theme, deliberately: the baseline comparison below
    is only honest if the theme is the single difference between the two
    trees.
    """
    spec = plain_spec()
    spec.theme = THEME
    return spec


def plain_spec() -> Spec:
    from protopilot.spec import Entity, Field_

    spec = Spec(name="Kitten Tracker", slug="kitten_tracker", purpose="Keep track of kittens.")
    spec.entities = [
        Entity(
            name="Kitten",
            plural="kittens",
            fields=[
                Field_(name="title", type="str", required=True),
                Field_(name="notes", type="text", required=False),
            ],
        )
    ]
    from protopilot import archetypes

    spec.screens = [Screen(**s) for s in archetypes.screens_for(spec)]
    return spec


@pytest.fixture()
def ctx(tmp_path) -> PassContext:
    c = PassContext(project_dir=tmp_path, failure="something went wrong")
    return c


# -- the rule -------------------------------------------------------------


def test_the_theme_reaches_the_ui_pass_and_no_other(ctx):
    """The whole justification for a second axis.

    A theme that can reach `models` renames columns; one that can reach
    `smoke` writes assertions about a look. Both make a theme cost a baseline,
    which is exactly what keeping the axes apart is buying us.
    """
    spec = themed_spec()
    for module in SPEC_PASSES:
        system, user = module.build(spec, ctx)
        prompt = system + user
        found = [f for f in FINGERPRINTS if f in prompt]
        if module is ui:
            assert found == list(FINGERPRINTS), "the UI pass must be shown the whole theme"
        else:
            assert not found, f"{module.NAME} was shown the theme: {found}"


def test_the_repair_pass_is_not_shown_the_theme_either(ctx):
    """Repair is given the current source of every generated file, so it can
    already see the themed markup it is fixing. Handing it the theme as well
    invites a restyle during a bug fix, which is the one moment nobody is
    looking at the artwork."""
    system, user = repair.build(themed_spec(), ctx)
    assert not [f for f in FINGERPRINTS if f in system + user]


def test_amending_a_spec_does_not_show_the_theme():
    """Sharper than the code passes: `amend` reuses the intake schema, where
    `theme` is a model-owned exclusion. The model could not return it, so
    showing it could only invite an opinion with nowhere to land."""
    from protopilot.passes import intake

    system, user = intake.build_amend(themed_spec(), "add a vet visit")
    assert not [f for f in FINGERPRINTS if f in system + user]


def test_only_the_ui_pass_reads_the_theme_in_source():
    """Structural, and recomputed rather than allowlisted: the prompt test
    above can only catch a leak through wording that happens to survive into
    the prompt. A pass that branched on `spec.theme` without quoting it would
    slip past it."""
    offenders = []
    for path in sorted(Path("protopilot/passes").glob("*.py")):
        if path.name == "ui.py":
            continue
        if ".theme" in path.read_text():
            offenders.append(path.name)
    assert not offenders, f"these passes read spec.theme: {offenders}"


# -- what the UI pass is actually told -------------------------------------


def test_the_ui_prompt_asks_for_the_theme_to_be_drawn():
    """The prompt already insisted artwork is drawn rather than emoji. A theme
    is what gives that instruction a subject."""
    block = ui.theme_block(themed_spec())
    assert "capybaras in raincoats" in block
    assert "draw" in block.lower()


def test_the_theme_may_not_become_a_stylesheet():
    """This pass may not write CSS -- the stylesheet is skeleton. So a palette
    has to arrive as `fill` and `stroke` on shapes the pass is already drawing,
    and saying so is the difference between a themed app and a 500."""
    block = ui.theme_block(themed_spec())
    assert "fill" in block and "stroke" in block
    assert "<style>" in block, "the prompt must name the thing it is forbidding"


def test_the_theme_may_not_rename_anything():
    block = ui.theme_block(themed_spec())
    assert "context key" in block


def test_a_partial_theme_only_speaks_about_what_it_has():
    """Every field is optional and the classifier is told to leave a field it
    is guessing at empty. An invented palette is worse than no palette."""
    spec = plain_spec()
    spec.theme = Theme(subject="capybaras in raincoats")
    block = ui.theme_block(spec)
    assert "capybaras in raincoats" in block
    assert "Palette" not in block and "Motif" not in block and "Tone" not in block


def test_no_theme_and_an_empty_theme_both_add_nothing(ctx):
    for value in (None, Theme()):
        spec = plain_spec()
        spec.theme = value
        assert ui.theme_block(spec) == ""


def test_the_human_checkpoint_still_shows_the_theme():
    """Hidden from the passes, never from the person. The review checkpoint is
    the only human gate in the tool, and an axis it does not print is an axis
    nobody reviews."""
    assert "capybaras in raincoats" in themed_spec().summary()


# -- what a theme costs ----------------------------------------------------


def test_the_offline_baseline_ignores_the_theme(tmp_path):
    """The economics of the axis, stated as a test. A theme that changed
    generated output would need a baseline per theme, and the baseline is what
    CI runs -- so themes would stop being free and start being a queue."""
    from protopilot.build import generate
    from protopilot.llm import OfflineLLM
    from protopilot.render import render_skeleton

    def tree(spec: Spec, into: Path) -> dict[str, str]:
        render_skeleton(spec, into)
        spec.save(into)
        generate(spec, PassContext(project_dir=into), OfflineLLM(), log=lambda _: None)
        return {
            str(p.relative_to(into)): p.read_text()
            for p in sorted(into.rglob("*"))
            if p.is_file() and p.suffix in {".py", ".html"}
        }

    plain = tree(plain_spec(), tmp_path / "plain")
    themed = tree(themed_spec(), tmp_path / "themed")
    assert plain == themed


def test_the_theme_costs_no_archetype_baseline():
    """The other half of the same claim, one level up: a theme is not a shape,
    so it adds nothing to the registry. If this ever fails, someone has written
    `archetypes/cats.py` and the axes have collapsed into one."""
    from protopilot import archetypes

    assert set(archetypes.names()) == {"crud", "turn-based-game"}
