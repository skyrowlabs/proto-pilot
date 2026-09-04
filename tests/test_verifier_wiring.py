"""The verifier factory, and the two defaults that nothing was calling.

`Verifier` itself is covered by `tests/test_verify.py`. What was not covered is
the wiring **around** it: `targets.web.verifier()`, which is the one place the
four constructor arguments are decided, and the two callers that build their
verifier through it when nothing is injected.

That gap is the interesting kind. `tests/test_web.py` passes a
`verifier_factory` into every generation it drives, so the default in
`protopilot/web/app.py` — a one-line lambda — had never run under a test, and
**coverage does not show it**: the line is reported as covered because the
assignment executed, while the body of the lambda never did. A factory that is
only ever reached in production is a factory that fails in production.

Docker is the boundary and the only thing faked here. Everything above it — the
factory, the real `Verifier`, `drive_to_green`, the front end's whole
generation path — is the real code, so a change to any of them is visible here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes import FakeRunner

from protopilot import browser
from protopilot import build as builder
from protopilot import cli
from protopilot.archetypes import crud
from protopilot.llm import OfflineLLM
from protopilot.passes import PassContext
from protopilot.runner import CommandResult
from protopilot.spec import Screen, Spec, checkable_paths
from protopilot.targets import MissingTarget
from protopilot.targets import web as web_target
from protopilot.verify import Verifier

# Host-side: no key, no Docker daemon, no network. Every docker call in this
# file goes to a fake runner, and the one stage that would reach out over HTTP
# is never arrived at -- `verify()` returns at the build stage.
pytestmark = [pytest.mark.unit]


class CwdRunner(FakeRunner):
    """`FakeRunner`, plus the working directory each call was made in.

    Which tree docker is pointed at is half of what the factory decides, and
    the shared fake discards it.
    """

    def __init__(self, responses=None):
        super().__init__(responses)
        self.cwds: list[str] = []

    def run(self, argv, cwd: Path | None = None, timeout: float | None = None) -> CommandResult:
        self.cwds.append(str(cwd))
        return super().run(argv, cwd=cwd, timeout=timeout)


BUILD_FAILED = (["docker", "compose", "up"], (1, "", "no such image: gearlist-app"))


def built(project_dir, spec, runner=None) -> Verifier:
    """The factory's product, typed as the concrete class it actually is.

    `verifier()` is annotated `-> Verifies` on purpose — `drive_to_green` must
    never learn which implementation it got, and Phase 5 of
    `docs/implementations/spec/terminal-target.md` depends on that staying true. These tests
    are the exception: they are about the construction rather than the
    protocol, so the narrowing is deliberate, and it doubles as the assertion
    that today's web target still hands back the Docker verifier.
    """
    made = web_target.verifier(project_dir, spec, runner)
    assert isinstance(made, Verifier)
    return made


@pytest.fixture()
def screened_spec(spec) -> Spec:
    """The fixture spec with the screens a CRUD generation would give it.

    `checkable_paths` is empty for a spec with no screens, which would make the
    browser-stage assertions below vacuously true.
    """
    spec.screens = [Screen(**s) for s in crud.screens(spec)]
    return spec


# ── the factory ──────────────────────────────────────────────────────────


def test_the_factory_runs_docker_in_the_project_directory(spec, tmp_path):
    """`down -v` before `up`, in the tree it was handed. The order is the
    schema guarantee `Verifier.up` documents; the directory is the factory's."""
    runner = CwdRunner()
    built(tmp_path, spec, runner).up()

    compose = [call for call in runner.calls if call[:2] == ["docker", "compose"]]
    assert compose[0][2:5] == ["down", "-v", "--remove-orphans"]
    assert compose[1][2:5] == ["up", "-d", "--build"]
    assert set(runner.cwds) == {str(tmp_path)}


