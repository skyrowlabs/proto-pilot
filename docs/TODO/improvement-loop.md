---
title: "The Improvement Loop"
slug: improvement-loop
shelf_status: planned
priority: high
updated: 2026-09-03
tags: [loop, verify, docker, agent, safety]
summary: "Let a prototype be told to keep getting better, with a ratchet that reverts any iteration leaving it less green than it found it."
---

# The Improvement Loop

> **Status**: 🔴 Planned — designed, unreviewed
> **Shelf-Status**: planned
> **Priority**: High — it is the second of the three things asked for when this
> tool was reframed, and the only one still unbuilt
> **Queue-Order**: unset until it is `ready`

## The pivot barely touches this, and that is worth stating

[`sketches-not-scaffolds`](../ideas/sketches-not-scaffolds.md) changes the output
medium. **This plan is almost entirely medium-independent** and stays `planned`
rather than blocked, unlike [drawing-freedom](drawing-freedom.md), whose every
rung was a browser capability.

What survives untouched: the ratchet argument, git as the revert mechanism, the
pass machinery and write guard as the thing that changes files, every human
control, and the whole `Dropped, and why` section.

What needs one edit when a second target exists: **two of the four rails are
named in web vocabulary.** `templates` counts `app/templates/*.html`, and
`screens served` compares `checkable_paths(spec)` against routes that answer. A
terminal app has screens and no routes. The *rails* are right — "did a screen
stop existing" is the question on any medium — so this is a target-owned
implementation behind the same names, not a redesign. The plan already says the
rails are "a tuple in one place so a fifth is a line, not a refactor"; that
property is what makes this cheap, and it should be honoured rather than
special-cased.

### It is not the loop the pivot asked for, and conflating them would be a mess

This is the trap. The pivot's own framing is *"iterate to this idea and show me
a prototype"*, which sounds exactly like this plan and is a **different loop**:

| | This plan | The pivot's loop |
|---|---|---|
| Who drives | the model, unattended | a person, watching |
| Turn length | minutes to hours | seconds |
| What it optimises | measurable rails | what the person just said |
| Safety mechanism | the ratchet, because nobody is looking | the person, who is looking |
| Failure it prevents | a random walk with a commit bit | none — you see it and say so |

**A ratchet is what you build when nobody is watching.** Put one in an
interactive loop and it starts reverting changes the person asked for, because
"make the list denser" legitimately removes a template. So the pivot's loop is
closer to `proto add` plus a TUI than to `proto improve`, and it should not
reuse the rails.

Both are wanted. They are separate plans and the vocabulary must not merge —
the moment `improve` grows a `--watch` flag, this plan's safety argument stops
being true and nothing will say so.

## Problem

`proto new` is a one-shot. It produces a running prototype and stops, and the
only way to change what it produced is `proto add "<change>"`, which re-runs
intake, amends the spec, and regenerates **every** file from it. That is the
right shape for "add a vet visit to this tracker" and the wrong shape for
almost everything else, because it makes a small improvement cost a whole-app
rewrite and gives the model a fresh opportunity to change its mind about
things nobody asked about.

What is missing is the thing a person actually wants after looking at a
prototype for thirty seconds: **"keep making this better while I do something
else."** Not a rewrite, not a new spec — a sequence of small, bounded changes
to the app that already exists, each one checked before it is kept.

The reason that is not simply "run the model in a loop" is the failure mode it
has. An unratcheted loop makes the app worse roughly as often as better, and
the worse cases are not obvious: a template that renders but drops a column, a
test deleted because it was failing, an empty state that stopped being handled.
Left running overnight, a loop like that converges on a tree that boots and
does nothing, and every intermediate state looked fine to the thing producing
it. **A loop without a ratchet is a random walk with a commit bit.**

## The ratchet already exists, at the smallest possible scale

This is the part not to reinvent. `build.drive_to_green` already refuses one
specific regression:

```python
after = _test_count(ctx.project_dir)
if before and after < before:
    (ctx.project_dir / SMOKE_PATH).write_text(original)
    log(f"    rejected: repair cut the smoke suite from {before} to {after} tests")
```

One file, one metric, one pass, with the previous content held in a local
variable. It is the correct idea at a scale where it needed no machinery, and
the whole of this plan is widening it: **the whole tree, a measured baseline,
many iterations, with git as the revert mechanism instead of a string in
memory.**

