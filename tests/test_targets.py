"""The `target` axis: registry, round trip, matrix, and what it took over.

Phase 2 of `docs/TODO/terminal-target.md`. The axis mirrors `archetype`, so
most of what is asserted here has a twin in `tests/test_archetypes.py` — the
interesting tests are the four that do not:

- the **round trip**, because the whole value of `Spec.target`'s default is
  that a `spec.json` written before this axis existed still loads and still
  means `web`;
- the **ownership** checks, because the four things a target owns were moved
  out of `render.py`, `build.py` and `files.py` rather than copied, and a copy
  left behind would be a second definition that silently wins somewhere;
- the **matrix**, because a hole discovered at verify time is the tool lying
  about its own coverage;
- the **two defaults**, which are equal today, are not the same decision, and
  are the single most likely thing to be collapsed by somebody tidying up.
"""

from __future__ import annotations

import json

import pytest

from protopilot import archetypes
from protopilot import build as builder
from protopilot import targets
from protopilot.llm import OfflineLLM
from protopilot.spec import Spec
from tests.fakes import FakeLLM

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


# ── the registry ─────────────────────────────────────────────────────────


def test_the_web_target_is_installed():
    assert "web" in targets.names()
    assert targets.get("web").NAME == "web"


def test_discovery_is_by_module_presence():
    """Keyed by the module's declared NAME, not by its filename — the string in
    every `spec.json` is the one the module declares, so a file rename must not
    orphan the specs that named it."""
    for name, module in targets.all().items():
        assert module.NAME == name


def test_every_target_declares_the_whole_contract():
    """The five constants and the one function `targets/__init__.py` documents.

    Recomputed over whatever is installed rather than asserted about `web`, so
    a second target added later is enrolled by existing — the same reason the
    registry has no list to update.
    """
    for name, module in targets.all().items():
        for attr in (
            "NAME",
            "LABEL",
            "SKELETON_DIR",
            "CODE_PASSES",
            "REPAIR",
            "WRITABLE",
            "PROTECTED",
            "ARCHETYPES",
            # What the CLI has to know about the medium, and could not derive.
            # Each of these was a sentence hardcoded somewhere that turned out
            # to be true only of the web target: a port in the review
            # checkpoint, a URL in the hand-back line, `make up`, "Container
            # logs", a `docker compose` block in the RUNBOOK.
            "USES_PORT",
            "HANDOFF",
            "RUN_HINT",
            "LOGS_LABEL",
            "MANUAL",
        ):
            assert hasattr(module, attr), f"target {name!r} does not declare {attr}"
        assert callable(module.verifier), f"target {name!r} has no verifier()"
        assert callable(module.preflight), f"target {name!r} has no preflight()"
        assert module.SKELETON_DIR.is_dir(), f"target {name!r} points at a skeleton that is not there"
        assert module.CODE_PASSES, f"target {name!r} has no passes"


def test_an_unknown_target_raises_and_says_what_exists():
    with pytest.raises(targets.MissingTarget) as caught:
        targets.get("hologram")
    assert "hologram" in str(caught.value)
    assert "web" in str(caught.value)


def test_an_unknown_target_does_not_fall_back():
    """The one place this axis deliberately differs from `archetype`.

    `archetypes.for_spec` returns `crud` for a name it does not have, because a
    tree of the wrong shape still builds. The target picks the skeleton, the
    passes and the verifier, so the same fallback would hand somebody a FastAPI
    app because they asked for a terminal one — which is exactly the "generated
    into something broken" the plan refuses.
    """
    spec = Spec(name="X", slug="x", purpose="y", target="hologram")
    with pytest.raises(targets.MissingTarget):
        targets.for_spec(spec)
    # ...where the archetype axis, on the same spec shape, does not raise:
    assert archetypes.for_spec(Spec(name="X", slug="x", purpose="y", archetype="nonsense")).NAME == archetypes.DEFAULT


# ── the two defaults, which are not the same decision ────────────────────


def test_the_field_default_is_web():
    """What a `spec.json` written before this axis existed MEANT. It stays
    `web` forever; nothing about a later CLI default may touch it."""
    assert Spec.model_fields["target"].default == "web"


def test_a_spec_with_no_target_key_loads_as_web(tmp_path):
    """The compatibility guarantee, exercised on real JSON with the key absent
    rather than on a constructor default — a `spec.json` on disk is what the
    promise is about."""
    payload = {"name": "Gear List", "slug": "gearlist", "purpose": "Track gear.", "port": 8099}
    assert "target" not in payload
    path = tmp_path / ".protopilot" / "spec.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload))

    loaded = Spec.load(tmp_path)
    assert loaded.target == "web"
    assert targets.for_spec(loaded).NAME == "web"


