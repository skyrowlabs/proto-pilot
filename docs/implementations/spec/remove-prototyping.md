---
title: Remove Prototyping
slug: remove-prototyping
priority: high
category: spec
agent_value: 2
completed: 2026-11-11
updated: 2026-11-11
tags: [cli, plan, registry, tests, ci, docs]
summary: Delete everything that generates, runs or verifies an app, both front ends included, so that the surviving CLI is plan, dream, ls, rm, prune and doctor.
---

# Remove Prototyping

> **Status**: ✅ Complete — 2026-11-11
> **Priority**: High — the decision of 2026-11-11, and [living-plans](../../TODO/living-plans.md) waits on it
> **Updated**: 2026-11-11

## Problem

Planning has been the product since 2026-11-06, and
[plans-first](../../ideas/plans-first.md) decision 2 kept prototyping "tabled, not
deleted". On 2026-11-11 it was decided further: **remove the physical prototyping
layer outright and feature the written plan.** Decision 2 is superseded by this
plan.

What the tabled layer costs today, measured on `develop` at `f0e88ef`:

- 94 tracked files under `protopilot/` and `skeleton/` that only exist to
  generate, run or verify an app, against 29 that planning uses.
- 31 test files that test only that layer, three golden manifests, and parts of
  11 more test files.
- Two core dependencies (`sqlalchemy`, `textual`) that every user of
  `proto plan` installs and no plan code imports, plus seven dev pins and two
  extras.
- 14 of the CLI's 20 commands, and a kind guard on every one of them so that it
  can refuse a plan tree.

The whole removal was rehearsed in a throwaway clone before this was written:
about 130 paths and 18,500 lines deleted, and the unit suite then stood at
1,991 passed with every failure listed in Phase 3. Nothing in that list is a surprise gate.

## Approach

Five commits on `feat/remove-prototyping`, each green under `./pp check lint`,
`./pp check docs` and `./pp test unit`, then one PR to `develop`.

The order is forced by two gates, and it is the reverse of the obvious one:

- `tests/test_docs_name_real_paths.py` and `tests/test_docs_name_live_code.py`
  fail a reference doc that names a path or a callable the tree no longer has.
  Nothing fails a doc for *not* naming code that still exists. **So the docs
  stop describing the layer one commit before the layer goes** (Phase 2), and
  for that one commit on the branch the README is ahead of the code.
- A test file cannot outlive the module it imports, and `pip install -e .`
  fails when `[tool.setuptools] packages` names a directory that is gone. **So
  the code, its tests and the packaging lines go in one commit** (Phase 3). It
  cannot be split into smaller green commits and the plan does not try.

**What survives:** `proto plan`, `proto dream` (`round`, `promote`, `drop`),
`proto ls`, `proto rm`, `proto prune`, `proto doctor`, `proto --version`; the
whole of `protopilot/plan/`; `llm.py` with all three backends; `jobs.py`;
`registry.py`; `runner.py`; and the event fold, moved to `protopilot/progress.py`.

**Three things the brief for this plan did not know**, found by reading imports:

1. `protopilot/runner.py` stays. `ClaudeCodeLLM` builds a `SubprocessRunner`
   (`llm.py:366`). Only `docker_available` leaves it.
2. `protopilot/console/progress.py` has a surviving consumer. Five plan test
   files fold `job.events` through it (15 assertions). It holds no Textual
   import, so it moves rather than dies.
3. `[tool.setuptools] packages` has never listed `protopilot.plan.passes` (nor
   `protopilot.console`). An editable install hides that; a wheel would ship
   `proto plan` without its passes. Phase 3 writes the list correctly.

## Phase 0 — Mark the last commit that holds both layers

- [x] Confirm `develop` is clean and pushed; record its SHA in the PR body as
      `proto-pilot@<sha>`
- [x] `git tag -a prototyping-final -m "last commit with proto new, both targets and both front ends" <sha>`.
      The name is safe by measurement: `tests/test_version_follows_the_tag.py`
      and `cli/__init__.py` both match `v[0-9]*`, `scripts/docs/release_window.py`
      lists `v*`, and Release Please reads `v` tags only
