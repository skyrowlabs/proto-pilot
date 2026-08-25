"""The web front end's generation path.

This exists because of a real bug: the front end called `intake.run(...)`,
which does not exist, and nothing caught it until a generation was attempted
through the UI. The page-rendering tests all passed, because rendering a page
never touches the pipeline.

So this test drives the actual generation the way the browser does -- offline
backend, faked verifier, no Docker, no API -- and asserts it reaches a tree on
disk. Anything invented about the pipeline's API surface fails here.
"""

from __future__ import annotations

import pytest

from fakes import FakeVerifier

from protopilot.jobs import JobStore
from protopilot.verify import VerifyResult

pytest.importorskip("fastapi")

from protopilot.web.app import run_generation  # noqa: E402


GREEN = VerifyResult(ok=True, stage="tests", summary="green")


def green_verifier():
    return FakeVerifier([GREEN])


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


def test_generation_produces_a_tree_and_registers_it(tmp_path):
    from protopilot import registry

    job = JobStore().create("track camping gear across trips", "make it a checklist")
    run_generation(
        job, tmp_path, backend="offline", verifier_factory=green_verifier
    )

    root = tmp_path / job.project_dir.rsplit("/", 1)[-1]
    assert (root / "app" / "models.py").exists()
    assert (root / "app" / "routes.py").exists()
    assert (root / "tests" / "test_smoke.py").exists()
    assert job.url.startswith("http://localhost:")
    assert [e.slug for e in registry.load()] == [root.name]


def test_demo_mode_hides_tests_from_the_log_but_still_writes_them(tmp_path):
    job = JobStore().create("track camping gear across trips")
    run_generation(
        job, tmp_path, backend="offline", demo=True,
        verifier_factory=green_verifier,
    )
    root = tmp_path / job.project_dir.rsplit("/", 1)[-1]
    # Generated regardless -- the routes pass is handed this file as its target.
    assert (root / "tests" / "test_smoke.py").exists()
    assert not any("test_smoke.py" in line for line in job.lines)


def test_without_demo_the_test_file_is_named_in_the_log(tmp_path):
    job = JobStore().create("track camping gear across trips")
    run_generation(
        job, tmp_path, backend="offline", demo=False,
        verifier_factory=green_verifier,
    )
    assert any("test_smoke.py" in line for line in job.lines)