def test_a_saved_spec_keeps_its_target(tmp_path, spec):
    spec.target = "web"
    spec.save(tmp_path)
    assert json.loads((tmp_path / ".protopilot" / "spec.json").read_text())["target"] == "web"
    assert Spec.load(tmp_path).target == "web"


def test_the_cli_default_and_the_field_default_are_separate_constants():
    """They moved apart on 2026-09-04 and that is the whole of Phase 6.

    `targets.DEFAULT` is now `tui` — what a NEW spec is born with. The field
    default is still `web` — what a spec written before the axis existed
    MEANT. Collapsing them is a one-line tidy-up that would silently rewrite
    the meaning of every old `spec.json` on disk, and until the flip nothing
    else would have gone red, because the two constants held the same string.

    Pinned to the literals on purpose. A test written as `DEFAULT != field
    default` would pass again the day somebody flipped the wrong one back.
    """
    assert targets.DEFAULT == "tui"
    assert targets.DEFAULT in targets.names()
    assert Spec.model_fields["target"].default == "web"


def test_an_old_spec_still_generates_the_web_app_it_always_did(tmp_path):
    """The compatibility half of the flip, end to end rather than by field.

    A `spec.json` with no `target` key is loaded, and the tree it renders is
    the web skeleton — not the new default. This is the guarantee the field
    default exists for, and after the flip it is the only thing standing
    between an old prototype and a regeneration in the wrong medium.
    """
    from protopilot.render import render_skeleton

    payload = {"name": "Gear List", "slug": "gearlist", "purpose": "Track gear.", "port": 8099}
    path = tmp_path / "old" / ".protopilot" / "spec.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload))

    loaded = Spec.load(tmp_path / "old")
    render_skeleton(loaded, tmp_path / "tree")

    assert (tmp_path / "tree" / "compose.yml").exists(), "an old spec rendered something other than the web tree"
    assert not (tmp_path / "tree" / "app" / "screens.py").exists()


# ── what a target owns, and that it owns it alone ────────────────────────


def test_the_skeleton_directory_moved_off_render():
    """`render.SKELETON_DIR` could only ever name one tree. It was moved, not
    copied — a leftover would be the definition `render_skeleton` reached for
    when nobody was looking."""
    import protopilot.render as render

    assert not hasattr(render, "SKELETON_DIR")


def test_the_pass_tuple_moved_off_build():
    import protopilot.build as build

    assert not hasattr(build, "CODE_PASSES")


def test_the_write_allowlist_moved_off_files():
    import protopilot.files as files

    assert not hasattr(files, "WRITABLE")
    assert not hasattr(files, "PROTECTED")


def render_relative(spec, tmp_path) -> set[str]:
    from protopilot.render import render_skeleton

    return {str(rel) for rel in render_skeleton(spec, tmp_path)}


