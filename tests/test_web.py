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

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


GREEN = VerifyResult(ok=True, stage="tests", summary="green")


def green_verifier():
    return FakeVerifier([GREEN])


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


def test_generation_produces_a_tree_and_registers_it(tmp_path):
    from protopilot import registry

    job = JobStore().create("track camping gear across trips", "make it a checklist")
    run_generation(job, tmp_path, backend="offline", verifier_factory=green_verifier)

    root = tmp_path / job.project_dir.rsplit("/", 1)[-1]
    assert (root / "app" / "models.py").exists()
    assert (root / "app" / "routes.py").exists()
    assert (root / "tests" / "test_smoke.py").exists()
    assert job.url.startswith("http://localhost:")
    assert [e.slug for e in registry.load()] == [root.name]


def test_demo_mode_hides_tests_from_the_log_but_still_writes_them(tmp_path):
    job = JobStore().create("track camping gear across trips")
    run_generation(
        job,
        tmp_path,
        backend="offline",
        demo=True,
        verifier_factory=green_verifier,
    )
    root = tmp_path / job.project_dir.rsplit("/", 1)[-1]
    # Generated regardless -- the routes pass is handed this file as its target.
    assert (root / "tests" / "test_smoke.py").exists()
    assert not any("test_smoke.py" in line for line in job.lines)


def test_without_demo_the_test_file_is_named_in_the_log(tmp_path):
    job = JobStore().create("track camping gear across trips")
    run_generation(
        job,
        tmp_path,
        backend="offline",
        demo=False,
        verifier_factory=green_verifier,
    )
    assert any("test_smoke.py" in line for line in job.lines)


# ── the journey: classify, overrule, answer, theme ───────────────────────
#
# The front end is a second CALLER of the pipeline, never a second
# implementation — so what these check is that what the journey collects
# actually reaches the spec, in the form that has a contract.


def _client(tmp_path):
    from fastapi.testclient import TestClient

    from protopilot.web.app import create_app

    return TestClient(create_app(tmp_path / "workspace", backend="offline"))


def _start_clarify(client) -> str:
    """POST an idea and wait for the background job to actually finish.

    `JobStore.run` works on a thread, so the redirect comes back before there
    is anything to render. Reading the page immediately is a race that passes
    most of the time and fails in a full suite run -- which is worse than a
    test that fails always, because it teaches people to re-run rather than
    to look.
    """
    import time

    from protopilot.jobs import STORE

    started = client.post("/clarify", data={"idea": "kitten chess", "direction": ""}, follow_redirects=False)
    job_id = started.headers["location"].rsplit("/", 1)[-1]

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = STORE.get(job_id)
        if job is not None and job.status not in ("pending", "running"):
            return job_id
        time.sleep(0.01)
    raise AssertionError(f"clarify job {job_id} never finished")


def test_the_offline_backend_still_gets_the_default_archetypes_questions(tmp_path):
    """The baseline cannot read an idea, so it cannot classify one — but the
    fixed questions are ours and need no model."""
    from protopilot import archetypes
    from protopilot.web.app import run_clarify

    job = JobStore().create("track camping gear", "")
    run_clarify(job, backend="offline")

    assert job.result["archetype"] == archetypes.DEFAULT
    assert [q["id"] for q in job.result["fixed"]] == [q["id"] for q in archetypes.get(archetypes.DEFAULT).QUESTIONS]
    assert job.result["questions"] == [], "the baseline must not invent questions"


def test_the_clarify_page_lets_you_overrule_the_classifier_without_a_model_call(tmp_path):
    """Switching shape re-renders from the registry. It is a GET on purpose:
    the fixed questions are already in this build, so correcting the highest
    leverage decision on the page must not cost a request."""
    client = _client(tmp_path)
    job_id = _start_clarify(client)

    page = client.get(f"/clarify/{job_id}?archetype=crud")

    assert page.status_code == 200
    assert 'name="archetype" value="crud"' in page.text


def test_an_unknown_archetype_in_the_query_is_ignored_rather_than_honoured(tmp_path):
    """It arrives in a URL anyone can edit, so it degrades rather than raises."""
    client = _client(tmp_path)
    job_id = _start_clarify(client)

    page = client.get(f"/clarify/{job_id}?archetype=simulator")

    assert page.status_code == 200
    assert 'value="simulator"' not in page.text


def test_what_the_journey_collects_reaches_the_spec(tmp_path):
    """The end of the plumbing: a typed answer, a themed look and an explicit
    archetype all arrive on spec.json rather than being flattened into prose."""
    from pathlib import Path

    from protopilot.passes import clarify
    from protopilot.spec import Spec
    from protopilot.web.app import run_generation

    known = sorted(clarify.fixed_ids("crud"))[0]
    job = JobStore().create("track camping gear", "")
    job.archetype = "crud"
    job.answers = {known: "gigs"}
    job.theme = {"subject": "cats", "palette": "", "motif": "", "tone": "playful"}

    run_generation(job, tmp_path, backend="offline", verifier_factory=green_verifier)

    spec = Spec.load(Path(job.project_dir))
    assert spec.archetype == "crud"
    assert spec.answers == {known: "gigs"}
    assert spec.theme is not None and spec.theme.subject == "cats" and spec.theme.tone == "playful"


def test_an_all_blank_theme_is_stored_as_none_rather_than_an_empty_shell(tmp_path):
    """`spec.summary()` decides whether to show the theme line, and an empty
    Theme object is not the same as no theme at the review checkpoint."""
    from pathlib import Path

    from protopilot.spec import Spec
    from protopilot.web.app import run_generation

    job = JobStore().create("track camping gear", "")
    job.theme = {"subject": "", "palette": "", "motif": "", "tone": ""}

    run_generation(job, tmp_path, backend="offline", verifier_factory=green_verifier)

    assert Spec.load(Path(job.project_dir)).theme is None
