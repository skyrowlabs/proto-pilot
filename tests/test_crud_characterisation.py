"""What an offline CRUD generation produced before archetypes existed.

Phase 2 of docs/TODO/archetypes-and-theme.md extracts today's behaviour into
`archetypes/crud.py` and makes `baseline.py` derive its pages from
`spec.screens` rather than re-deriving a CRUD set from `spec.entities`. If that
extraction is faithful, every byte of the output is unchanged; if it is not,
this is the one phase where finding out is cheap.

So this is a **characterisation test**, not a specification. It asserts nothing
about whether the output is *good* -- only that it is the same. The golden
manifest was generated from the code as it stood at `1403f37`, before any of
the extraction was written, which is the only ordering that makes it evidence.

Two files are normalised before hashing. `compose.yml` and the `Dockerfile`
embed the target's absolute path and a hash of it (the compose project name),
so their bytes legitimately differ per run and per machine. Normalising is
narrower than skipping them: the rest of those files is still covered.

When this test fails after a deliberate change to generated output, regenerate
with:

    PROTOPILOT_REGOLD=1 python -m pytest tests/test_crud_characterisation.py

and read the diff in the manifest before committing it. A golden file updated
without reading the diff is a golden file that asserts nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from protopilot.build import generate
from protopilot.llm import OfflineLLM
from protopilot.passes import PassContext
from protopilot.render import project_name, render_skeleton

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

GOLDEN = Path(__file__).resolve().parent / "golden" / "crud_offline_manifest.json"

SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def _normalise(text: str, target: Path, project: str) -> str:
    """Remove the two things that legitimately differ per run.

    The absolute target path and the compose project name (which is a hash of
    that path) are stamped into `compose.yml` and the `Dockerfile` as Docker
    labels. Everything else in those files is fixed.
    """
    return text.replace(str(target.resolve()), "<TARGET>").replace(project, "<PROJECT>")


def manifest(tree: Path, project: str) -> dict[str, str]:
    """relative path -> sha256 of its normalised contents."""
    out: dict[str, str] = {}
    for path in sorted(tree.rglob("*")):
        if not path.is_file() or SKIP_PARTS & set(path.relative_to(tree).parts):
            continue
        try:
            body = _normalise(path.read_text(encoding="utf-8"), tree, project)
        except UnicodeDecodeError:
            body = path.read_bytes().hex()
        out[str(path.relative_to(tree))] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return out


@pytest.fixture()
def generated(spec, tmp_path) -> dict[str, str]:
    render_skeleton(spec, tmp_path)
    spec.save(tmp_path)
    generate(spec, PassContext(project_dir=tmp_path), OfflineLLM(), log=lambda _: None)
    return manifest(tmp_path, project_name(spec, tmp_path))


def test_offline_crud_generation_is_unchanged(generated):
    if os.environ.get("PROTOPILOT_REGOLD"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
        pytest.skip("regenerated the golden manifest — read the diff before committing")

    assert GOLDEN.exists(), f"no golden manifest at {GOLDEN}; run with PROTOPILOT_REGOLD=1"
    golden = json.loads(GOLDEN.read_text())

    added = sorted(set(generated) - set(golden))
    removed = sorted(set(golden) - set(generated))
    changed = sorted(p for p in set(golden) & set(generated) if golden[p] != generated[p])

    assert not removed, f"files that used to be generated and no longer are: {removed}"
    assert not added, f"files that are now generated and were not before: {added}"
    assert not changed, f"files whose contents changed: {changed}"


def test_the_golden_manifest_covers_the_files_that_matter(generated):
    """A manifest that silently stopped covering the generated half would pass
    forever. These are the five paths the model is allowed to write."""
    for path in (
        "app/models.py",
        "app/routes.py",
        "app/seed.py",
        "tests/test_smoke.py",
        "app/templates/trips_list.html",
    ):
        assert path in generated, f"{path} is missing from the generation being characterised"