Which is nearly free, because every generated tree is already a git repository
— `proto new` runs `git init` unless told not to. There is nothing to build to
get "revert this iteration"; there is a `git reset --hard` and a decision.

## Approach

An **iteration** is: measure, change one thing, measure again, keep or revert.
Never anything else. The loop is the iteration run N times with stop
conditions.

### The measure

A `Snapshot` of a generated tree, taken by the existing verifier plus a few
cheap counts. Greenness is not one bit, because one bit cannot tell "still
green" from "still green and now missing a page":

| Rail | Source | Rule |
|---|---|---|
| verification | `Verifier.verify()` — build, health, tests | must be `ok` |
| smoke tests | `build._test_count` | must not decrease |
| screens served | `checkable_paths(spec)` vs routes that answer | must not shrink |
| templates | `app/templates/*.html` present | must not shrink |

An iteration is **kept** only if every rail is at least as good. Anything else
is reverted, recorded with a reason, and the loop continues. The rails are a
tuple in one place so a fifth is a line, not a refactor — and so the reason a
revert happened is a rail name rather than a summary somebody wrote.

Deliberately **not** a rail: anything unmeasurable without a judgement call —
"looks better", "more idiomatic", page weight, boot time. A rail that needs an
opinion is a rail that will be argued with at 3am by a loop that cannot argue.

### What does the changing

**The pass machinery, not a free agent.** `protopilot/files.py` already
enforces that a model may write only five paths, and that guard is one of the
five load-bearing invariants in the README. An agent with a shell can edit the
Dockerfile, the compose file or `requirements.txt`, and an improvement loop
with that power is a way to end up debugging a stack nobody chose — which is
the exact thing the fixed skeleton exists to prevent.

So an iteration is a **pass**: `protopilot/passes/improve.py`, given the spec,
the real current source, and the previous iterations' notes, returning file
contents through the same schema and the same write guard as every other pass.
The autonomy question is then already answered by machinery that exists,
rather than by a policy in a comment.

This also means the loop inherits the rule every pass has: **it ships with an
offline baseline in the same change**, or CI cannot see it.

### What the human controls

The ask was for controls, and these are the ones that matter — each is a thing
somebody would actually want to say, not a knob for its own sake:

- **How many.** `--iterations N`, bounded, small default. There is no unbounded
  mode. A loop you cannot describe the end of is a loop you cannot leave.
- **What to aim at.** `--goal "make the list page worth looking at"`, optional.
  Empty means the pass picks, which is the mode being asked for.
- **When to stop early.** `--until-dry`: stop after K iterations that changed
  nothing or were reverted. Discovery loops end when they stop finding things,
  not when a counter runs out.
- **Whether to keep going after a revert.** Default yes; a revert is
  information, not a failure.
- **What it did.** `proto improve --log <project>` reads the tree's own git log
  and the per-project ledger. Every kept iteration is one commit with the rail
  measurements in the message, so `git show` is the audit trail and nothing has
  to be trusted.

## Phase 1 — The measure, and the existing ratchet moved onto it

No loop yet. The thing that decides "at least as green" exists and is tested
before anything is allowed to act on it.

- [ ] `protopilot/quality.py`: `Snapshot` (the four rails), `take(project_dir,
      spec, verifier)`, and `Snapshot.regressions(previous) -> list[str]`
      naming the rails that got worse
- [ ] `drive_to_green`'s inline test-count check is replaced by the shared
      rail. One implementation, per the rule the last plan's Phase 6 landed —
      and this is the same shape, since it is currently the only ratchet and is
      about to have a second caller
- [ ] Snapshots are testable with no Docker: the verifier is already a
      `Verifies` protocol the suite drives with scripted results, and the other
      three rails are reads off the tree
- [ ] A test that a snapshot of a tree against itself has no regressions, and
      that deleting a template, a test, or a route each produce exactly the
      named rail

## Phase 2 — One iteration, kept or reverted

- [ ] `proto improve <project> --once`: snapshot, run the pass, snapshot,
      commit or `git reset --hard`
- [ ] Refuses a dirty tree, and says so. An iteration that cannot be reverted
      cleanly must not start — the whole safety argument is that revert works
