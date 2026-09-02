# proto.pilot

A framework for prototyping ideas with agents.

> **Before making changes**: load docs on-demand via `docs/README.md` or `.github/DOCS_INDEX.md`.
> Never load the whole tree — a typical task needs one or two documents.

This file is the one every agent reads. `AGENTS.md` is the convention shared
across tools; `CLAUDE.md` is a pointer to it rather than a copy, because two
files stating the same rules drift within the week and the copy that is wrong is
the one that happens to get loaded. Put rules here, never there.

The detailed rule files are in `docs/rules/`, and they are plain markdown with
no tool-specific syntax. They sit under `docs/` rather than in a vendor
directory on purpose: nothing loads them automatically for any agent — they are
read because this file names them — so putting them somewhere tool-branded
would have been a claim that was never true, and one that made the conventions
look optional to anybody not using that tool.

---

## Quick Start

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
.venv/bin/pre-commit install --install-hooks
./pp check pre-push   # everything CI blocks on; green on a fresh tree
./pp test unit        # the fast suite
./pp check health     # can this checkout generate? (runs `proto doctor`)
```

These are rendered from the same source as the README's Setup block, and every
one of them exists. An earlier version of this file opened with `./pp setup`
and `./pp service up`, which the CLI has never implemented — and `setup`
could not be implemented, because the CLI cannot run until the install it would
be performing has already put `click` in the venv. A quick start that fails on
line one reads as user error at the exact moment a reader has no way to tell.

---

## Services

Nothing here runs as a long-lived service. The two things that listen on a
port are the optional front end and the *output* of the tool.

| Piece | Stack | Port | Purpose |
| ----- | ----- | ---- | ------- |
| `proto serve` | FastAPI + Jinja | 7000 | A web face on `proto new`. A second *caller* of the pipeline, never a second implementation of it |
| a generated prototype | FastAPI + Postgres, in Docker | first free from 8080 | The output. One compose project per tree, named `<slug>_<path-hash>` |

The generated prototype's stack is fixed and is not this repo's stack — see the
invariants below before changing anything under `skeleton/`.

---

## What this repo is

`proto new "an idea"` turns a sentence into a running Dockerised FastAPI app:
idea -> typed `spec.json` -> skeleton copied -> five generation passes ->
`docker compose up` -> observed -> bounded repair loop -> a URL. The output is a
thing to look at this afternoon and throw away, explicitly not a production
starting point.

**[`README.md`](README.md) is the design document.** It explains the five
load-bearing decisions and why each exists. Read it before changing pipeline
behaviour; the reasoning there is what keeps this from degenerating into a
stack-picking code generator.

### Naming: two "skeletons" in one tree

`skeleton/` is the fixed application tree copied into every *generated
prototype*. **skeletor** (a sibling checkout at `../skeletor`, not part of this
repository) is the generator that produced *this
repository's* shell. They are unrelated, and the collision is unfortunate but
load-bearing in both directions — do not rename either to resolve it, and do
not confuse `skeleton/` (product data) with `.skeletor.json` (repo metadata).

### Invariants — do not soften these

These are the guarantees that make generated output trustworthy. Each was a
deliberate decision, not an accident of implementation.

- **The model can only write five paths**: `app/models.py`, `app/routes.py`,
  `app/seed.py`, `app/templates/*.html` (except `base.html`), and
  `tests/test_smoke.py`. Everything else is refused by `protopilot/files.py`
  *before it reaches disk*. Model output is data, not authority — the parts of
  the tree known to work are exactly the parts the model must not be able to
  touch. Widening this list is a significant design change, not a convenience
  fix.
- **The stack is fixed, not chosen.** FastAPI, server-rendered Jinja,
  SQLAlchemy 2.0, Postgres. No JS build step, no CDN, no migrations. A
  generator that picks a stack per idea produces N unrunnable variants.
  **`skeleton/` is copied byte for byte, never generated**, so it is debugged
  once rather than once per prototype.
- **Tests are generated before the code they test.** Pass order is
  `schema -> smoke -> seed -> routes -> ui`. Smoke tests come second, from the
  spec, when no route exists yet — so they describe what was *asked for*, not
  what got built. Reordering the passes breaks this.
- **Each pass reads the previous pass's real source**, never a description of
  it. UI goes last and receives `routes.py`, because a template referencing a
  context key no route passes is the most common way a generated app 500s.
- **Nothing is handed back unobserved.** `verify.py` brings the stack up, waits
  on `/healthz` (which checks the DB, so it stays red while Postgres boots),
  runs the smoke suite inside the container, and captures logs. Three repair
  attempts, then a **floor**: the tree is handed back anyway with a
  `RUNBOOK.md` naming the red stage, the last error, and what was tried. A
  known-broken prototype beats a mystery, and both beat a loop that never
  terminates.
- **The shrink guard**: if a repair shrinks the smoke suite, the file is
  reverted. Green because there is nothing left to fail is the one failure mode
  nobody would otherwise notice.

### The offline baseline is the test suite

Every pass has two implementations: a prompt, and a deterministic generator in
`protopilot/baseline.py`. `--offline` runs the second — no API calls, no key, a
plain CRUD app.

It exists for three reasons, in increasing importance: a fast free path to a
skeleton; the worked example each prompt is written against; and **it is what
the test suite runs**, so the whole pipeline is exercised on every commit with
no key and no Docker daemon. A pipeline that can only be tested with a network
call and a credit card stops being tested.

**When adding or changing a pass, the baseline implementation is part of the
change, not a follow-up.** `proto add` is the exception: it needs the model,
because the baseline cannot read a change request.

### Layout

| Path | What |
| ---- | ---- |
| `protopilot/passes/` | One module per pass — `intake`, `clarify`, `models`, `smoke`, `seed`, `routes`, `ui`, `repair`; `_shared.py` holds the stack brief |
| `protopilot/files.py` | The write guard — the five-path allowlist |
| `protopilot/verify.py` | Boot, health-wait, smoke run, log capture |
| `protopilot/baseline.py` | The deterministic offline implementation of every pass |
| `protopilot/llm.py` | `LLM` Protocol + three backends |
| `protopilot/registry.py` | Tracked prototypes — see the `prune()` trap in `NOTES.md` |
| `skeleton/` | Copied byte-for-byte into every generated app |
| `cli/`, `scripts/` | This repo's own tooling — never shipped to a user |

### Known state

**[`NOTES.md`](NOTES.md) is the live parking lot** — open items, "resolved this
session", and what is highest value next. Read it before starting work; update
it when you resolve something. It is not superseded by `docs/TODO/`: a
paragraph of context that is not yet a plan belongs there, and a plan belongs
in `docs/TODO/`.

---

## Critical Rules

Numbered so they can be cited in review and in commit bodies. Each one exists because
something went wrong without it — keep the reason attached when you edit one.

### 1. Read the Config From One Place

Never re-derive a value that already has an owner. Feature parameters, schedules, windows,
sort orders, and version numbers are each resolved by exactly one module, which every
consumer **imports**. Two copies of a rule drift within the week, and the copy that is wrong
is always the one being read.

### 2. Test Code Before Delivery

Execute and verify in the correct environment before handing off. "It should work" is not a
result. If the code runs in a container, run it in that container.

### 3. Lint Before Committing

Run the blocking set after any change — see `docs/rules/python.md`. CI blocks on
all of it, and the type check is **whole-project**: one stale error anywhere blocks every
commit, not just commits near it.

### 4. Run Tests Before Committing

`./pp test <suite>` — all tests must pass. Never commit half-working code. Test files
self-register via a module-wide `pytestmark` marker; there are no registries to update.
Full rules in `docs/rules/testing.md`.

### 5. Keep the CLI in Sync

Adding or changing a script means updating the `cli/` package in the same commit. A script
nobody can discover is a script nobody runs.

### 6. Commit Strategy — Frequent, Logical, Bundled

One commit per logical idea, all of its files bundled into that commit. Conventional format,
one subject line. Full rules in `docs/rules/commits.md`.

### 7. Commit Autonomously — Push When Complete

Commit freely as each logical unit lands (tests green, conventions followed) — **no need to
ask permission**. Once the requested work is fully complete and all checks pass, push the
branch autonomously. Don't push half-finished work mid-task. **Force-push is permitted on
your own unreviewed branch** — but never on `develop` or `main`, and
never from an unattended agent.

**Base branch: `develop`.** New branches are cut from it; every PR targets it.
Never commit directly to `main`.

**In this repo, committing directly to `develop` is normal** — no branch, no PR.
That is a standing decision made while proto.pilot is private and single-author,
and it is the same trade the workspace guide names in the other direction: *two
branches are what an audience costs*. `develop` and `main` already exist because
the repo is being prepared to go public, but while nobody outside can clone it
there is no second reader for a PR to inform. **The day the repo goes public,
this paragraph expires** and Rules 7 and 8 apply as written. Do not extend the
exemption to `main`, which stays the released ref and is only ever reached by
merge.

### 8. Open Every PR as a Draft

(Applies when a PR is opened at all — see the exemption in Rule 7.)

`gh pr create --draft`. Mark it ready only when you believe it is green.

The expensive CI jobs are gated on draft status: a draft PR runs the cheap gate job alone.
Nothing is un-gated by this — GitHub blocks merging a draft regardless, and marking it ready
fires `ready_for_review`, which runs the full set before it can merge.

**Flip back to draft before pushing a fix** — `gh pr ready --undo <n>`. A `synchronize` event
on a *ready* PR re-runs everything that PR earns; iterating in draft pays once, when the work
is actually done.

### 9. Docs Are Part of the Change, Not a Follow-Up

Decide in planning which docs a change will invalidate, and update them in the same PR. A
plan that is finished **moves** from `docs/TODO/` to `docs/implementations/` — never copies.
Both indexes are generated; never hand-edit them. Full rules in `docs/rules/docs.md`.

### 10. No Temp Files in the Project Root

Use tool-based file editing. If a scratch file is genuinely necessary it goes in `tmp/`
(gitignored). `tmp/` is for things nothing will want next week — the record of what
ran is not a temp file and does not go there. See Rule 14.

### 11. Anything That Stands Up the Stack Stays in Sync

If two files describe the same environment — a dev compose file and a CI one, two workflows
that both boot the stack, a host script that mirrors a CI action — **a drift check owns that
pair**, and intended divergences are recorded in an allowlist with a written reason.

Do not hand-copy setup between them. Enrollment in the drift check is **automatic** (anything
matching the pattern is checked); it is deliberately not a registry, because forgetting to
update a registry is the same bug the check exists to catch.

### 12. Found an Unrelated Bug? Capture It — Don't Widen Your Scope

A bug you hit that is **not** what you were asked to work on goes to the capture command, not
into your current change and not into a sentence the user will lose when the session ends:

```bash
./pp bug "<one-line summary>" \
    --finding "<path:line + what is wrong>" \
    --reproduce "<exact command; observed vs expected>" \
    --scope "<what is in, what is explicitly out>" \
    --acceptance "<assertions; the command that must pass>"
```

All four sections are required — a capture missing any of them is refused, because a capture
nobody can act on is a note, not a task. Mention what you captured in your response so the
user can kill it if they disagree.

### 13. One Voice, Two Streams

Nothing prints a status symbol or picks a stream by hand. Every emission goes
through `scripts/output.py`: `ok` / `fail` / `warn` / `skip` / `step` to **stderr**,
`line` / `emit` to **stdout**.

The split is what makes `--json` free — the payload has the stream to itself, so
a machine-readable flag is one extra emit rather than a second code path. Every
`scripts/check_*.py` supports `--json` and answers on every path, including the
ones that pass. `pp check output` enrols every file under `cli/` and
`scripts/` by pattern; exceptions go in `scripts/output_allowlist.yaml` with a
reason. Full rules in `docs/rules/output.md`.

### 14. Agent State Goes Through the Resolver

Transcripts, ledgers, per-job memory and the payloads agent stages read live under
`~/skyrow.labs/sl-agent-logs/proto-pilot/`, never in this checkout. A record that
lives in a working tree is one `git clean -fdx` from gone, and is invisible to every
other worktree of this repo.

Reach it with `state_dir()` from `scripts/paths.py`. **Never a literal path, and never
a second definition of one.** The second is the one that looks fine in review: split
the resolver and a test can point the write at a scratch file while the read still
finds the live one — it passes, and proves nothing. `tests/test_state_paths.py` holds
this line; run it rather than trusting the rule.

`state_dir()` being a function does not help a caller that freezes it: a module-level
`LEDGER = state_dir(...)` is evaluated at import, so a fixture setting the environment
runs too late and the suite writes to the live record with every test green. Resolve at
the point of use, or set the variable at `conftest.py` import time.

---

### 15. Two CLIs, Two Audiences — Never Merge Them

**`proto` is the product.** Installed onto a user's PATH via
`[project.scripts]`, run from wherever they want a prototype, implemented in
`protopilot/`. **`./pp` is this repository's own tooling** — gates, generators,
scheduled jobs — implemented in `cli/` and `scripts/`, run from the repo root,
never shipped.

They keep separate env prefixes for the same reason: `PROTOPILOT_*` configures
the product, `PP_*` configures the repo. A single `--help` serving both a person
generating an app and a person maintaining the generator serves neither, and the
first thing that goes wrong is `proto check docs` appearing in a user's shell.

Rule 5 ("keep the CLI in sync") is about `./pp`. A new *product* command belongs
in `protopilot/cli.py` and in the README's command table.


### 16. A Reason That Names a Broken Thing Has an Expiry Nobody Wrote Down

When you fix a defect, **everything that was justified by that defect is now
justified by nothing.** The dangerous case is the one where the conclusion
survives: nothing goes red, so nobody re-reads the reason, and a workaround
quietly persists as though it were a design.

The tell is whether a stated reason is a **workaround** or an **intention**:

- *"Pinned to the release branch because an unpinned badge would read no-status
  forever"* — a workaround. It was falsifiable by a fix somewhere else, and a
  fix somewhere else duly falsified it.
- *"Pinned to the release branch because a badge is a claim about what was
  released"* — an intention. It survives anything.

Both sentences defend the same line of config. Only one of them is still true
after the push trigger is fixed.

So: when a reason names something broken, absent or unimplemented — ours or a
dependency's — say so explicitly and say what changes if it is fixed. See
`containers.py::known_paths` for the shape. And when you close a defect, grep
for what cited it. This session produced two instances in one afternoon: a
neighbour's badge rule, and this repo's own README, which still listed a gap
Phase 2 had closed an hour earlier.

---

## Documentation Reference

Load on-demand only. Full mapping in `.github/DOCS_INDEX.md`.

| Topic                      | Doc                              |
| -------------------------- | -------------------------------- |
| Architecture / design      | `docs/ARCHITECTURE.md`           |
| Dev setup / CI / testing   | `docs/DEVELOPMENT.md`            |
| CLI commands               | `docs/CLI.md`                    |
| Unfinished work (the tank) | `docs/TODO/README.md`            |
| Completed work (archive)   | `docs/implementations/README.md` |
| Scheduled jobs / automation | `docs/AGENTIC_AUTOMATION.md`     |
| The design argument        | `README.md`                      |
| Live parking lot           | `NOTES.md`                       |
| Hosted-service idea        | `docs/hosted.md`                 |

<!-- Add a row per doc as it is written. `pp check docs` fails on a doc
     registered in neither this table nor .github/DOCS_INDEX.md — an
     unregistered doc is one no agent will load, which is the same, from the
     agent's point of view, as a doc that does not exist. -->

---

## Commit Types

`feat` / `fix` / `perf` / `docs` / `refactor` / `chore` / `ci` / `test` / `build`

> `docs:` for `docs/**` changes only — never `feat:`. Release Please owns `CHANGELOG.md`.
