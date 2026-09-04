---
title: "The proto Console"
slug: proto-console
shelf_status: planned
priority: medium
updated: 2026-09-04
tags: [console, jobs, front-end, textual, ux]
summary: "A terminal front end for the tool itself — type the idea in one pane, watch generation in another — built as a second view over the job seam `proto serve` already paid for."
---

# The proto Console

> **Status**: 🔴 Planned — designed, unreviewed
> **Shelf-Status**: planned
> **Priority**: Medium — the default target has no front end but raw stdout,
> which is a gap the pivot opened rather than a pre-existing one
> **Queue-Order**: unset until it is `ready`

## What this is not

**This is not the `tui` target.** That is what `proto` *emits*, and it landed on
2026-09-04 as [the terminal target](../implementations/spec/terminal-target.md).
This plan is what `proto` *is*: the tool's own interface.

The distinction is load-bearing enough to constrain the code. `tui` already means
"the terminal target" in five places — `targets/tui.py`, `passes/tui/`,
`baseline_tui.py`, `verify_tui.py`, `tui_probe.py` — so **this front end must not
be called `tui` anything.** It lives in `protopilot/console/`. A reader who has
to work out which `tui` a module means will get it wrong eventually, and the two
are adjacent in every way that matters.

[`docs/ideas/sketches-not-scaffolds.md`](../ideas/sketches-not-scaffolds.md)
poses the fork this answers: *"Does `proto` become a TUI itself, or does it host
one? These are separable."* This is the **becomes one** half. Hosting the running
prototype in a pane is dropped below, deliberately.

## Why now, in one line

`proto serve` is pinned to `--target web` for a durable reason — it hands back a
link you click, and a terminal app has no link. Since 2026-09-04 the **default**
target is `tui`, so the default output has no front end at all. This is the
missing counterpart to the pivot, not a nicety on top of it.

## Problem

Generation is a twenty-one minute operation (`tui` mean wall clock, measured at
1278s in [the go/no-go](../reports/occasional/2026-09-04-terminal-target-go-no-go.md))
whose only interactive surface is a `[Y/n]` prompt in the middle. You type one
command, answer one question, and then watch a wall of text with no way to
change your mind, compare two ideas, or see where you are.

## The expensive half is already built

**`protopilot/jobs.py` is 112 lines and imports nothing but the standard
library** — `io`, `threading`, `uuid`, `contextlib`, `dataclasses`, `datetime`,
`typing`. No FastAPI, no Starlette. `protopilot/web/app.py` *imports* it and does
not own it.

So the hard part — decoupling generation from the terminal it was printing to —
was done for the web front end and is already under test. This plan is a second
view over `STORE`, not a rewrite of anything. **That is the whole reason it is
Medium and not High cost**, and if Phase 1 finds it untrue the estimate is wrong
rather than the plan.

## Phase 1 — Verify the two claims this plan rests on

Both are read out of the source, not measured. Both are cheap. Neither needs a
line of new product code.

- [ ] `protopilot.jobs` imports and `JobStore.run()` completes with **no web
      extra installed**. The claim is that the seam is standalone; the check is
      an import in an environment without FastAPI
- [ ] **`job.lines` grows *during* a run, not only at the end.** `run_generation`
      binds `log = job.log` and calls it, so lines should appear as passes
      complete — but `JobStore.run` also wraps the work in
      `redirect_stdout(buffer)` and flushes that buffer in its `finally`. Anything
      reaching the log via stdout rather than via `job.log()` therefore arrives
      **all at once, twenty-one minutes late**. Measure which of the two paths
      the real generation output actually takes
- [ ] Record the split: how many lines arrive incrementally, how many at the end
- [ ] **Gate:** if the output is mostly buffered, Phase 2 stops being an
      enhancement and becomes a prerequisite — a pane that is empty for twenty
      minutes and then fills is worse than the CLI it replaced, because the CLI
      at least prints as it goes

## Phase 2 — A structured event beside the text

- [ ] `Job` gains `events: list[dict]` **beside `lines`, not replacing it**. The
      web front end renders `lines` today and must keep working unchanged
