# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Workspace-wide conventions (naming, doc ownership, cross-repo seams) live in
`../CLAUDE.md`. This file covers only proto-pilot.

## What this repo is

A framework for prototyping ideas with agents. `proto new "an idea"` turns a
sentence into a running Dockerised FastAPI app: idea → typed `spec.json` →
skeleton copied → five generation passes → `docker compose up` → observed →
bounded repair loop → a URL.

The output is a thing to look at this afternoon and throw away — explicitly not a
production starting point.

**`README.md` is the design document.** It explains the five load-bearing
decisions and why each exists. Read it before changing pipeline behavior; the
reasoning there is what keeps this from degenerating into a stack-picking code
generator.

## Branches

Work lands on `develop`; `main` is what has been released. The split arrived
2026-08-30 with the CI and licence work, for the reason the workspace guide
gives: two branches are what an audience costs. One ref cannot answer both
*what is being worked on* and *what you should expect to work*, and the moment a
stranger can clone the repo those became different questions.

CI runs on push and pull request against both, so a change is gated twice. The
README's CI badge reads `?branch=develop` — the branch that is actually moving.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate   # required — Arch's Python is externally managed
pip install -e ".[dev]"
proto doctor            # checks Docker, the SDK, credentials and a free port
python -m pytest -q     # no key, no Docker daemon needed
```

`pip install -e ".[dev]"` without a venv — as the README's install section says —
fails on this machine. Extras: `dev` (pulls the generated app's stack too, since
the e2e test runs a generated tree in-process), `browser` (Playwright; without it
the browser stage is **skipped and reported as skipped, never as green**), `web`.

Needs Docker with Compose v2 and Claude credentials for the model path —
`ANTHROPIC_API_KEY`, or a subscription via the Claude Code CLI backend.

## Invariants — do not soften these

These are the guarantees that make generated output trustworthy. Each was a
deliberate decision, not an accident of implementation.

- **The model can only write five paths**: `app/models.py`, `app/routes.py`,
  `app/seed.py`, `app/templates/*.html` (except `base.html`), and
  `tests/test_smoke.py`. Everything else is refused by `files.py` *before it
  reaches disk*. Model output is data, not authority — the parts of the tree
  known to work are exactly the parts the model must not be able to touch.
  Widening this list is a significant design change, not a convenience fix.
- **The stack is fixed, not chosen.** FastAPI, server-rendered Jinja, SQLAlchemy
  2.0, Postgres. No JS build step, no CDN, no migrations. A generator that picks a
  stack per idea produces N unrunnable variants. Everything in `skeleton/` is
  copied byte for byte into every app, so it is debugged once rather than once per
  prototype. **`skeleton/` is copied, never generated.**
- **Tests are generated before the code they test.** Pass order is
  `schema → smoke → seed → routes → ui`. Smoke tests come second, from the spec,
  when no route exists yet — so they describe what was *asked for*, not what got
  built. Reordering the passes breaks this.
- **Each pass reads the previous pass's real source**, never a description of it.
  UI goes last and receives `routes.py`, because a template referencing a context
  key no route passes is the most common way a generated app 500s.
- **Nothing is handed back unobserved.** `verify.py` brings the stack up, waits on
  `/healthz` (which checks the DB, so it stays red while Postgres boots), runs the
  smoke suite inside the container, and captures logs. Three repair attempts, then
  a **floor**: the tree is handed back anyway with a `RUNBOOK.md` naming the red
  stage, the last error, and what was tried. A known-broken prototype beats a
  mystery, and both beat a loop that never terminates.
- **The shrink guard**: if a repair shrinks the smoke suite, the file is reverted.
  Green because there is nothing left to fail is the one failure mode nobody would
  otherwise notice.

## Layout

| Path | What |
|---|---|
| `protopilot/passes/` | One module per pass — `intake`, `clarify`, `models`, `smoke`, `seed`, `routes`, `ui`, `repair`; `_shared.py` holds the stack brief |
| `protopilot/files.py` | The write guard — the five-path allowlist |
| `protopilot/verify.py` | Boot, health-wait, smoke run, log capture |
| `protopilot/baseline.py` | The deterministic offline implementation of every pass |
| `protopilot/llm.py` | `LLM` Protocol + three backends (see below) |
| `protopilot/browser.py` | Browser verification stage (Playwright) |
| `protopilot/registry.py` | Tracked prototypes — see the `prune()` trap below |
| `protopilot/web/` | The web front end |
| `skeleton/` | Copied byte-for-byte into every generated app |

## The offline baseline is the test suite

Every pass has two implementations: a prompt, and a deterministic generator in
`baseline.py`. `--offline` runs the second — no API calls, no key, a plain CRUD app.

It exists for three reasons, in increasing importance: a fast free path to a
skeleton; the worked example each prompt is written against; and **it is what the
test suite runs**, so the whole pipeline — skeleton, five passes, write guard,
repair loop — is exercised on every commit with no key and no Docker daemon. A
pipeline that can only be tested with a network call and a credit card stops being
tested.

`tests/test_generate.py` generates a two-entity parent/child app offline and runs
*that app's own smoke suite* against SQLite in a subprocess. Docker and the API are
faked in `tests/fakes.py`, so verify and repair — most likely to be wrong, least
likely to be covered end-to-end — are tested directly.

When adding a pass or changing one, the baseline implementation is part of the
change, not a follow-up. `proto add` is the exception: it needs the model, because
the baseline cannot read a change request.

## Model backends

`LLM` is a one-method Protocol (`structured`), which is what lets one set of
prompts serve every backend:

- `OfflineLLM` — the baseline. No key.
- `ClaudeLLM` — the Messages API. Claude Opus 5, adaptive thinking, `effort: high`,
  structured output against a per-pass JSON Schema, **streaming** (generation runs
  long enough that non-streaming trips the SDK's HTTP timeout). Server-side refusal
  fallback is on by default so a refusal on one pass doesn't abandon a nearly-done
  generation.
- `ClaudeCodeLLM` — the same prompts billed to a Claude subscription via the Claude
  Code CLI. Slower per pass and noisier in tokens; it is the backend for someone
  with a plan but no API credit.

The stack brief is byte-identical across passes and repair attempts so it stays a
cache prefix — keep it that way. Override with `PROTOPILOT_MODEL` /
`PROTOPILOT_EFFORT`; timeouts via `PROTOPILOT_TIMEOUT`; the Claude binary via
`PROTOPILOT_CLAUDE_BIN`.

## Known state — check before trusting a doc

**`NOTES.md` is the live parking lot** (open items, "resolved this session", and
what's highest value next). Read it before starting work; update it when you
resolve something.

It lived at `../proto-pilot-notes.md` until 2026-08-28 — outside every repo, at a
workspace root that is not a git repository. It was unbacked, and it was lost. The
file here is a reconstruction from what this guide and the README already record;
anything that existed only in the old file is gone.

`docs/` holds long-form docs that are neither rules nor design:
[`docs/hosted.md`](docs/hosted.md) captures the hosted-public-service idea — not a
plan, and it would reclassify this repo from an internal instrument to a minor
product.

The README's **Status** section was stale in four known ways and was corrected on
2026-08-30, when this repo was prepared to go public: it claimed the `passes/`
prompts had never run live (they have), and omitted Pillow, the browser stage,
and the venv requirement. It is now the accurate list of gaps — keep it that way,
because it is the first thing a stranger reads.

Two traps worth knowing:

- **`proto ls` calls `prune()`, which deletes registry entries whose directory is
  missing.** Running `ls` merely to look at the list is what emptied the whole
  registry when `/tmp` was wiped. Don't point generated prototypes at a volatile
  scratch dir.
- **Orphaned Docker volumes survive a deleted tree.** `registry.delete` drops
  them; a tree removed any other way leaks one.

Real gaps in the pipeline, in the order they bite: `auth: "password"` is accepted
by the spec and implemented by no pass; `jobs` and `external_apis` are recorded and
ignored; the offline baseline ignores `spec.screens` and always generates its own
CRUD set (only the model path honours custom screens).