- [x] The session doing this work is on `feat/remove-prototyping`, cut from that
      SHA. **An implementer subagent must not `git switch` the shared checkout**;
      the orchestrating session creates the branch before delegating
- [x] Put the three items under *For the operator* into the PR body, and raise
      each as a DECISIONS row if this runs inside a sky.boss deck
      (`sb deck decide add`; the tag push is a `--run` row)

## Phase 1 — The plan package owns what it borrowed

A refactor with no behaviour change. Everything deleted in Phase 3 still exists
and still passes after this commit.

- [x] `protopilot/plan/model.py` defines `PLAN_DIR = ".protopilot"` and
      `SLUG_RE` itself and drops `from protopilot.spec import SLUG_RE, SPEC_DIR`.
      The directory name on disk does not change: a plan made before this must
      still load
- [x] `protopilot/plan/ledger.py` and `protopilot/registry.py` take `PLAN_DIR`
      from `protopilot.plan.model`
- [x] `protopilot/spec.py` re-imports both from `protopilot.plan.model` for the
      one commit it has left (`SPEC_DIR = PLAN_DIR`), so there is still one
      definition (Rule 1)
- [x] `VerifyResult` moves into `protopilot/plan/verify.py`; `protopilot/verify.py`
      imports it from there until Phase 3
- [x] `git mv protopilot/console/progress.py protopilot/progress.py`, and
      `git mv tests/test_console_progress.py tests/test_progress.py`
- [x] Repoint the importers: `protopilot/console/app.py:31`, `tests/test_progress.py`,
      and `tests/test_plan_dream_limits.py`, `test_plan_floor.py`,
      `test_plan_model_output.py`, `test_plan_pipeline.py`, `test_plan_repair.py`
- [x] `tests/test_plan_baseline.py:11` and `tests/test_plan_dream_limits.py:47`
      import `SLUG_RE` from `protopilot.plan.model`
- [x] Check: `grep -rnE "protopilot\.(spec|verify|console)\b" protopilot/plan tests/test_plan_*.py tests/test_progress.py`
      prints nothing
- [x] Commit: `refactor(plan): own the constants and result type the plan borrowed`

## Phase 2 — The docs stop describing the layer

Phase 3 turns each of these red if it is skipped. The rehearsal named them:
24 cited paths in `AGENTS.md`, `docs/ARCHITECTURE.md`, `.github/DOCS_INDEX.md`
and `scripts/spikes/README.md`; two callables in `docs/ARCHITECTURE.md`
(`archetypes.brief_for()`, `cli.set_port()`); and `proto new` in a shell block in
`README.md`.

- [x] `docs/ideas/plans-first.md`: decision 2 is marked **superseded 2026-11-11**
      with the new ruling in one paragraph and a link to this plan; decision 3,
      *What this costs* and *What changes when* are brought in line. The
      `prototyping-final` tag is named as where the old layer can be read
- [x] `docs/ideas/README.md`: the plans-first row says prototyping was removed,
      not tabled
- [x] `docs/ideas/sketches-not-scaffolds.md` and `docs/ideas/hosted.md`: one
      status line each, saying the thing they describe left the tree on
      2026-11-11. Their arguments stay; the folder is narrative
- [x] `README.md`: hero alt text; the nav link and the whole *Prototypes come
      later* section go; *Commands* lists the six survivors; *Status* says
      prototyping was removed and names the tag; *Install* and *Testing* lose
      extras, Docker and the browser. Add four lines for somebody upgrading with
      old prototypes on disk (see Phase 3, *Old registries*)
