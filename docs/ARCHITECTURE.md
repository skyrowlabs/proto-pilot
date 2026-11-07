# Architecture

The map. **This file says what the pieces are and how they connect**; it
deliberately does not restate two things that live elsewhere:

- **Why the design is this way** — [`README.md`](../README.md), which is the
  design document and explains the five load-bearing decisions.
- **The rules for changing it** — [`AGENTS.md`](../AGENTS.md), which carries the
  invariants and what softening one costs.

Linked, never duplicated. A component table that also argues for itself goes
stale in the half nobody re-reads.

## What This Is

`proto new "an idea"` turns one sentence into a running prototype. By default a
Textual + SQLite app in your terminal; with `--target web`, a Dockerised FastAPI
+ Postgres app in a browser. The output is something to look at this afternoon
and throw away — not a production starting point, and the pipeline is shaped by
that all the way down.

Two command-line tools live in this repo and are **not** the same thing:
`proto` is the product (installed on PATH, `protopilot/`), `./pp` is this
repository's own tooling (`cli/`, `scripts/`). See AGENTS.md Rule 15.

## Data Flow

One generation, end to end. Every arrow is a place something can be refused.

```
  idea (one sentence)
    │
    ├─▶ clarify ──────────  one cheap call: a few targeted questions
    │                       (the cheapest place to fix a misunderstanding
    │                        is before anything is generated)
    ▼
  intake ─────────────────  idea ──▶ spec.json, typed and small
    │
    ▼
  ┌───────────────┐
  │ HUMAN REVIEW  │◀────── the only gate in the tool. `spec.summary()` is
  └───────────────┘        what it prints, so a field it omits is a field
    │                      nobody reviews.
    ▼
  render_skeleton ────────  the target's skeleton copied byte-for-byte,
    │                       @@TOKEN@@ filled
    │
    ▼
  the target's passes ────  web: schema ▶ smoke ▶ seed ▶ routes ▶ ui
    │                       tui: schema ▶ smoke ▶ seed ▶ screens ▶ ui
    │                       each fed the PREVIOUS pass's real source
    │                       every write filtered through files.py, against
    │                       the running target's allowlist
    ▼
  the target's verifier ──  web: compose up ▶ /healthz ▶ pytest in the
    │                            container ▶ logs ▶ (browser stage)
    │                       tui: import ▶ App.run_test ▶ pytest ▶ compare the
    │                            screen buffer to an empty app's
    │
    ├── green ──▶ registry.record ──▶ the target's hand-back line
    │
    └── red ────▶ repair pass ──▶ verify again (×3)
                    │
                    └── still red ──▶ RUNBOOK.md, tree handed back anyway
```

## Components