def test_a_build_failure_through_the_factory_reports_the_build_stage(spec, tmp_path):
    """The factory's product driven end to end, on the one path that needs
    neither a daemon nor a socket: `verify()` returns at `build` before it ever
    reaches the health wait."""
    runner = CwdRunner([BUILD_FAILED])
    result = built(tmp_path, spec, runner).verify()

    assert not result.ok
    assert result.stage == "build"
    assert "no such image: gearlist-app" in result.output
    # Nothing downstream of a stack that never started.
    assert not runner.ran("docker", "compose", "exec")


def test_the_factory_carries_the_specs_port_and_screens_to_the_browser(screened_spec, tmp_path, monkeypatch):
    """Two of the four constructor arguments, asserted where they are used.

    The browser stage is the only consumer of `screens=`, and the only place
    the port becomes a URL that is not the health probe, so a factory that
    dropped either would be invisible until a real generation reached it.
    """
    urls: list[str] = []
    fetched: list[list[str]] = []

    def fake_check(base_url: str, paths: list[str], timeout_ms: int = 15000):
        urls.append(base_url)
        fetched.append(list(paths))
        return browser.BrowserResult(ok=True)

    monkeypatch.setattr(browser, "available", lambda: "")
    monkeypatch.setattr(browser, "check", fake_check)

    page_result = built(tmp_path, screened_spec, FakeRunner()).check_pages()
    assert page_result is not None and page_result.ok

    assert urls == [f"http://localhost:{screened_spec.port}"]
    assert fetched == [checkable_paths(screened_spec)]
    assert "/trips" in fetched[0], "the spec's screens never reached the stage that loads them"


def test_the_factory_falls_back_to_a_real_subprocess_runner(spec, tmp_path, monkeypatch):
    """`runner or SubprocessRunner()` is the default both front ends rely on
    when they are not under test. Proven by watching the substitute get used,
    not by looking at the type of the attribute."""
    runner = CwdRunner()
    monkeypatch.setattr(web_target, "SubprocessRunner", lambda: runner)

    built(tmp_path, spec).up()

    assert runner.ran("docker", "compose", "up", "-d", "--build")


def test_the_repair_loop_accepts_what_the_factory_returns(spec, tmp_path):
    """`Verifies` is a Protocol, so nothing checks this at import time.

    `drive_to_green` is the only consumer that matters and it is run here for
    real: the offline baseline cannot repair, so the loop stops after one
    verify and hands the tree back at the stage that was red — which is the
    floor the whole design turns on.
    """
    verifier = web_target.verifier(tmp_path, spec, CwdRunner([BUILD_FAILED]))
    outcome = builder.drive_to_green(
        spec,
        PassContext(project_dir=tmp_path),
        OfflineLLM(),
        verifier,
        attempts=3,
        log=lambda _: None,
    )

    assert not outcome.ok
    assert outcome.result is not None and outcome.result.stage == "build"
    assert outcome.attempts == 1, "a baseline that cannot repair must not burn three attempts"


# ── the CLI's default ────────────────────────────────────────────────────


def test_the_cli_builds_its_verifier_through_the_target(spec, tmp_path, monkeypatch):
    runner = CwdRunner()
    monkeypatch.setattr(cli, "SubprocessRunner", lambda: runner)

    verifier = cli._verifier(tmp_path, spec)
    assert isinstance(verifier, Verifier)
    verifier.up()

    assert runner.ran("docker", "compose", "up", "-d", "--build")
    assert set(runner.cwds) == {str(tmp_path)}


def test_the_cli_verifier_asks_the_registry_rather_than_naming_a_class(tmp_path):
    """The seam Phase 5 needs. If `_verifier` still constructed `Verifier`
    directly this would quietly build a Docker verifier for a terminal spec;
    because it goes through the target, an unknown one is refused by name."""
    unknown = Spec(name="X", slug="x", purpose="y", target="hologram")
    with pytest.raises(MissingTarget) as caught:
        cli._verifier(tmp_path, unknown)
    assert "hologram" in str(caught.value) and "web" in str(caught.value)


# ── the front end's default, which nothing had ever run ──────────────────


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """`run_generation` records every tree it makes. Never in the real one."""
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


