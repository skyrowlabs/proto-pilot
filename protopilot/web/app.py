"""A small FastAPI front end over `proto new`.

Every route here is a thin wrapper over something the CLI already does. The
CLI stays the reference implementation; this exists so a demo does not have to
be a terminal. A plan from `proto plan` is listed read-only: it is made, and
acted on, in a terminal.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from protopilot import build as builder
from protopilot import generation, registry, targets
from protopilot.build import is_test_path
from protopilot.jobs import STORE
from protopilot.llm import build_llm
from protopilot.passes import PassContext, clarify
from protopilot.runner import SubprocessRunner, docker_available
from protopilot.spec import Spec

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def archetypes_default() -> str:
    from protopilot import archetypes

    return archetypes.DEFAULT


#: The medium this front end generates in, pinned rather than defaulted.
#:
#: It used to take `targets.DEFAULT`, with the reason "the web front end has no
#: target picker yet" -- a **workaround**, and the flip in Phase 6 of
#: `docs/implementations/spec/terminal-target.md` falsified it. The durable reason is the one
#: that survives: what this front end hands back is a link you click, and a
#: terminal app has no link. `job.url` would be a URL to nothing.
#:
#: So this is not "the default, copied". It is a constraint of the medium the
#: front end is itself built in, and it stays `web` until somebody builds the
#: half of the UI that tells a browser user how to run a thing that is not in a
#: browser. `proto new --target web` is the same generation from a shell.
TARGET = "web"


def run_generation(
    job,
    workspace: Path,
    backend: str | None = None,
    demo: bool = True,
    attempts: int = 3,
    verifier_factory=None,
) -> None:
    """One generation, in this front end's medium.

    The sequence itself lives in `protopilot/generation.py`, so that a front
    end which is not a web server can drive it without importing FastAPI. What
    stays here is the one thing that is genuinely this front end's: the target
    pin, and the reason for it directly above.

    Kept as a function rather than an alias so `TARGET` is applied at call time.
    A module-level `run_generation = partial(..., target=TARGET)` would bind the
    pin at import and silently ignore a test that sets `app.TARGET` — which the
    suite does, to assert the pin is real.
    """
    generation.run_generation(
        job,
        workspace,
        target=TARGET,
        backend=backend,
        demo=demo,
        attempts=attempts,
        verifier_factory=verifier_factory,
    )


def run_clarify(job, backend: str | None = None) -> None:
    """Classify the idea and assemble the questions. One call, before anything
    is generated.

    The model is asked only for what it can see and we cannot: the shape, the
    theme, and up to two questions specific to this idea. The archetype's own
    fixed questions are merged in here, from the registry, so no tokens are
    spent asking it to repeat what we already wrote down.
    """
    from protopilot import archetypes

    llm = build_llm(backend=backend)
    if llm.offline:
        # The baseline cannot read an idea, so it cannot classify one either.
        # It still gets the default archetype's questions: those are ours and
        # need no model.
        chosen = archetypes.DEFAULT
        job.result = {
            "archetype": chosen,
            "choices": archetypes.names(),
            "theme": {},
            "heads_up": "",
            "fixed": clarify.fixed_questions(chosen),
            "questions": [],
        }
        return

    system, user = clarify.build(job.idea, job.direction)
    result = llm.structured(system=system, user=user, schema=clarify.schema(), label=clarify.NAME)
    chosen = clarify.chosen_archetype(result)
    result["archetype"] = chosen
    result["fixed"] = clarify.fixed_questions(chosen)
    result["choices"] = archetypes.names()
    job.result = result


def run_amend(
    job,
    project_dir: Path,
    change: str,
    backend: str | None = None,
    demo: bool = True,
    attempts: int = 3,
    verifier_factory=None,
) -> None:
    """Apply a change to an existing prototype. The CLI's `add`, over HTTP."""
    import subprocess

    llm = build_llm(backend=backend)
    log = job.log
    if llm.offline:
        raise RuntimeError("amending needs the model; the baseline cannot read a change")

    target = Path(project_dir)
    spec = Spec.load(target)

    # Same reasoning as the CLI: a change can retype a column and there are no
    # migrations, so the old volume goes rather than silently disagreeing.
    subprocess.call(["docker", "compose", "down", "-v"], cwd=str(target))  # noqa: S603

    log("amending spec...")
    updated = builder.amend_spec(spec, change, llm)
    log(updated.summary())
    updated.save(target)

    ctx = PassContext(project_dir=target, change=change)
    builder.generate(updated, ctx, llm, log=log, hide_tests=demo, emit=job.event)

    log("verify...")
    make_verifier = verifier_factory or (
        lambda: targets.for_spec(updated).verifier(target, updated, SubprocessRunner())
    )
    outcome = builder.drive_to_green(updated, ctx, llm, make_verifier(), attempts=attempts, log=log, emit=job.event)
    job.project_dir = str(target)
    job.port = updated.port
    job.url = f"http://localhost:{updated.port}"
    if not outcome.ok:
        stage = outcome.result.stage if outcome.result else "unknown"
        log(f"red at {stage}; the tree is at {target}")