- [x] `AGENTS.md`: *Services* (nothing listens now, so the table goes), *What
      this repo is*, *Naming: two "skeletons"* (delete; one skeleton is left and
      it is skeletor's), *Invariants*, *The offline baseline is the test suite*,
      *Layout*, Rule 15's last sentence, and Rule 16's worked example
      (`containers.py::known_paths` is leaving; pick a live one or drop the
      clause). **Keep** the two-guard paragraph's `llm.ISOLATION` and
      `RESEARCH_ISOLATION` rule as a plan invariant: it is the one that still
      binds
- [x] `docs/ARCHITECTURE.md`: keep *The plan pipeline*, the registry lock
      pattern and whatever of *Decisions* is about planning; delete *What a
      target owns*, *How a prototype is built*, and the web- and terminal-target
      patterns. Rewrite *What This Is*, *Data Flow* and *Components* around the
      plan pipeline. Repoint `AGENTS.md`'s two anchors into it
- [x] `docs/CLI.md`: the *What a plan is to the other verbs* table loses the app
      verbs, `down --all` and `serve`
- [x] `docs/DEVELOPMENT.md`, `docs/README.md`, `.github/DOCS_INDEX.md` (lines
      33–34 route to `protopilot/passes/`), `scripts/spikes/README.md` (cites
      `protopilot/passes/tui/_brief.py`)
- [x] `docs/NOTES.md`: move every open item about `proto new`, a target, the
      console, the web front end, Docker or `gc` to *Resolved* with "removed
      2026-11-11". It is narrative, so no gate asks; this is the reading pass
      Rule 16 says no test can do
- [x] File the two parked designs as dropped. The lifecycle has no dropped
      state, so use the archive with a category that says it:
      `./pp docs file improvement-loop --category dropped --force` and
      `./pp docs file drawing-freedom --category dropped --force`
      (28 and 29 open tasks; `--force` is what the tool provides). Before filing,
      set each `> **Status**:` line to `Dropped 2026-11-11 — never built; the
      layer it extends was removed` so the archive's "completed" heading cannot
      be read as a claim about them
- [x] Repoint what cited them: `docs/ideas/plans-first.md:46-47` and
      `docs/reports/regular/repository-report.md:119,121`. The frozen
      `docs/reports/releases/v0.3.0/repository-report.md:143,145` is never
      edited: add two entries to `scripts/doc_refs_allowlist.yaml` beside the
      existing `../../../TODO/plan-prototypes.md` one, with the same reason
- [x] `docs/implementations/spec/{terminal-target,archetypes-and-theme,proto-console}.md`
      are untouched. Measured: no doc holds a markdown link into `protopilot/`,
      `skeleton/` or `tests/`, and `./pp check docs` was green in the rehearsal
      with the code gone
- [x] `./pp docs index`, then `./pp check docs` and `./pp test unit`. **If a gate
      here demands that a doc name something still live, move that one edit into
      Phase 3's commit and say so in its body** — none was found, but this state
      (docs changed, code not) is the one the rehearsal did not run
- [x] Commits: `docs: describe planning as the whole product`, then
      `chore(docs): file the two prototype designs as dropped`

## Phase 3 — Remove the layer

One commit. Lists below were produced by `git rm` in the rehearsal clone.

### Product code deleted

- [x] Directories, whole: `skeleton/` (43 files), `protopilot/passes/` (18),
      `protopilot/archetypes/` (3), `protopilot/targets/` (3),
      `protopilot/console/` (the 6 files left after Phase 1), `protopilot/web/` (8)
- [x] Files: `protopilot/baseline.py`, `baseline_tui.py`, `browser.py`,
      `build.py`, `containers.py`, `files.py`, `generation.py`, `render.py`,
      `spec.py`, `tui_probe.py`, `tui_stream.py`, `verify.py`, `verify_tui.py`
- [x] Not deleted, and why: `runner.py` (the `claude-code` backend runs through
      it), `jobs.py` (`proto plan` runs on a job), `progress.py` (see *Approach*)

### Product code changed

- [x] `protopilot/cli.py`: remove `new`, `add`, `spec`, `up`, `down`, `reset`,
      `logs`, `test`, `export`, `gc`, `console`, `serve`, `archetypes`, `targets`
      and what only they used: `free_port`, `PORT_RANGE`, `_classify`,
      `_parse_answers`, `PLAN_INSTEAD`, `_project`, `_verifier`, `_port_is_ours`,
      `PORT_LINE`, `set_port`, `_down_all`, `_compose`, `_finish`, `_git_init`,
      `_preflight_backend`. Module docstring lists the survivors
- [x] `proto ls`: no Docker call, no port column, no `up`/`down` state. The empty
      message names `proto plan` only
- [x] `proto rm`: a plan is deleted as today. Anything else is refused. A folder
      holding `.protopilot/spec.json` gets its own sentence: it is a prototype
      from an older proto.pilot, this version removes plans only, run
      `docker compose down -v` there if it was a web prototype and delete the
      folder by hand
- [x] `proto doctor`: the SDK check and the two backend checks stay and decide
      the exit code as now. The per-target loop, the browser check and the port
      check go. The last line's hint is `--offline`, without `--no-verify`
- [x] `protopilot/registry.py`, *old registries* — a user's `projects.json` may
      hold `app` rows, and every `plan` row holds `"port": null`:
      - `Entry` keeps a `port` field, default `None`, read and written back
        unchanged. **Dropping the field would make `Entry(**item)` raise on every
        existing row, `load()` would skip them all, and the next `save()` would
        erase the user's list.** That is the trap this task exists for
      - `Entry.kind`'s default stays `"app"`: a row with no kind was written
        before kinds existed and is one. `record()` loses `port` and defaults to
        a plan
      - `tree_kind` answers `plan` or `None`. An `app` row therefore reads as
        not ours: `proto ls` lists it with state `old`, and prints once that
        proto.pilot no longer runs these, their folders are untouched, and
        `proto prune` forgets them
      - `proto prune` forgets `old` rows along with `gone` ones and says how many
        of each. It never touches a folder
      - `delete()` loses its `runner` parameter and its Docker call
      - `load()` ignores keys it does not know rather than dropping the row, so
        the next field added does not repeat the trap from the other side
- [x] `protopilot/runner.py`: delete `docker_available`; the docstring stops
      saying every Docker call goes through here
- [x] `protopilot/progress.py`: drop what only an app emitted (`spec`, `preview`,
      `target`, `archetype`, `run_hint`) and the tests of them in
      `tests/test_progress.py`; `pipeline.py:515` stops sending `run_hint=""`
- [x] `protopilot/plan/verify.py`: `VerifyResult.logs` and the "container logs"
      block go if `grep -rn "logs=" protopilot/plan` is empty
- [x] Reading pass over what is left, for comments that lean on the removed
      layer: `grep -rnE "proto new|prototype|Docker|docker|console|web front" protopilot cli scripts/*.py`.
      Known: `jobs.py` docstring, `pipeline.py:18`, `plan/passes/repair.py:29`,
      `cli.py`'s `_review_outline` docstring and the `sys.exit(1)` comment,
      `cli/check.py:399`, `cli/test_cmds.py:109`, `.env.example:98`,
      `.gitignore:40`. `tests/test_docs_name_live_code.py` catches the
      backticked-call half; the rest is reading

### Packaging, in the same commit because the install needs it

- [x] `pyproject.toml`: `packages = ["protopilot", "protopilot.plan", "protopilot.plan.passes"]`;
      delete `[tool.setuptools.package-data]`; `description` loses "and a running
      prototype when you want one"; `norecursedirs` loses `skeleton` here **and**
      in `tests/pytest.ini` (`tests/test_marker_coverage.py` compares the two)
- [x] Verify the wheel, since the editable install cannot: build one into a
      scratch directory, install it into a fresh venv, and run
      `proto plan "x" --offline -y` from outside the checkout

### Tests deleted whole (31)

- [x] `tests/test_archetypes.py`, `test_baseline.py`, `test_browser.py`,
      `test_clarify.py`, `test_console.py`, `test_console_iterate.py`,
      `test_console_layout.py`, `test_containers.py`,
      `test_crud_characterisation.py`, `test_files.py`, `test_generate.py`,
      `test_proto_cli_targets.py`, `test_proto_front_end_preflight.py`,
      `test_render.py`, `test_repair.py`, `test_skeleton_move_characterisation.py`,
      `test_spec.py`, `test_spec_assembly.py`, `test_targets.py`,
      `test_terminal_requirements.py`, `test_theme.py`,
      `test_tui_base_screen.py`, `test_tui_baseline_edges.py`,
      `test_tui_skeleton.py`, `test_tui_target.py`, `test_tui_verify.py`,
      `test_turn_based_game.py`, `test_verifier_wiring.py`, `test_verify.py`,
      `test_web.py`, `test_web_asks_the_tree.py`
- [x] Also: `tests/tui_probe_base_screen.py`, `tests/artifacts/` (one
      `kitten_chess/.protopilot/spec.json`), and
      `tests/golden/{crud_offline,tui_offline,web_skeleton}_manifest.json`.
      `tests/golden/plan_offline_manifest.json` is not touched

### Tests changed

Each line is what the rehearsal showed failing or failing to import.

- [x] `tests/conftest.py`: delete the `spec` fixture (line 120) and the `helper`
      fixture (line 163). It is a skeletor-recorded file; this only removes our
      additions
- [x] `tests/test_lifecycle.py`: keep the five `ls` and `prune` tests (lines
      45, 56, 78, 88, 95) on plan trees; delete `test_ls_marks_a_running_prototype`
      and every `gc`, `set_port`, `up` and `down` test
- [x] `tests/test_proto_doctor.py`: keep the three backend tests (lines 222,
      235, 249); delete the seven target and Docker tests; the fixture stops
      patching `cli.free_port`
- [x] `tests/test_job_events.py`: keep the three `Job`/`JobStore` tests (lines
      89, 102, 113); delete the five that run a generation
- [x] `tests/test_llm.py`: drop the `passes` and `clarify` imports;
      `test_every_schema_proto_new_sends_reaches_the_api_unchanged` becomes the
      same assertion over every schema under `protopilot.plan.passes`, if
      `tests/test_plan_model_output.py` does not already hold it
- [x] `tests/test_registry.py`: drop `is_test_path`; `test_prune_drops_…` and
      `test_delete_removes_…` build plan trees
- [x] `tests/test_registry_hardening.py`: delete the `client` fixture and
      `test_the_web_deletes_the_app_that_shares_an_idea_with_a_plan`
- [x] `tests/test_plan_surfaces.py`: delete
      `test_every_app_verb_refuses_a_plan_…`, `test_ls_shows_both_kinds_side_by_side`,
      `test_down_all_never_reaches_a_plan` and the three web tests
- [x] `tests/test_plan_kind_guards.py`: the two `app` cases of
      `test_tree_kind_reads_only_our_own_files` now expect `None`; delete
      `test_delete_asks_the_tree_…stops_a_stack_that_appeared`,
      `test_an_app_verb_run_inside_a_plan_tree_refuses_it`,
      `test_down_all_with_only_plans_has_nothing_to_stop` and the seven web
      tests; `test_an_entry_with_an_unknown_kind_…` loses its Docker recorder
- [x] `tests/test_plan_registry.py`: `test_an_entry_written_before_kinds_existed_reads_as_an_app`
      keeps its name and asserts the row is listed `old`;
      `test_delete_still_calls_an_apps_stack_down` becomes a refusal test
- [x] `tests/test_plan_cli.py:652`: the first-contact test asserts `new` is not a
      command
- [x] New, in `tests/test_registry_hardening.py`: a registry file written by
      0.3.0 (one `app` row with a port, one row with no `kind`, one `plan` row
      with `"port": null`, one row with an unknown key) survives
      `ls` → `record` → `load` with all four rows present, and `prune` forgets
      exactly the first two
- [x] New, in `tests/test_plan_surfaces.py`: `proto rm` on a folder holding
      `.protopilot/spec.json` exits non-zero, deletes nothing, and names
      `docker compose down -v`
- [x] `tests/cli_smoke_allowlist.yaml`: the `check health` reason loses "docker
      daemon" and "a free port"
- [x] `./pp check lint && ./pp check docs && ./pp test unit`
- [x] Commit: `feat(cli)!: remove the prototyping layer`, with a
      `BREAKING CHANGE:` paragraph naming the removed verbs and the tag

## Phase 4 — Dependencies and CI

- [x] `pyproject.toml`: core `dependencies` lose `sqlalchemy` and `textual`.
      `dev` loses `pytest-asyncio`, `sqlalchemy`, `textual`, `fastapi`, `jinja2`,
      `httpx`, `python-multipart` and the comments that explain them
      (`asyncio_mode` is mentioned at line 49). The `browser` and `web` extras
      go. Measured in the rehearsal: no surviving test is `async`, and the unit
      suite's failure set was identical with these lines removed
- [x] `.github/dependabot.yml` names none of these; nothing to change. Confirm
      with `grep -nE "skeleton|textual|sqlalchemy" .github/dependabot.yml .github/pyright-deps.txt`
- [x] `.github/workflows/ci.yml` is skeletor's file with our text merged in.
      Change only comments that are ours and now false: lines 548–556 (the
      project "plus the generated app's stack", extras, Playwright), 646–658
      (the integration placeholder's "skeleton, five passes, write guard"), and
      684–689 (`tests/test_console*.py`). Leave 476–479: it records why the
      matrix was halved, which stays true as history. **No job, step, trigger or
      `if:` changes**
- [x] `scripts/template_divergence_allowlist.yaml`: the `.github/workflows/ci.yml`
      entry says "with this tree's extras". Reword it to what still differs. Do
      not delete it unless `tests/test_template_divergence_allowlist.py` says the
      file now matches skeletor's render
- [x] `cli/test_cmds.py:109`: the `ui` row's reason cited the console's pilot
      tests. The suite is still empty and still unscheduled; say why without them
- [x] Rebuild the venv from the Quick Start lines, so the gates run without the
      removed packages installed, then `./pp check pre-push`
- [x] Commit: `build: drop the dependencies only generated apps needed`

## Phase 5 — Re-record the coverage baseline

`tests/coverage_budget.json` holds `own_baseline_pct: 87.32` under `scheduled`.
The own population was `protopilot/` plus `skeleton/`; it is now about 2,800
statements of `protopilot/`, and the rehearsal read roughly 95% over them with
four test files not yet repaired. The ratchet fails only on a drop, so nothing
goes red, but a baseline eight points under the truth protects nothing.

- [x] Do not hand-edit the number. Record it from the nightly's own sequence on
      `/usr/bin/python3.11`: a fresh venv, `scripts/requirements.txt`, the
      project through `scripts/install_project.py`, the unit run with `--cov`
      then the integration run with `--cov-append` as `coverage-nightly.yml`
      lines 80–110 spell them, `coverage xml -o tmp/coverage.xml`, then
      `python scripts/check_coverage_budget.py --suite scheduled --update --xml tmp/coverage.xml`
- [x] If the measurement is taken in a copy of the tree, clear `__pycache__`,
      `.pytest_cache` and `.coverage` there first
- [x] `python scripts/check_coverage_budget.py --suite scheduled` passes against
      the new number
- [x] Commit: `test(coverage): re-record the baseline over the planning code`,
      with the old and new figures and the interpreter in the body

## Phase 6 — Prove it, and open the PR

- [x] `./pp check pre-push` and `./pp test all`, both green
- [x] `proto plan "start a community tool library" --offline -y --dir <scratch>`
      writes ten files, and `git diff develop -- tests/golden/plan_offline_manifest.json`
      is empty
- [x] `proto --help` lists exactly `doctor`, `dream`, `ls`, `plan`, `prune`, `rm`
- [x] `gh pr create --draft --base develop`; mark it ready when green. PRs skip
      whole-project pyright here, so after the merge watch the `develop` run for
      the merge SHA to the end
- [x] `./pp docs file remove-prototyping --category spec`

## For the operator

Not tasks: nothing above waits on them, and a `ready` plan may not carry a step
an agent cannot take. They are listed so the PR body can carry them.

1. **Push the tag.** Done: pushed 2026-11-11. `git push origin prototyping-final`. The standing push
   permission covers `develop` and says nothing about tags. Until it is pushed
   the old layer is recoverable from this machine only.
2. **Report to skeletor.** `.claude/skills/release/SKILL.md:41` runs
   `git describe --tags --abbrev=0` with no `--match`, so once this tag is the
   nearest one it answers `prototyping-final` there. The file is skeletor's and
   is not edited here. Also worth reporting: the docs lifecycle has no state for
   a plan that was dropped rather than finished.
3. **Tell the workspace its two copies are stale.** The proto.pilot row in
   the company workspace guide ("its Dockerised prototypes are tabled but
   still run") and the product copy in `skyrowlabs.com/README.md`. Two other
   repos, two other changes.

## Acceptance

- [x] `git ls-files skeleton protopilot/passes protopilot/archetypes protopilot/targets protopilot/console protopilot/web`
      prints nothing
- [x] `grep -rnE "sqlalchemy|textual|fastapi|playwright|uvicorn|jinja" pyproject.toml protopilot`
      prints nothing
- [x] `python -c "import protopilot.cli as c; print(sorted(c.main.commands))"`
      prints `['doctor', 'dream', 'ls', 'plan', 'prune', 'rm']`
- [x] `./pp test unit` green with zero skips, and
      `python scripts/check_skip_budget.py --suite unit` agrees
- [x] The 0.3.0 registry test in Phase 3 passes: no row is lost by an upgrade
- [x] `tests/golden/plan_offline_manifest.json` is byte-identical to `develop`'s
- [x] A wheel built from the branch runs `proto plan --offline` outside the
      checkout
- [x] `git tag -l prototyping-final` prints the tag, and
      `git show prototyping-final:protopilot/build.py` prints the file
- [ ] (~deferred) CI is green on the PR, and on `develop` at the merge SHA: observed after the push, recorded in the PR

## Dropped, and why

- **Keeping one front end as a plan reader.** `proto serve` already showed a
  plan read-only. Decided against on 2026-11-11: both front ends are built
  around starting and watching a generation, and a reader cut out of either
  would carry FastAPI or Textual for one page. A reader can be designed later
  from what a plan needs; see [living-plans](../../TODO/living-plans.md), *Dropped*.
- **Deleting `progress.py` with the console.** It has no product caller once the
  console is gone. Kept because 15 plan assertions read events through it
  rather than through `job.lines`, and because it is the seam a later reader or
  a `--json` status folds.
- **Migrating old `app` rows out of the registry on first load.** A read that
  rewrites is how `proto ls` once emptied the registry
  (`docs/NOTES.md`, the `prune()` trap). The rows stay until a person runs
  `proto prune`.
- **Having `proto rm` still stop an old web prototype's stack.** It would keep a
  Docker call and a compose assumption alive for trees this version cannot
  make. The refusal says what to type instead.
- **A branch instead of a tag for the old layer.** A branch invites commits. The
  tag is one fixed point and cannot drift.
- **Splitting Phase 3 into front ends first, generation second.** It would be
  two green commits instead of one. Not done because only the one-commit shape
  was rehearsed, and an unrehearsed split is where an unlisted red would come
  from.
- **Removing the empty `integration` job or the `node` job from `ci.yml`.** Both
  are skeletor's and both are required contexts; neither exists for the removed
  layer.
- **Adding a "dropped" status to `docs/rules/docs.md`.** That file is
  skeletor's, with one recorded divergence already. The two designs are filed
  under a `dropped` category with a status line that says so, and the gap in
  the lifecycle is worth reporting to skeletor rather than patching here.
