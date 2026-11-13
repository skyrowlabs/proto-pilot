# proto.pilot

A framework for planning ideas with agents.

> **Before making changes**: load docs on-demand via `docs/README.md` or `.github/DOCS_INDEX.md`.
> Never load the whole tree — a typical task needs one or two documents.

This file is the one every agent reads. `AGENTS.md` is the convention shared
across tools.

`CLAUDE.md` is a pointer to this file rather than a copy, because two files
stating the same rules drift within the week and the copy that is wrong is the
one that happens to get loaded. Put rules here, never there.

The detailed rule files are in `docs/rules/`, and they are plain markdown with
no tool-specific syntax. They sit under `docs/` rather than in a vendor
directory on purpose: nothing loads them automatically for any agent — they are
read because this file names them — so putting them somewhere tool-branded
would have been a claim that was never true, and one that made the conventions
look optional to anybody not using that tool.

---

## Quick Start

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt && .venv/bin/python scripts/install_project.py
.venv/bin/pre-commit install --install-hooks && .venv/bin/python scripts/git/install_merge_drivers.py
./pp check pre-push   # every host-runnable CI gate; green on a fresh tree
./pp test unit        # the fast suite
./pp check health     # can this checkout plan? (runs `proto doctor`)
```

**Every one of them exists** — that is the claim this paragraph is making, and it
is the one worth checking. Every line but the last is shared with the README's
Setup block, and what keeps them in step is `tests/test_setup_blocks_agree.py`
rather than the generator, which left. The first line ends by installing
proto.pilot itself with every extra, through the same script CI runs, because
the unit suite imports the package. The last line belongs to this file alone. An
earlier version of this file opened with a `setup` and a
`service up` subcommand, which the CLI has never implemented — and `setup`
could not be implemented, because the CLI cannot run until the install it would
be performing has already put `click` in the venv. A quick start that fails on
line one reads as user error at the exact moment a reader has no way to tell.

---

## Services

Nothing here runs as a service and nothing listens on a port. `proto` is a
command that writes a folder of text and exits.

---

## What this repo is

**Planning is the product**, since 2026-11-06; the argument is in
[`docs/ideas/plans-first.md`](docs/ideas/plans-first.md). `proto plan "an idea"`
turns a sentence and a little direction into a folder of text plans: scope ->
an outline a person reviews -> typed links between topics -> risks, unknowns and
decisions -> first steps -> dreams -> checks on the structure, never the truth ->
bounded repair -> a tree handed back green or with a `RUNBOOK.md`. `proto dream`
adds to the pool of dreams and settles one. Research runs one web-only call per topic
on the `claude-code` backend; a source counts only if the run's own transcript shows it
fetched, and a plan made without research is stamped *Not researched*.

**Dreams are guesses, not findings.** They stay in `dreams.md`, never in a topic
file, and only a person promotes one, through `proto dream promote`. A dream
never costs a plan, and it extends only a plan that is green.

**Prototyping was removed on 2026-11-11.** `proto new`, both targets and both
front ends left the tree; the tag `prototyping-final` is the last commit that
holds them. Nothing here generates, runs or verifies an app, and nothing calls
Docker.

**[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) holds the reasoning.**
[The plan pipeline](docs/ARCHITECTURE.md#the-plan-pipeline) explains planning, and
[Critical Patterns](docs/ARCHITECTURE.md#critical-patterns) lists what a change
can break without anything going red. Read the first before changing a pass.

### Invariants — do not soften these

These are the guarantees that make a plan trustworthy. Each was a deliberate
decision, not an accident of implementation.

- **Model output is data, not authority.** A pass's `apply` reads only the fields
  it names, so none but `research` can set `researched`, `sources` or a finding,
  and no pass can promote a dream or remove the *Not researched* stamp. The only
  model text that reaches a file name is a checked slug.
- **The process that answers is isolated too, and that takes its own guard.** On
  the `claude-code` backend the answer comes from `claude --print`, which runs
  with Read, Write, Bash and the caller's working directory unless told
  otherwise. `llm.ISOLATION` is what tells it otherwise: no tool and no MCP
  server. The research call is the one exception, and holds
  `RESEARCH_ISOLATION`: web search and fetch, no write, no shell, no MCP, checked
  against every init event and every tool use in the stream. It writes no file;
  its output is findings, which are data. A change to either constant is a
  change to this rule.
- **A source counts only if this run's transcript shows it fetched.** The ledger
  is redrawn from the transcripts on every read, so a hand edit cannot upgrade a
  plan, and a plan made without research is stamped *Not researched*.
- **Verified means the structure holds, never that the plan is true.** The green
  line claims only what held, and a check with nothing to read is reported as
  that and never counts as passed.
- **Nothing is handed back unverified without saying so.** Three repair attempts
  that can change links and steps and nothing else, then a **floor**: the tree
  is handed back anyway with a `RUNBOOK.md`, *Not verified* banners and exit 1.
  A known-broken plan beats a mystery, and both beat a loop that never
  terminates.
- **The shrink guard**: a repair that removes a healthy step or a real
  dependency, or leaves more wrong than it found, is thrown away. Green because
  there is nothing left to fail is the one failure mode nobody would otherwise
  notice.
- **Dreams are guesses, and only a person promotes one.** A dream never reaches
  a topic file, never costs a plan, and extends only a plan that is green.

### The offline baseline is the test suite

Every plan pass has two implementations: a prompt, and a deterministic twin
that slices the plan `protopilot/plan/baseline.py` builds. `--offline` runs the
second — no API calls, no key, the same bytes on every run.

It exists for three reasons, in increasing importance: a fast free path to a
plan's shape; the worked example each prompt is written against; and **it is
what the test suite runs**, so the whole pipeline is exercised on every commit
with no key and no network. A pipeline that can only be tested with a network
call and a credit card stops being tested.

**When adding or changing a pass, the offline twin is part of the change, not a
follow-up.**

### Layout

| Path | What |
| ---- | ---- |
| `protopilot/llm.py` | `LLM` Protocol + three backends |
| `protopilot/plan/` | `proto plan` and `proto dream`. `passes/` holds its model passes, research, repair and the dream passes among them, and `pipeline.py` runs them; `model.py` is `plan.json`, the truth; `render.py` draws the markdown from it; `verify.py` checks structure, never truth, and a plan still red is handed back with a `RUNBOOK.md`; `lenses.py` is the fixed lenses as data, `dreaming.py` is the pool's rules, and `ledger.py` reads what research fetched from its transcripts — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#the-plan-pipeline) |
| `protopilot/registry.py` | Tracked plan trees, each a plan by its own files — see the `prune()` trap in `docs/NOTES.md` |
| `protopilot/jobs.py`, `protopilot/progress.py` | The job a plan runs on and its typed events, and the pure fold of those events |
| `protopilot/runner.py` | The subprocess seam the `claude-code` backend runs through |
| `cli/`, `scripts/` | This repo's own tooling — never shipped to a user |

### Known state

**[`NOTES.md`](docs/NOTES.md) is the live parking lot** — open items, "resolved this
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

CI jobs are gated by cost: a draft PR carrying code runs the cheap ones and skips the
expensive ones, and a docs-only PR runs the gate and the unit suite whether it is draft or
ready — that is the other rule, and it decides first. `.github/scripts/docs-only.cjs`
decides both, and is the only place that does; `ci.yml` says which job is in which class.

This named the five jobs by name for one release, which is a claim about *your* workflow
rather than about the rule — a tree that had renamed or dropped one got a sentence that was
more precise and less true than the vague one it replaced.
Nothing is un-gated by this — GitHub blocks merging a draft regardless, and marking it ready
fires `ready_for_review`, which re-runs what the PR earns. **Leaving draft does not by itself
escalate anything**: the classifier returns the same verdict for a draft carrying code and for a
ready code change into `develop`, so in a two-branch tree the expensive jobs stay
`skipped` either way and branch protection accepts that. A code change entering
`main` earns the full set, and so does every code change in a tree where those two
branches are the same. Nothing reaches a release un-integrated regardless, because the merge is a
push and a push earns everything.

**Flip back to draft before pushing a fix** — `gh pr ready --undo <n>`. A `synchronize` event
on a *ready* PR re-runs everything that PR earns; iterating in draft pays once, when the work
is actually done.

**`./pp pr land` is the end of that loop as one command**: `check pre-push`, push, the
pull request opened as a draft (or found) and marked ready, its checks waited for on the head
commit, and the pinned `gh pr merge <n> --merge --match-head-commit <sha>` printed. It stops
there, because a merge is a person's call; `--merge` makes that call on the command line, and
then watches the base branch's push runs on the merge commit too.

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

**An allowlist entry expires, and the check says so.** Every allowlist here is re-read against
the thing it exempts on every run: an entry whose target was fixed has outlived its reason, and
one whose target left the tree is worse — the name can come back for something else and arrive
pre-exempted, which is an exemption nobody made. When a check reports a stale entry, **delete
it**; do not rewrite the reason to keep it alive. Every allowlist in this repository is read by
`scripts/allowlist.py`, which is also where that rule is written down.

### 12. Found Something Unrelated? Capture It — Don't Widen Your Scope

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

**If it is not a defect, it is the other lane.** `pp bug` demands `--reproduce`, and for
"rename this helper", "add the missing test", "delete the flag nothing reads" there is no
honest answer to it — so you either write something false or you file nothing. That is the
same loss one size down:

```bash
./pp task "<one-line summary>" \
    --what "<the change, in terms of the files it touches>" \
    --why "<what is worse today because this has not been done>" \
    --acceptance "<assertions; the command that must pass>"