- [ ] Refuses a tree with no git repository (`proto new --no-git`), naming the
      flag. Better than silently degrading to "changes are permanent"
- [ ] The commit message carries the rails and the goal, so the tree explains
      itself without the ledger
- [ ] Ledger at `.protopilot/improvements.jsonl`, reusing the `run_ledger`
      outcome vocabulary — `ok`, `failed`, `declined`, `skipped` — with
      `declined` first-class: an iteration that correctly found nothing worth
      changing is not a failure, and recording it as one teaches the operator
      to ignore the ledger

## Phase 3 — The `improve` pass, with its baseline

- [ ] `passes/improve.py`, writing only the five allowed paths, given the real
      current source rather than a description of it
- [ ] Its prompt asks for **one** bounded change and a one-line rationale. A
      pass that rewrites four files per iteration defeats the ratchet, because
      a revert then throws away the good change with the bad one
- [ ] The archetype's `brief()` reaches it, as it reaches the other code passes
- [ ] **The offline baseline**, and it must be a real improvement the ratchet
      accepts rather than a no-op: the honest candidate is adding a smoke test
      for a screen the suite does not currently assert on, which is
      deterministic, always available while any screen is unasserted, and
      raises a rail rather than merely not lowering one
- [ ] `--goal` is threaded through and the baseline ignores it, the same way
      the baseline ignores `theme`

## Phase 4 — The loop and its stop conditions

- [ ] `--iterations N` with a small default, `--until-dry K`, and a hard
      ceiling that is not a flag
- [ ] Interruptible: Ctrl-C between iterations leaves the tree at the last kept
      commit, never mid-iteration. The container is left as the loop found it
- [ ] `proto improve --log` reads the ledger and the git log together
- [ ] A summary at the end that says what was kept, what was reverted and which
      rail did the reverting — the numbers, not an adjective

## Phase 5 — The boundary, stated and enforced

- [ ] The loop may never touch the spec. Changing what the app *is* is
      `proto add`; changing how well it does it is this. Enforced by a test,
      because the temptation is real and the failure is silent
- [ ] It may never push, never touch a branch outside the generated tree, and
      never run in this repository. A test asserts the project directory is not
      proto-pilot's own root
- [ ] Docs: `docs/CLI.md`, and a `NOTES.md` entry for what it cannot yet do

## Acceptance

- [ ] `./pp check pre-push` green
- [ ] A generated tree, run for three iterations offline, ends with three
      commits, each verified, and its smoke suite larger than it started
- [ ] An iteration whose change deletes a template is reverted, the tree is
      byte-identical to before it, and the ledger names the `templates` rail
- [ ] A dirty tree and a non-git tree are both refused, by name
- [ ] Ctrl-C during a run leaves the tree at a commit, not mid-edit
- [ ] `proto improve` on this repository's own root refuses
- [ ] The improve pass writes nothing outside the five allowed paths, proven by
      the existing write guard rather than a new one

## Dropped, and why

**An unbounded or daemonised loop.** The ask was "set the AI to iterate", which
is satisfied by a bounded run you can start again. A background daemon needs
supervision, log rotation, a way to notice it has been failing for a week, and
a story for two of them running at once — all of which is real work in service
of not typing the command again.

**Letting the loop edit the spec.** It would let an iteration "improve" the app
into a different app, and the ratchet cannot catch that: every rail would be
green because the app it is now measuring is the one it just decided to build.
`proto add` exists for changing the spec, and it has a human checkpoint.

**A free agent with a shell.** Covered above. The write guard is the reason
this tool's output is debuggable at all, and an improvement loop is exactly
the situation where the guard stops being an inconvenience and starts being
the point.

**"Looks better" as a rail.** Unmeasurable without a judgement, and a loop
cannot hold one. If a subjective rail is ever wanted, it belongs to a human
looking at a screenshot, not to the ratchet.

**Merging or pushing anything.** The generated tree's git history is a record
for the person who owns it. A loop that pushes is a loop that can lose work
somebody else was holding.

**Reusing `scripts/reporting/agent_runner.py`.** It is the right machinery for
improving *this repository* — it has `fix_policy`, the argv contract and the
declined outcome — and the wrong machinery for improving a *generated* one,
which needs the write guard and the passes rather than a shell. The vocabulary
is worth borrowing; the runner is not.