| Component | Responsibility | Talks to |
| --------- | -------------- | -------- |
| `protopilot/cli.py` | The `proto` command: generation, prototype lifecycle and `proto plan` | everything below |
| `protopilot/web/` | `proto serve` — a web face on `proto new`, **pinned to `--target web`** | the same functions the CLI calls |
| `protopilot/spec.py` | **The contract.** The only thing downstream reads about user intent | every pass |
| `protopilot/passes/` | One module per pass; prompt, JSON Schema, and the previous pass's source. `passes/tui/` is the terminal set | `llm.py`, `files.py` |
| `protopilot/build.py` | Orchestration: the repair loop, the runbook floor. The pass *tuple* is the target's | `passes/`, `targets/`, `verify.py` |
| `protopilot/files.py` | **The write guard.** A handful of allowed paths; everything else refused. The mechanism only — the list is the target's | `passes/` |
| `protopilot/llm.py` | `LLM` Protocol + three backends (api, claude-code, offline) | `anthropic`, the `claude` CLI |
| `protopilot/baseline.py` | Deterministic offline implementation of every pass, web | `spec.py` |
| `protopilot/baseline_tui.py` | The same, for the three files whose content is the medium's | `baseline.py`, `spec.py` |
| `protopilot/verify.py` | **Web:** boot, health-wait, run the smoke suite, capture logs | `runner.py`, `browser.py` |
| `protopilot/verify_tui.py` | **Terminal:** import, boot under `App.run_test`, smoke suite, blank-screen check | `runner.py`, `tui_probe.py` |
| `protopilot/tui_probe.py` | Runs inside a generated tree as a subprocess; reports what it painted | the generated app |
| `protopilot/browser.py` | Loads every web screen for real; fails a page that painted nothing | Playwright, optional |
| `protopilot/runner.py` | Every subprocess, behind a Protocol so Docker can be faked | `subprocess` |
| `protopilot/registry.py` | JSON index of generated trees — what exists, where, on which port | the filesystem |
| `protopilot/containers.py` | **Docker as a second, independent source of truth**, via labels | `runner.py` |
| `protopilot/render.py` | a target's skeleton ▶ a project directory, substituting `@@TOKEN@@` | `targets/`, `skeleton/` |
| `protopilot/archetypes/` | What SHAPE a spec is: questions, screen rule, prompt fragment, baseline | `spec.py`, `baseline.py` |
| `protopilot/targets/` | What MEDIUM it is built in — fifteen things, listed below | `passes/`, `verify.py`, `verify_tui.py` |
| `protopilot/jobs.py` | In-process job store: the web front end runs generations on it in the background, and `proto plan` runs on it from the CLI | `web/`, `cli.py` |
| `protopilot/plan/` | `proto plan`, a sibling pipeline to `Spec` — [below](#the-plan-pipeline) | `jobs.py`, `llm.py`, `spec.py` |
| `skeleton/` | The fixed application tree copied into every generated app, one directory per target. **Not generated** | — |
| `cli/`, `scripts/` | This repo's own gates and jobs. Never shipped to a user | — |

## What a target owns

A target is one module in `protopilot/targets/`, discovered by presence — a file
in that directory is a registered target and there is no list beside it to
update. It declares **thirteen module-level constants and two functions**, all
fifteen required;
`tests/test_targets.py::test_every_target_declares_the_whole_contract`
recomputes the list over whatever is installed, so a third target cannot omit
one.

| Declares | What it decides | `web` | `tui` |
| --- | --- | --- | --- |
| `NAME` | the identifier stored in `spec.json` | `web` | `tui` |
| `LABEL` | the phrase shown when a person is choosing | a web app you open in a browser | a terminal app you run in a shell |
| `SKELETON_DIR` | the tree copied byte-for-byte | `skeleton/web/`, 24 files | `skeleton/tui/`, 19 files |
| `CODE_PASSES` | the pass modules, in order | `schema ▶ smoke ▶ seed ▶ routes ▶ ui` | `schema ▶ smoke ▶ seed ▶ screens ▶ ui` |
| `REPAIR` | the pass the repair loop runs, which is not in the tuple | talks about container logs and 307s | talks about the boot probe's report |
| `WRITABLE` | what a pass may write | five paths | six — `app/app.tcss` is generated here |
| `PROTECTED` | skeleton sitting under a writable glob | `app/templates/base.html` | empty; no globs to exclude from |
| `ARCHETYPES` | which archetypes it can actually build | `crud`, `turn-based-game` | `crud`, `turn-based-game` |
| `USES_PORT` | whether `spec.port` means anything | `True` | `False` |
| `HANDOFF` | the green hand-back line | `http://localhost:{port}` | `cd {directory} && make run` |
| `RUN_HINT` | what to type to start it | `make up` | `make run` |
| `LOGS_LABEL` | what the RUNBOOK's second stream is | Container logs | What the app printed |
| `MANUAL` | the RUNBOOK's carry-on-by-hand block | `docker compose …` | `python -m app.main` |
| `preflight(runner)` | what must be true before generating | a Docker daemon | nothing |
| `verifier(…)` | a `verify.Verifies` for the tree | `Verifier` | `TuiVerifier` |

**Eleven of those fifteen were not designed; they were found.** The plan that
built the second target named four — skeleton directory, pass tuple, write
allowlist, verifier. Of the eleven that arrived by building it, `NAME`, `LABEL`,
`PROTECTED` and `ARCHETYPES` are registry bookkeeping and `REPAIR` is a sixth
pass; the other six are the interesting ones, because **each was a sentence
hardcoded somewhere that turned out to be true only of Docker**. A port printed
at the review checkpoint for an app that listens on nothing. `http://localhost:`
in the hand-back. `make up` under `--no-verify`. "Container logs" in the
RUNBOOK, and a `docker compose` block beneath it. `docker_available` asked
before intake, refusing a generation that needed no daemon.

The general shape is what carries forward: **a second medium costs several times
what the seam looks like it costs, and the excess is prose the tool prints about
itself.** Those sentences are invisible while there is one medium, because
nothing distinguishes "true" from "true here".

A sixteenth thing is target-owned and does *not* live on the module: the
**archetype prompt fragments**, which are written per medium (`archetypes.brief_for()`
says "in the same browser" and "inline SVG") and live beside the passes, in
`protopilot/passes/_shared.py` and `protopilot/passes/tui/_brief.py`.

### Two defaults, and they answer different questions

Never write "the default target" without saying which:

- **`targets.DEFAULT`** is `"tui"`. What a *new* spec is born with — what
  `proto new` picks when nobody passes `--target`.
- **`Spec.target`'s field default** is `"web"`. What a `spec.json` written
  before this axis existed **means**, permanently. An old spec still generates
  the app it always did.

They are separate constants and
`tests/test_targets.py::test_the_cli_default_and_the_field_default_are_separate_constants`
pins both literals. Collapsing them into one would make the next flip silently
rewrite the meaning of every spec on disk.

## The plan pipeline

`proto plan "an idea"` writes a folder of text instead of an app:
`PLAN.md`, `topics/`, `dreams.md`, `sources.md` and a stored `plan.json`, with a
`RUNBOOK.md` when the plan ends red. Why is [plans-first](ideas/plans-first.md); the design and what is still to build are
[plan-prototypes](TODO/plan-prototypes.md); flags are in [CLI.md](CLI.md#proto-plan).

**It is a sibling of the `Spec` pipeline, not a third target.** It shares the job
seam and its event vocabulary, the `.protopilot/` directory, the slug rule from
`spec.py`, and the rule that a pass has an offline twin. It reads no `Spec`, no
target and no skeleton, and the write guard does not apply: model output reaches
`render.write` as text inside a page, never as a path. The one model value in a
file name is a topic slug, which `model.py` checks, and `render.py` escapes any
HTML opener in plan text.

- **`plan.json` is the truth.** `model.py` defines it; every markdown file is
  drawn from it, and a re-render overwrites them, so an edit belongs in `plan.json`.
- **Rendering is deterministic.** `render.py` uses no model and no clock, so one
  plan is one set of bytes; `tests/test_plan_render.py` holds that.
- **A run is `scope`, `outline`, the review, `connect`, `consider`, `start`,
  verification, any repair, then render.** That is five model calls and up to three
  repair calls, one module each in `protopilot/plan/passes/`. `pipeline.py` runs them on one job, in halves, so `proto plan` can stop for
  scope's questions and the outline review. `--yes` skips both, and off a terminal
  it is required, `--offline` included, because a prompt there cannot be answered.
- **Nothing is researched yet.** No research or dreaming pass exists, so every plan
  is stamped not researched, green or red. A pass's `apply` reads only the fields it
  names, so none can set `researched`, `sources` or a finding: a model run's topics
  have no findings, and an offline run's have only the baseline's assumptions.
  `apply` refuses what a plan cannot hold, such as an edge or a step naming a missing
  topic. Order is the verifier's: a step ahead of its dependency lands in the plan and
  goes red at `start_order`.
- **Verification proves structure, never truth.** `verify.py` has one check per bullet
  of [What "verified" means](TODO/plan-prototypes.md#what-verified-means-for-text):
  `topic_map`, `no_cycles`, `findings_traced`, `sources_fetched`, `start_order`,
  `dreams_shaped` and `dreams_apart`. Each is a pure function of a plan and its pages,
  so one check judges the pages drawn in memory and the pages read back from disk, and
  all of them always run. A check ends passed, failed or no subject, and no subject
  proved nothing. `green_line` builds its sentence from what held: *coherent and
  traceable* needs `findings_traced` and `sources_fetched` both to hold, which no
  run earns until research records a fetch, so green today says the structure holds
  and that nothing traces to a source.
- **Repair reaches links and steps, and nothing else.** On red, `repaired` runs
  `protopilot/plan/passes/repair.py` up to three times, against pages drawn in memory,
  so repair only ever edits data. Its `apply` is `connect`'s then `start`'s, and `FIXES`
  names the two checks whose subject that is, `no_cycles` and `start_order`; any other
  failure goes to the floor with no call made. `rejected` is the plan's shrink guard,
  judged against the plan repair started from: it throws away a repair that removes an
  edge on no loop, every link of a loop, or a healthy step, unless the step cap forced
  that out for a step a kept one waits on. `worsened` throws away one that leaves more
  wrong than it found. A thrown-away attempt counts, and its reason goes into the next.
  A repair pass that fails or changes nothing stops the loop, and offline, where the
  twin returns the plan as it stands, that is the first attempt.
- **The floor hands back a whole tree.** A plan still red is written anyway, with a
  `RUNBOOK.md` from `verify.runbook`, a *Not verified* banner on `PLAN.md` and every
  topic page, and no green line; `finished` says `ok=False` and the CLI exits 1, as
  `proto new`'s floor does. `_hand_back` then judges what landed, so a plan green in
  memory and red on disk takes the floor too. A failed pass is a different thing: a
  pass that returns nothing a plan can hold leaves no tree at all.
- **The baseline is the offline twin.** `baseline.py` builds a generic plan from the
  idea's words, and each pass's `offline` slices it. It always has the same six
  topics, so `--depth`, which asks for 4, 6 or 8, is refused on an offline backend.
- **Nothing reaches disk until render.** `plan.json` saves atomically, then the pages
  follow. In a fresh tree `PLAN.md` goes last, so holding it means holding every page;
  over an old one a red plan draws it first, so a write that dies midway leaves it
  marked. A failed model pass leaves no tree, and a rerun starts from scope, losing any
  review edits. A render that fails after that save keeps `plan.json`, so a rerun
  redraws it. **That order covers `PLAN.md` alone:** a write dying mid-render can leave
  old topic pages, unmarked, which is why `after_failure` says any page may be out of
  date and points at the rerun.
- **A rerun of a finished plan is a re-render, and it verifies.** No pass runs, and it
  needs neither `--yes` nor a terminal. Another idea, direction or `--depth` is refused.
  `plan.json` may be hand-edited, so `rerender` judges it as it stands, and red takes
  the floor and exits 1. With no model there is no repair, so a red tree's rerun never
  retries one: a fresh attempt means removing the tree.
- **`render.write` never writes through what it did not make.** `_blockers` names a
  link, dangling or not, at a page path or at `topics/`, a directory at a page path,
  and a `RUNBOOK.md` that does not open with `RUNBOOK_MARK`, which is a person's. A
  green plan that is blocked draws nothing. A red one draws every page it can reach,
  so no old page goes on reading as verified, then refuses. Both refuse by name with
  exit 1, nothing is written outside the tree, and a link is neither followed nor
  removed. A green run removes a runbook only if it carries the mark, so a person's
  stays.
- **A plan tree is not a prototype.** It is not in the registry, so `proto ls`
  omits it, and `proto rm`, `up` and the other app commands refuse it for having no
  `spec.json`.

## Critical Patterns

Patterns a change can violate **silently** — the code still runs, and the
failure surfaces somewhere else, later, as something else.

### Model output passes through the write guard

Every file a pass produces goes through `files.py`, which refuses anything
outside the running target's allowlist *before it reaches disk*. A pass that writes directly works
perfectly in the happy case, which is exactly why the violation is invisible:
you only find out the day a model decides to helpfully rewrite `app/main.py` or
the Dockerfile, and by then the tree that was known-good is not.

### The pass order is the design

`schema ▶ smoke ▶ seed ▶ routes ▶ ui`, and `schema ▶ smoke ▶ seed ▶ screens ▶ ui`
one medium over. Smoke tests are generated **second**, from the spec, when
nothing they test exists yet — so they describe what was *asked for*. Reorder so
tests come afterwards and they still generate, still pass, and now describe
whatever the code happened to do. Nothing goes red. The suite just stops being
evidence.

The tuple is the target's; the invariant is `build.py`'s and holds for every
target.

### The baseline is half of every pass

Change a pass's prompt without changing `baseline.py` and CI stays green while
exercising the old shape — because the baseline is what CI runs. The suite
reports on a pipeline nobody is using. Both halves, same commit.

### The stack brief is a cache prefix

`protopilot/passes/_shared.py` is byte-identical across every pass and every repair
attempt, deliberately, so it stays a prompt-cache prefix. Personalising it per
pass costs nothing visible and multiplies the bill. Nothing fails; it just gets
expensive quietly.

### `spec.port` and `compose.yml` must agree — on the web target

The port is chosen at generation and frozen into `compose.yml`. Update one
without the other and you get a prototype that runs somewhere other than where
every command says it does. `cli.set_port()` is the only thing that should move
it, and it moves both.

A terminal prototype has no port. `spec.port` is still populated for one — the
registry allocates it and `proto ls` prints it — and it means nothing, which is
why `USES_PORT` exists rather than a check for a `compose.yml`.

### The registry and Docker are two answers on purpose — on the web target

`registry.py` is what we wrote; `containers.py` is what Docker knows, read back
from labels. They are allowed to disagree — that disagreement is how `proto gc`
finds a tree that was deleted with `rm -rf`. Making one derive from the other
collapses them into a single source that cannot detect its own gaps.

`gc`, the resource labels and `up`/`down`/`logs`/`test`/`reset` are Docker verbs
and stay web-only. **There is genuinely nothing to collect for a terminal tree**:
a terminal verify writes a fresh SQLite file per attempt into `<tree>/.dbs/`,
inside the tree, so deleting the tree orphans nothing and there is no daemon to
ask. Do not extend the label vocabulary to `tui` — machinery applied to a target
with no resources to label reads as coverage and is not. `proto prune` is about
the *registry* rather than Docker and applies to any tree. What remains open is
what these commands should *say* for a `tui` project, and that is in
[`NOTES.md`](../NOTES.md), not here.

### A skipped verification stage is reported as skipped

Without the `browser` extra, the browser stage does not run — and says so.
Never as green. A stage that silently passes when it did not execute is the
most expensive shape of lie a verification loop can tell.

The terminal target's equivalent — the `paint` stage, two rendered buffers
compared — needs no extra and is never skipped.

### The blank screen is caught twice, and the outer one is the backstop

`skeleton/tui/tests/test_boots.py` asserts a non-empty buffer, and it is
skeleton, so **every generated tree carries it**. An app that paints nothing
therefore goes red at `tests`, one stage before `paint` ever looks. The `paint`
stage catches the narrower case the tree's own suite cannot — an app whose smoke
suite was silenced or never asked, that mounts, answers every query and shows
nothing.

Read in the other order this is a doc that mislabels which stage fires. The
useful consequence: a blank-screen regression reported at `tests` is the normal
path and not evidence that `paint` is broken.
## Decisions and Their Reasons

- **The five load-bearing decisions** — fixed stack, the write guard, tests
  before code, each pass reading real source, nothing handed back unobserved —
  are argued in [`README.md`](../README.md#how-it-works).
- **What is unfinished, and what bit us** — [`NOTES.md`](../NOTES.md), the live
  parking lot, including traps that are fixed but worth knowing.
- **Planned work** — [`TODO/README.md`](TODO/README.md). A new plan goes
  there before any code does.
- **Completed plans** — [`implementations/README.md`](implementations/README.md).
  [Archetypes and Theme](implementations/spec/archetypes-and-theme.md) is the
  first one filed, and the one to read before touching the spec: it is what
  reshaped `spec.py` and added `protopilot/archetypes/`. Its landed-notes
  carry what each phase's live call found, which is the half no test records.