def _plan_summary(root: Path) -> str:
    """What the plan says it is, or why it cannot say: a page must not 500 on a hand-edited plan.json."""
    from protopilot.plan.model import Plan

    try:
        return Plan.load(root).summary()
    except (OSError, ValueError) as exc:
        return f"plan.json cannot be read: {exc}"


def create_app(workspace: Path, backend: str | None = None, demo: bool = True) -> FastAPI:
    app = FastAPI(title="proto-pilot")
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    def _generate(job) -> None:
        run_generation(job, workspace, backend=backend, demo=demo)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        # `load`, never `prune`: this used to prune on every page view, so
        # merely opening the front end deleted every entry whose directory
        # had gone. Same trap `proto ls` had, one refresh away instead of
        # one command away.
        ok, why = docker_available(SubprocessRunner())
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {"projects": registry.load(), "jobs": STORE.all(), "docker_ok": ok, "docker_why": why, "demo": demo},
        )

    @app.post("/clarify")
    def start_clarify(idea: str = Form(...), direction: str = Form("")):
        job = STORE.create(idea.strip(), direction.strip())
        STORE.run(job, lambda j: run_clarify(j, backend=backend))
        return RedirectResponse(f"/clarify/{job.id}", status_code=303)

    @app.get("/clarify/{job_id}", response_class=HTMLResponse)
    def clarify_page(request: Request, job_id: str, archetype: str = ""):
        job = STORE.get(job_id)
        if job is None:
            return RedirectResponse("/", status_code=303)

        # Overruling the classifier is a GET with no model call: the fixed
        # questions come from the registry, so switching shape re-renders from
        # what this build already knows rather than asking again.
        selected = job.result.get("archetype", "")
        if archetype and archetype in job.result.get("choices", []):
            selected = archetype
            job.result["fixed"] = clarify.fixed_questions(selected)
        return TEMPLATES.TemplateResponse(request, "clarify.html", {"job": job, "demo": demo, "selected": selected})

    @app.post("/generate")
    async def generate(request: Request):
        form = await request.form()
        idea = str(form.get("idea", "")).strip()
        direction = str(form.get("direction", "")).strip()
        # Answers arrive as answer::<question text>; folding them into
        # `direction` means they reach every pass with no new plumbing.
        # Keyed by question ID now, not by question text: the id is what makes
        # an answer addressable by the pass that eventually reads it.
        answers = {key.split("::", 1)[1]: str(value) for key, value in form.items() if key.startswith("answer::")}
        chosen = str(form.get("archetype") or "").strip() or archetypes_default()
        typed, prose = clarify.split_answers(chosen, answers)
        direction = clarify.merge_direction(direction, prose)
        job = STORE.create(idea, direction)
        job.archetype = chosen
        job.answers = typed
        job.theme = {k: str(form.get(f"theme::{k}", "")).strip() for k in ("palette", "motif", "tone", "subject")}
        STORE.run(job, _generate)
        return RedirectResponse(f"/jobs/{job.id}", status_code=303)

    @app.post("/projects/{slug}/amend")
    def amend(slug: str, change: str = Form(...)):
        entry = next((e for e in registry.load() if e.slug == slug), None)
        if entry is None:
            return RedirectResponse("/", status_code=303)
        if registry.tree_kind(Path(entry.path)) != registry.APP:
            return RedirectResponse(f"/projects/{slug}", status_code=303)
        job = STORE.create(f"[change] {change.strip()}", "")
        STORE.run(
            job,
            lambda j: run_amend(j, Path(entry.path), change.strip(), backend=backend, demo=demo),
        )
        return RedirectResponse(f"/jobs/{job.id}", status_code=303)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_page(request: Request, job_id: str):
        job = STORE.get(job_id)
        if job is None:
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(request, "job.html", {"job": job, "demo": demo})

    # Distinct prefix, not a suffix: `/jobs/{job_id}.json` is matched by the
    # `/jobs/{job_id}` route first, with the id silently becoming "xxx.json".
    @app.get("/api/jobs/{job_id}")
    def job_json(job_id: str):
        job = STORE.get(job_id)
        return JSONResponse(job.snapshot() if job else {"status": "missing"})

    @app.get("/projects/{slug}", response_class=HTMLResponse)
    def project_page(request: Request, slug: str, tests: int = 0):
        entry = next((e for e in registry.load() if e.slug == slug), None)
        if entry is None:
            return RedirectResponse("/", status_code=303)
        root = Path(entry.path)
        kind = registry.tree_kind(root)
        if kind is None:
            return RedirectResponse("/", status_code=303)  # gone, or never ours: nothing to show
        files = sorted(
            p.relative_to(root)
            for p in root.rglob("*")
            if p.is_file() and not {"__pycache__", ".git", ".pytest_cache"} & set(p.parts)
        )
        if kind != registry.APP:
            return TEMPLATES.TemplateResponse(
                request,
                "plan.html",
                {"entry": entry, "files": files, "summary": _plan_summary(root), "demo": demo},
            )
        show_tests = bool(tests) or not demo
        hidden = sum(1 for f in files if is_test_path(f))
        if not show_tests:
            files = [f for f in files if not is_test_path(f)]
        return TEMPLATES.TemplateResponse(
            request,
            "project.html",
            {
                "entry": entry,
                "files": files,
                "show_tests": show_tests,
                "hidden": hidden,
                "spec": Spec.load(root).summary(),
                "demo": demo,
            },
        )

    def _compose(entry, *args: str) -> int:
        return subprocess.call(["docker", "compose", *args], cwd=entry.path)  # noqa: S603

    @app.post("/projects/{slug}/{action}")
    def project_action(slug: str, action: str):
        entry = next((e for e in registry.load() if e.slug == slug), None)
        if entry is None:
            return RedirectResponse("/", status_code=303)
        # The tree, never the entry, says what this is: an index can be stale or hand-edited.
        kind = registry.tree_kind(Path(entry.path))
        if kind == registry.PLAN:
            # Read-only here: a plan has no stack, and is deleted with `proto rm`.
            return RedirectResponse(f"/projects/{slug}", status_code=303)
        if kind is None and action in ("up", "down", "purge"):
            return RedirectResponse("/", status_code=303)  # nothing of ours is there to run
        if action == "up":
            _compose(entry, "up", "-d", "--build")
        elif action == "down":
            _compose(entry, "down")  # data kept
        elif action == "purge":
            _compose(entry, "down", "-v")  # data dropped
        elif action == "forget":
            # Leaves the tree on disk; just stops listing it.
            registry.forget(Path(entry.path))
            return RedirectResponse("/", status_code=303)
        elif action == "delete":
            try:
                registry.delete(Path(entry.path))
            except registry.NotAProject:
                # Guarded in registry.delete; a bad slug must not remove a
                # directory that was never ours.
                registry.forget(Path(entry.path))
            return RedirectResponse("/", status_code=303)
        return RedirectResponse(f"/projects/{slug}", status_code=303)

    return app