def test_render_skeleton_follows_the_spec_target(spec, tmp_path):
    """Not that it renders — `test_render.py` covers that — but that the tree it
    renders is the one `spec.target` names."""
    written = render_relative(spec, tmp_path)
    expected = {
        str(p.relative_to(targets.get(spec.target).SKELETON_DIR))
        for p in targets.get(spec.target).SKELETON_DIR.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert written == expected


def test_the_write_guard_uses_the_running_targets_list(spec, tmp_path):
    """The seam that matters: `run_pass` asks the spec's target, so the guard
    cannot be a step behind the tree it is guarding."""
    from protopilot.files import UnsafePath
    from protopilot.passes import PassContext
    from protopilot.passes import models as schema_pass
    from protopilot.passes import run_pass

    # A terminal path, returned by a pass running against a web spec.
    rogue = FakeLLM([{"files": [{"path": "app/screens.py", "content": "x = 1\n"}], "notes": ""}])
    with pytest.raises(UnsafePath) as caught:
        run_pass(schema_pass, spec, PassContext(project_dir=tmp_path), rogue)
    # On the web target `app/screens.py` is not writable, and the refusal names
    # the list it was checked against rather than only the path that failed.
    assert "app/models.py" in str(caught.value)
    assert not (tmp_path / "app" / "screens.py").exists()


def test_the_write_guard_is_still_handed_the_targets_protected_list(spec, tmp_path):
    """The half of the same seam that fails **quietly**.

    `files.write_all(...)` defaults `protected` to `()`, so a caller that stops
    passing it does not raise — it silently makes `app/templates/base.html`
    writable, and the only symptom is a prototype whose chrome the model
    rewrote. `run_pass` is the one product caller of that function; this is the
    assertion that it still hands both lists over.
    """
    from protopilot.files import UnsafePath
    from protopilot.passes import PassContext, run_pass
    from protopilot.passes import ui as ui_pass
    from protopilot.render import render_skeleton

    render_skeleton(spec, tmp_path)
    base = tmp_path / "app" / "templates" / "base.html"
    skeleton_chrome = base.read_text()

    # `base.html` matches `app/templates/*.html`, so only PROTECTED refuses it.
    rogue = FakeLLM([{"files": [{"path": "app/templates/base.html", "content": "<h1>mine</h1>"}], "notes": ""}])
    with pytest.raises(UnsafePath) as caught:
        run_pass(ui_pass, spec, PassContext(project_dir=tmp_path), rogue)

    assert "base.html" in str(caught.value) and "skeleton" in str(caught.value)
    assert base.read_text() == skeleton_chrome, "the model rewrote the one template it must never touch"


# ── the matrix ───────────────────────────────────────────────────────────


def test_every_declared_archetype_exists():
    """A stale name in `ARCHETYPES` would refuse a pair that is actually fine,
    and nothing else would notice."""
    installed = set(archetypes.names())
    for name, module in targets.all().items():
        unknown = set(module.ARCHETYPES) - installed
        assert not unknown, f"target {name!r} declares archetypes that are not installed: {sorted(unknown)}"


def test_the_default_target_can_build_every_installed_archetype():
    """The other direction, and the one that catches a new archetype nobody
    wired up. A hole elsewhere in the matrix is a legitimate stated hole; a hole
    in the default target is `proto new` refusing its own classifier's answer."""
    missing = set(archetypes.names()) - set(targets.archetypes_for(targets.DEFAULT))
    assert not missing, f"the {targets.DEFAULT!r} target cannot build: {sorted(missing)}"


def test_an_unsupported_pair_is_refused_by_name():
    with pytest.raises(targets.UnsupportedPair) as caught:
        targets.check_pair("web", "holodeck")
    message = str(caught.value)
    assert "web" in message and "holodeck" in message, "both halves have to be in it, or neither is actionable"
    assert "crud" in message, "and what it CAN build, or the reader has nowhere to go"


def test_the_pair_is_refused_at_intake_before_any_call():
    """Before the model runs, not after — that is the whole point of doing it
    here. The LLM is one that fails the test by being used at all."""

    counting = FakeLLM([])  # any call at all raises "ran out of responses"
    with pytest.raises(targets.UnsupportedPair):
        builder.spec_from_idea("an idea", counting, archetype="holodeck", target="web", port=8080)
    assert counting.calls == [], "a refused pair must not have cost a generation"


def test_an_unknown_target_is_refused_at_intake_too():
    with pytest.raises(targets.MissingTarget):
        builder.spec_from_idea("an idea", OfflineLLM(), archetype="crud", target="hologram", port=8080)


# ── the review checkpoint ────────────────────────────────────────────────


def test_the_handoff_line_never_promises_a_url_without_a_port(spec):
    """One sentence per target, and it is the last thing a user reads.

    It was `http://localhost:{port}` in `cli._finish` for as long as there was
    one medium. A target that does not listen has to say something else, and
    a target that does must still say the URL — so this checks the pairing
    rather than either half.
    """
    for name, module in targets.all().items():
        line = module.HANDOFF.format(name=spec.name, slug=spec.slug, port=spec.port, directory="/tmp/x")
        assert spec.name in line, f"{name}: the hand-back line does not say what was built"
        if not module.USES_PORT:
            assert "localhost" not in line, f"{name} has no port and its hand-back line offers a URL"
        else:
            assert str(spec.port) in line, f"{name} has a port and does not say where to find it"


def test_the_summary_prints_a_port_only_for_a_target_that_has_one(spec):
    """The review checkpoint is the one gate in the tool. A headline reading
    "port 8099" over an app that listens on nothing is the tool being
    confidently wrong at the only moment somebody could object."""
    spec.target = "web"
    assert f"port {spec.port}" in spec.summary()

    spec.target = "tui"
    assert f"port {spec.port}" not in spec.summary()
    assert spec.slug in spec.summary(), "the headline lost the thing it is a headline for"


def test_the_summary_prints_the_target(spec):
    """The only gate in the tool. A person approving a generation has to be able
    to see which KIND of thing it is — a field the summary omits is a field
    nobody reviews."""
    assert "target: web" in spec.summary()
