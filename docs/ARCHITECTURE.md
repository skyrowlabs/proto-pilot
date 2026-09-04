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

`proto new "an idea"` turns one sentence into a running Dockerised web app.
The output is something to click through this afternoon and throw away — not a
production starting point, and the pipeline is shaped by that all the way down.

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
    │                       each fed the PREVIOUS pass's real source
    │                       every write filtered through files.py, against
    │                       the running target's allowlist
    ▼
  verify ─────────────────  compose up ▶ wait on /healthz ▶ pytest in the
    │                       container ▶ capture logs ▶ (browser stage)
    │
    ├── green ──▶ registry.record ──▶ a URL
    │
    └── red ────▶ repair pass ──▶ verify again (×3)
                    │
                    └── still red ──▶ RUNBOOK.md, tree handed back anyway
```

## Components

| Component | Responsibility | Talks to |
| --------- | -------------- | -------- |
| `protopilot/cli.py` | The `proto` command: generation and prototype lifecycle | everything below |
| `protopilot/web/` | `proto serve` — a web face on `proto new` | the same functions the CLI calls |
| `protopilot/spec.py` | **The contract.** The only thing downstream reads about user intent | every pass |
| `protopilot/passes/` | One module per pass; prompt, JSON Schema, and the previous pass's source | `llm.py`, `files.py` |
| `protopilot/build.py` | Orchestration: the repair loop, the runbook floor. The pass *tuple* is the target's | `passes/`, `targets/`, `verify.py` |
| `protopilot/files.py` | **The write guard.** Five allowed paths; everything else refused. The mechanism only — the list is the target's | `passes/` |
| `protopilot/llm.py` | `LLM` Protocol + three backends (api, claude-code, offline) | `anthropic`, the `claude` CLI |
| `protopilot/baseline.py` | Deterministic offline implementation of every pass | `spec.py` |
| `protopilot/verify.py` | Boot, health-wait, run the smoke suite, capture logs | `runner.py`, `browser.py` |
| `protopilot/browser.py` | Loads every screen for real; fails a page that painted nothing | Playwright, optional |
| `protopilot/runner.py` | Every subprocess, behind a Protocol so Docker can be faked | `subprocess` |
| `protopilot/registry.py` | JSON index of generated trees — what exists, where, on which port | the filesystem |
| `protopilot/containers.py` | **Docker as a second, independent source of truth**, via labels | `runner.py` |
| `protopilot/render.py` | a target's skeleton ▶ a project directory, substituting `@@TOKEN@@` | `targets/`, `skeleton/` |
| `protopilot/archetypes/` | What SHAPE a spec is: questions, screen rule, prompt fragment, baseline | `spec.py`, `baseline.py` |
| `protopilot/targets/` | What MEDIUM it is built in: skeleton, pass tuple, write allowlist, verifier | `passes/`, `verify.py` |
| `protopilot/jobs.py` | In-process job store so the web front end can run work in the background | `web/` |
| `skeleton/` | The fixed application tree copied into every generated app, one directory per target. **Not generated** | — |
| `cli/`, `scripts/` | This repo's own gates and jobs. Never shipped to a user | — |

## Critical Patterns

Patterns a change can violate **silently** — the code still runs, and the
failure surfaces somewhere else, later, as something else.

### Model output passes through the write guard

Every file a pass produces goes through `files.py`, which refuses anything
outside five paths *before it reaches disk*. A pass that writes directly works
perfectly in the happy case, which is exactly why the violation is invisible:
you only find out the day a model decides to helpfully rewrite `app/main.py` or
the Dockerfile, and by then the tree that was known-good is not.

### The pass order is the design

`schema ▶ smoke ▶ seed ▶ routes ▶ ui`. Smoke tests are generated **second**,
from the spec, when no route exists — so they describe what was *asked for*.
Reorder so tests come after routes and they still generate, still pass, and now
describe whatever the code happened to do. Nothing goes red. The suite just
stops being evidence.

### The baseline is half of every pass

Change a pass's prompt without changing `baseline.py` and CI stays green while
exercising the old shape — because the baseline is what CI runs. The suite
reports on a pipeline nobody is using. Both halves, same commit.

### The stack brief is a cache prefix

`passes/_shared.py` is byte-identical across every pass and every repair
attempt, deliberately, so it stays a prompt-cache prefix. Personalising it per
pass costs nothing visible and multiplies the bill. Nothing fails; it just gets
expensive quietly.

### `spec.port` and `compose.yml` must agree

The port is chosen at generation and frozen into `compose.yml`. Update one
without the other and you get a prototype that runs somewhere other than where
every command says it does. `cli.set_port()` is the only thing that should move
it, and it moves both.

### The registry and Docker are two answers on purpose

`registry.py` is what we wrote; `containers.py` is what Docker knows, read back
from labels. They are allowed to disagree — that disagreement is how `proto gc`
finds a tree that was deleted with `rm -rf`. Making one derive from the other
collapses them into a single source that cannot detect its own gaps.

### A skipped verification stage is reported as skipped

Without the `browser` extra, the browser stage does not run — and says so.
Never as green. A stage that silently passes when it did not execute is the
most expensive shape of lie a verification loop can tell.

## Decisions and Their Reasons

- **The five load-bearing decisions** — fixed stack, the write guard, tests
  before code, each pass reading real source, nothing handed back unobserved —
  are argued in [`README.md`](../README.md#how-it-works).
- **What is unfinished, and what bit us** — [`NOTES.md`](../NOTES.md), the live
  parking lot, including traps that are fixed but worth knowing.
- **Planned work** — [`TODO/README.md`](TODO/README.md). The holding tank is
  empty; the next plan goes there before any code does.
- **Completed plans** — [`implementations/README.md`](implementations/README.md).
  [Archetypes and Theme](implementations/spec/archetypes-and-theme.md) is the
  first one filed, and the one to read before touching the spec: it is what
  reshaped `spec.py` and added `protopilot/archetypes/`. Its landed-notes
  carry what each phase's live call found, which is the half no test records.