def test_the_front_end_verifies_through_the_target_when_nothing_is_injected(tmp_path, monkeypatch):
    """The lambda in `web/app.py` that no test had ever executed.

    Driven the way the browser drives it — offline backend, no
    `verifier_factory` — with docker replaced one layer lower, at the runner.
    So the default factory, the target lookup and the real `Verifier` all run,
    and the generation ends at the same honest floor the CLI has.
    """
    from protopilot.jobs import JobStore
    from protopilot.web import app as web_app

    runner = CwdRunner([BUILD_FAILED])
    monkeypatch.setattr(web_app, "SubprocessRunner", lambda: runner)

    job = JobStore().create("track camping gear across trips")
    web_app.run_generation(job, tmp_path, backend="offline")

    assert runner.ran("docker", "compose", "up", "-d", "--build"), "the default verifier never booted anything"
    assert runner.cwds and set(runner.cwds) == {job.project_dir}
    assert any("red at build" in line for line in job.lines), job.lines


def test_the_front_end_asks_the_target_rather_than_naming_the_class(tmp_path, monkeypatch):
    """The half the docker-level test above cannot see.

    A default that called `Verifier(target, spec.port, ...)` directly would
    behave identically today and would hand a Docker verifier to a terminal
    spec the day a second target exists. So the assertion is that the *target*
    was asked, with the tree and the spec that were generated.
    """
    from fakes import FakeVerifier

    from protopilot.jobs import JobStore
    from protopilot.verify import VerifyResult
    from protopilot.web import app as web_app

    asked: list[tuple[Path, str]] = []

    def recording(project_dir, spec, runner=None):
        asked.append((Path(project_dir), spec.target))
        return FakeVerifier([VerifyResult(ok=True, stage="tests", summary="green")])

    monkeypatch.setattr(web_target, "verifier", recording)

    job = JobStore().create("track camping gear across trips")
    web_app.run_generation(job, tmp_path, backend="offline")

    assert asked == [(Path(job.project_dir), "web")]


def test_the_front_end_is_pinned_to_web_rather_than_following_the_default(tmp_path, monkeypatch):
    """`proto serve` hands back a link you click.

    It used to take `targets.DEFAULT`, with the reason "no target picker yet" —
    a workaround, and the Phase 6 flip falsified it. The durable reason is that
    a terminal app has no URL, so `job.url` would point at nothing. Asserted
    against the constant AND against the tree, because a pin nobody checks is
    a literal waiting to drift.
    """
    from fakes import FakeVerifier

    from protopilot.jobs import JobStore
    from protopilot.verify import VerifyResult
    from protopilot.web import app as web_app

    assert web_app.TARGET == "web"

    job = JobStore().create("track camping gear across trips")
    web_app.run_generation(
        job,
        tmp_path,
        backend="offline",
        verifier_factory=lambda: FakeVerifier([VerifyResult(ok=True, stage="tests", summary="green")]),
    )

    root = Path(job.project_dir)
    assert Spec.load(root).target == "web"
    assert (root / "app" / "routes.py").exists()
    assert job.url.startswith("http://localhost:"), "the front end promised a URL it could not honour"


def test_an_injected_factory_still_wins(tmp_path, monkeypatch):
    """The other half of `verifier_factory or (...)`: when a caller supplies
    one, the default must not run as well. Every other test of the front end
    depends on this being true."""
    from fakes import FakeVerifier

    from protopilot.jobs import JobStore
    from protopilot.verify import VerifyResult
    from protopilot.web import app as web_app

    runner = CwdRunner()
    monkeypatch.setattr(web_app, "SubprocessRunner", lambda: runner)

    job = JobStore().create("track camping gear across trips")
    web_app.run_generation(
        job,
        tmp_path,
        backend="offline",
        verifier_factory=lambda: FakeVerifier([VerifyResult(ok=True, stage="tests", summary="green")]),
    )

    assert not runner.ran("docker", "compose", "up"), "the default verifier ran alongside the injected one"
    assert job.url.endswith(str(Spec.load(Path(job.project_dir)).port))