```

`--why` is not decoration. It is what stops a task queue becoming a wish list.

Both lanes are labels, and `scripts/lanes.py` is the registry that owns them. The editor's
issue views are generated from it — see `scripts/gen_vscode_queries.py` — so a queue you can
file into is a queue you can see. Adding a lane means adding its intake in the same change;
`tests/test_lanes.py` refuses a lane nothing files into, because a pane that is empty forever
looks exactly like one you have kept clear.

### 13. One Voice, Two Streams

Nothing prints a status symbol or picks a stream by hand. Every emission goes
through `scripts/output.py`: `ok` / `fail` / `warn` / `skip` / `step` to **stderr**,
`line` / `emit` to **stdout**.

The split is what makes `--json` free — the payload has the stream to itself, so
a machine-readable flag is one extra emit rather than a second code path. Every
`scripts/check_*.py` supports `--json` and answers on every path, including the
ones that pass. `pp check output` enrols every file under `cli/` and
`scripts/` by pattern; exceptions go in `scripts/output_allowlist.yaml` with a
reason, and are dropped when they stop exempting anything (see Rule 11). Full
rules in `docs/rules/output.md`.

### 14. Agent State Goes Through the Resolver

Transcripts, ledgers, per-job memory and the payloads agent stages read live under
`state_dir()`, never in this checkout. A record that lives in a working tree is one
`git clean -fdx` from gone, and is invisible to every other worktree of this repo.

Where that resolves to is `scripts/paths.py`'s answer and is deliberately not written
here: a path in this file is a second definition, and this rule is the one forbidding
those. Run `python -c "from scripts.paths import state_root; print(state_root())"` —
`state_root()` rather than `state_dir()` because it reports **which** of the override
and the default answered, and a path alone cannot. When a run writes somewhere
unexpected that is usually the whole question, and a bare path leaves you to guess it.

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
`[project.scripts]`, run from wherever they want a plan,
implemented in `protopilot/`. **`./pp` is this repository's own tooling** — gates, generators,
scheduled jobs — implemented in `cli/` and `scripts/`, run from the repo root,
never shipped.

They keep separate env prefixes for the same reason: `PROTOPILOT_*` configures
the product, `PP_*` configures the repo. A single `--help` serving both a person
planning an idea and a person maintaining the tool serves neither, and the
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

**The safest state is not one reason. It is both reasons, with the perishable
one labelled.** You cannot always avoid citing a broken thing — sometimes it
genuinely is why you did it — but you can refuse to let it be the only reason on
the page. State the durable reason too, mark which one is load-bearing, and the
day the broken thing is fixed nobody has to re-derive whether the decision still
holds.

When you close a defect, grep for what cited it. Two things make that harder
than it sounds, and both bit in the same afternoon:

- **The distance that matters is audience, not files.** This repo's README still
  listed a gap that had been closed an hour earlier, one commit away, because
  `docs/NOTES.md` is the parking lot I have the habit of updating and the README is
  for a stranger. Check the widest-audience document, not the nearest one.
- **No test can do the semantic half.** Nothing can read "because X is broken"
  and go check whether X is still broken. `tests/test_docs_name_live_code.py`
  catches the mechanical cousin — a reference doc naming a callable this repo
  used to define — and that is the whole of what a gate can offer here. The rest
  is a reading pass.

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
| The design argument        | `docs/ARCHITECTURE.md`           |
| Live parking lot           | `docs/NOTES.md`                  |
| Captured ideas (not scheduled) | `docs/ideas/README.md`       |
| Reports (anchored to releases) | `docs/reports/README.md`     |

<!-- Add a row per doc as it is written. `pp check docs` fails on a doc
     registered in neither this table nor .github/DOCS_INDEX.md — an
     unregistered doc is one no agent will load, which is the same, from the
     agent's point of view, as a doc that does not exist. -->

---

## Commit Types

`feat` / `fix` / `perf` / `docs` / `refactor` / `chore` / `ci` / `test` / `build`

> `docs:` for hand-written prose wherever it lives — this file and `README.md`
> included — never `feat:`. The path is the hint, not the test; `docs/rules/commits.md`
> holds the rule. Release Please owns `CHANGELOG.md`.