- [ ] Emitted from the two loops that already know the structure: `build.py`'s
      pass loop (which pass, of how many, what it wrote) and the verify/repair
      loop (which attempt, which stage went red, what was patched)
- [ ] `Job.snapshot()` carries them, so both front ends see the same thing

**Why this is not optional and not cosmetic.** A progress view built by parsing
`lines` would be reading human-formatted output to recover structure the producer
already had — the exact anti-pattern the workspace guide names as *sky.boss
never parses human output* (`skyrow-workspace/workspace.md`, a sibling checkout;
named rather than linked, because a relative link into a sibling repo resolves on
this machine and nowhere else). The text log is for a person. The event list is
for a view.

## Phase 3 — The two panes

- [ ] `protopilot/console/`, a Textual app. **Not `tui`** — see above
- [ ] An input pane: the idea, `--direction`, and the flags that change the
      result (`--target`, `--archetype`, `--offline`, `--backend`)
- [ ] An output pane: `job.lines` streaming, and a progress region driven by
      `events` — the five passes, the verify attempts, the file each pass wrote
- [ ] A job list, from `STORE.all()`. Being able to see the last four runs is
      most of the value: it is what makes two ideas comparable
- [ ] `proto console` launches it. `proto new` is untouched and stays the
      scriptable path

## Phase 4 — The review checkpoint becomes a screen

The one interaction that has to move, and the one worth moving.

- [ ] The spec review — entities, screens, target, archetype, then approve — is a
      `[Y/n]` on stdin today. In the console it is a screen you can read properly
- [ ] Declining costs nothing and must keep costing nothing: the checkpoint sits
      before generation for exactly that reason
- [ ] The CLI prompt stays as it is. Two front ends, one seam, no shared view code

## Phase 5 — The concurrency defect, before concurrency is offered

- [ ] `JobStore.run` wraps work in `redirect_stdout`, and `sys.stdout` is
      **process-global**. Two jobs on two threads clobber each other's capture.
      `proto serve` gets away with it because nobody has run two at once
- [ ] **Until this is fixed the console runs one job at a time**, and says so when
      you ask for a second. A queue is honest; interleaved transcripts are not
- [ ] The fix is per-job capture rather than a global redirect. It is a `jobs.py`
      change and it improves `proto serve` for free

## Phase 6 — Tested with no key and no daemon

- [ ] The console drives `--offline` end to end in the suite, using Textual's
      `App.run_test` pilot — the same mechanism `verify_tui` already uses, so
      there is no new test dependency
- [ ] A run that fails still renders: the error, the last stage, and the
      `RUNBOOK.md` path. The floor the pipeline already has must be visible in
      the pane, not only on disk

## Acceptance

- [ ] `./pp check pre-push` green
- [ ] Phase 1's numbers exist and are recorded, whichever way they fell
- [ ] `proto console`, offline, generates a prototype end to end with no key, no
      daemon and no browser
- [ ] Output appears **while** generation runs, demonstrated by asserting on a
      partial log mid-run rather than on the final one
- [ ] `proto new` and `proto serve` are unchanged and green
- [ ] A second concurrent generation is refused by name, not interleaved

## Dropped, and why

**Embedding the running prototype in a pane.** The obvious next thought, and a
different project: two Textual `App`s cannot share one process because
`App.run()` owns the terminal, so it means a PTY and a terminal-emulator widget
Textual does not ship. `tui_probe.py` can already mirror a *screenshot* cheaply,
which is a Phase 3 nicety if wanted. Live interaction is its own plan.

**Replacing the CLI.** `proto new` is the scriptable path and what CI runs. A
front end that is the only way in is a tool you cannot automate.

**Sharing view code with `proto serve`.** Two views over one seam is the design.
A shared abstraction over a Jinja template and a Textual widget would be invented
before either had settled — the same argument that keeps `Screen.path` alone in
the terminal-target plan.

**A console for `./pp`.** Different tool, different audience, AGENTS.md Rule 15.
One interface serving a person generating an app and a person maintaining the
generator would serve neither.

**Deciding this replaces `proto serve`.** It might, once the default target has a
front end that fits it. That is a judgement to make with the console built and
used, not while arguing from a plan.
