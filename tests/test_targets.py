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
        for attr in ("NAME", "LABEL", "SKELETON_DIR", "CODE_PASSES", "WRITABLE", "PROTECTED", "ARCHETYPES"):
            assert hasattr(module, attr), f"target {name!r} does not declare {attr}"
        assert callable(module.verifier), f"target {name!r} has no verifier()"
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
    """Equal today, and the day Phase 6 moves one it must not move the other.

    Collapsing them is a one-line tidy-up that silently rewrites the meaning of
    every spec written before the axis existed, and nothing else would go red.
    """
    assert targets.DEFAULT in targets.names()
    assert Spec.model_fields["target"].default == "web"


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


def test_the_summary_prints_the_target(spec):
    """The only gate in the tool. A person approving a generation has to be able
    to see which KIND of thing it is — a field the summary omits is a field
    nobody reviews."""
    assert "target: web" in spec.summary()
