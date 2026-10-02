---
title: The proto Console
slug: proto-console
priority: medium
category: spec
agent_value: 3
completed: 2026-09-04
updated: 2026-09-04
tags: [console, jobs, front-end, textual, ux]
summary: A terminal front end for the tool itself — type the idea in one pane, watch generation in another — built as a second view over the job seam `proto serve` already paid for.
---

# The proto Console

> **Status**: 🟢 All six phases done — ready for review
> **Priority**: Medium — the default target has no front end but raw stdout,
> which is a gap the pivot opened rather than a pre-existing one

## What this is not

**This is not the `tui` target.** That is what `proto` *emits*, and it landed on
2026-09-04 as [the terminal target](terminal-target.md).
This plan is what `proto` *is*: the tool's own interface.

The distinction is load-bearing enough to constrain the code. `tui` already means
"the terminal target" in five places — `targets/tui.py`, `passes/tui/`,
`baseline_tui.py`, `verify_tui.py`, `tui_probe.py` — so **this front end must not
be called `tui` anything.** It lives in `protopilot/console/`. A reader who has
to work out which `tui` a module means will get it wrong eventually, and the two
are adjacent in every way that matters.

[`docs/ideas/sketches-not-scaffolds.md`](../../ideas/sketches-not-scaffolds.md)
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
1278s in [the go/no-go](../../reports/occasional/2026-09-04-terminal-target-go-no-go.md))
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

## Phase 1 — Verify the two claims this plan rests on ✅

Both were read out of the source, not measured. Both are now measured, on
2026-09-04, and **the gate passes: the output is not buffered.** Phase 2 stays
an enhancement rather than becoming a prerequisite.

- [x] `protopilot.jobs` imports and `JobStore.run()` completes with **no web
      extra installed**. Confirmed in a venv built from `pip install -e .` with
      no extras, which resolves `fastapi`, `starlette` and `jinja2` to nothing —
      asserted absent at the top of the check, because a claim about a bare
      environment is worthless if the environment was not bare. Seam imports,
      job runs, status `done`
- [x] **`job.lines` grows during a run.** 27 of 28 lines arrive while the job is
      still running; the 28th is the verify result, which arrives when verify
      finishes and not via any flush
- [x] Record the split: **the `redirect_stdout` buffer holds 0 bytes** at the
      `finally`. Read out of the buffer directly rather than inferred from where
      lines landed, since "no late lines appeared" and "nothing was captured"
      are different claims. Every one of the 28 lines came through `job.log()`
- [x] **Gate: passed.** Nothing arrives late, so a pane is never dark waiting on
      a flush

### The numbers, and the one that matters

Offline generation finishes in under three seconds, which shows lines arrive
in order but says nothing about a twenty-one minute run. So the same shipped
`run_generation` was driven through the same `JobStore.run` with latency put
back into `run_pass`, where a real pass spends its wall clock:

| | |
|---|---|
| lines total | 28 |
| arriving during the run | 27 |
| arriving at the end | 1 (the verify result, logged) |
| bytes in the stdout buffer | **0** |
| **longest gap between lines** | **one pass** |

The last row is the design input. A pane is never blank for the length of a
run; it is blank for the length of *one pass*, and it already names the pass it
is waiting on — `builder.generate` logs `pass {name}...` **before** doing the
work, not after. Scaled to the measured 1278s `tui` run that is roughly four
minutes between lines, with the current pass on screen throughout.

### Why the pipeline is clean, in one fact

`SubprocessRunner.run` passes `capture_output=True`, so verify's pytest and
Docker calls never reach the terminal at all — their output comes back as a
`CommandResult` and is surfaced through `log()` like everything else. There is
exactly one `print()` left in `protopilot/` outside the web front end, in
`tui_probe.py`, and it is a CLI entry point that no job calls. The buffer is
empty because there is nothing to put in it.

### A hazard checked while here, and cleared

`redirect_stdout` rebinds `sys.stdout` for the whole **process**, not the thread
that entered it — so the obvious worry is that a job running underneath a live
console would capture the console's own painting and freeze the screen. It
cannot, on two independent counts: Textual's `LinuxDriver` writes to
`sys.__stderr__`, which is the wrong stream *and* the pristine handle, resolved
once at construction and handed to a `WriterThread`. Verified against Textual
8.2.8's source rather than its documentation.

This does not clear Phase 5, which is about two jobs clobbering **each other**.
It does mean the console's screen is not at risk, so Phase 5 stays where it is.

### What the measuring cost, which is the reusable part

The first latency injection slept inside `llm.structured`, and offline mode
never calls it — `run_pass` branches to `module.offline()` well before the LLM.
The run finished in the same 3.0s and reported *"27 during, 1 at end"*, which is
the correct answer arrived at by a method that had measured nothing. It would
have been reported as latency-in-play.

**A plant that did not land is indistinguishable from a gate that works.** The
version that stands asserts its own injection fired — `run_pass` was called five
times, wall clock exceeded the sleep budget — before it prints a single number.
Same shape as the `sed` that silently matched nothing during the same session's
skeletor upgrade, twice in one afternoon, by two different roads.

## Phase 2 — A structured event beside the text ✅

- [x] `Job` gains `events: list[dict]` **beside `lines`, not replacing it**, with
      `Job.event(kind, **fields)` stamping `at` so every producer's events are
      comparable. The web front end renders `lines` and is untouched — measured,
      not assumed: the same offline run produces the same 28 lines it did before
- [x] Emitted from the two loops that already know the structure. `generate`
      emits `pass_started` / `pass_done` / `pass_failed`; `drive_to_green` emits
      `verify_started` / `verify_passed` / `verify_failed`, `repair_started` /
      `repair_done` / `repair_empty` / `repair_failed` / `repair_rejected`, and
      `exhausted`
- [x] `Job.snapshot()` carries them, JSON-safe, so both front ends see the same
      thing over the same poll endpoint

The channel is a second parameter, `emit: Emit = no_emit`, threaded beside the
existing `log: Log = print`. **Every existing caller keeps working untouched** —
`proto new` passes no `emit` and gets the silent default, which is asserted by
running the real loop with the parameter omitted rather than by inspection.

### Two decisions worth keeping

**`index` and `of` come from the producer.** A view cannot count the passes
itself: which ones run belongs to `spec.target`, so *"pass 3 of 5"* is knowable
in `generate` and nowhere downstream. This is the concrete reason the channel
exists at all — the alternative is reading it back out of the sentence.

**`exhausted` is a distinct event from `verify_failed`.** A view that only ever
saw failures could not tell *still trying* from *gave up*, and that difference is
the whole point of the `RUNBOOK.md` the caller writes next. Measured on the red
path with a scripted verifier: `verify_failed → repair_started → repair_empty →
exhausted`, with the stage named on both ends.

`pass_done` carries `shown`, not `result.files` — `hide_tests` is presentation
and the event feeds a presentation, so a demo that keeps the suite out of the log
must not surface it in the progress region instead. Held by a test that first
asserts its own fixture contains a test file, since the check is vacuous
otherwise.

**Why this is not optional and not cosmetic.** A progress view built by parsing
`lines` would be reading human-formatted output to recover structure the producer
already had — the exact anti-pattern the workspace guide names as *sky.boss
never parses human output* (`skyrow-workspace/workspace.md`, a sibling checkout;
named rather than linked, because a relative link into a sibling repo resolves on
this machine and nowhere else). The text log is for a person. The event list is
for a view.

## Phase 3 — The two panes ✅

- [x] `protopilot/console/`, a Textual app. **Not `tui`** — held by a test that
      recomputes the package's filenames rather than trusting the reviewer
- [x] An input pane: the idea, `--direction`, and the flags that change the
      result. `--target` and `--archetype` are `Select`s built from the
      registries, so a new target appears without an edit here
- [x] An output pane: `job.lines` streaming, and a progress region driven by
      `events` — the passes with their state and files, the verify attempts,
      the repairs, and the floor
- [x] A job list, from `STORE.all()`. Read from the store rather than from a
      list the app keeps, so a job started by the web front end in the same
      process appears here too
- [x] `proto console` launches it. `proto new` is untouched and stays the
      scriptable path

### The move Phase 3 forced, and why it was not optional

`run_generation` lived in `protopilot/web/app.py`, which imports FastAPI at
module scope. A console importing it from there would have needed the `web`
extra to generate anything — **and the suite would not have noticed**, because
the test environment installs that extra. A plain `pip install -e .` console
would have failed for a user and stayed green here.

So it moved to `protopilot/generation.py`: standard library plus proto.pilot's
own modules, nothing else. `web/app.py` keeps a thin `run_generation` that pins
`TARGET` and delegates — a function rather than a `partial`, so the pin is
applied at call time and the suite's `app.TARGET` override still bites.

Two tests caught the move, both correctly, and the second is the one worth
keeping in mind: `test_an_injected_factory_still_wins` asserts a **negative** —
that the default verifier did not also run — through a `monkeypatch` aimed at
the module the call had just left. It passed. A patch that no longer reaches the
code under test turns a negative assertion into a tautology, and nothing in the
output says so. Confirmed non-vacuous afterwards by planting: with the injected
factory ignored, it now runs the real verifier to a timeout.

`test_both_front_ends_call_the_same_function` named two paths by hand and is now
`test_only_the_two_entry_points_assemble_a_spec`, which recomputes the set of
modules calling `spec_from_idea` and compares it to an expectation. The old
shape could not have noticed a *third* caller appearing, which is the direction
that matters now that there are three front ends sharing two entry points.

### One console bug, found by a test for something else

The status line was rewritten on **every tick**, so the "one at a time" refusal
was set by the button and overwritten 200ms later by `generating ...`. Declining
a second run looked exactly like a button that does nothing — the failure the
refusal exists to prevent, wearing its own clothes. It writes on transitions now.

Found by the test for the refusal, not by the test for the status line.

## Phase 4 — The review checkpoint becomes a screen ✅

- [x] The spec review is a screen you can read properly — the spec's **own**
      `summary()`, the same string `proto new` prints, so the two front ends
      cannot drift into describing one spec differently
- [x] Declining costs nothing further: asserted on the **workspace**, which is
      the only place a generation can leave a trace, rather than on a flag the
      console sets about itself
- [x] The CLI prompt is untouched. Two front ends, one seam, no shared view code

### The split this needed

`run_generation` did intake → skeleton → passes → verify in one call, with no
seam to put a question in. It is now `assemble` (intake, **writes nothing**) and
`build` (everything after the spec is settled), with `run_generation` calling
both for a front end that has no checkpoint — which the web front end does not.

That split is what makes "declining costs nothing" true rather than asserted.
And it makes the cost honest in the other direction too: intake has already run
by the time there is a spec to show, so declining is not free. **One model call
is spent.** What the checkpoint saves is the five passes and the verify loop,
which is the whole of the wall clock and nearly all of the tokens — which is why
it sits here and not one step earlier, where there would be nothing to review.

`busy` is asked of a **phase**, not of `job.status`. The job is `done` while the
review is open — intake finished, nothing after it has started — so a status
reading would call the console idle and start a second generation underneath the
modal. Held by its own test.

### Two real bugs, one of them only visible on a small terminal

**The buttons were inside the scroll region.** A spec summary is as long as the
spec: five entities with eight fields is a screen and a half, and the answer to
a blocking question was then below the fold. They are outside it now, so the
summary scrolls and the answer does not move.

That one surfaced as a test failing about one run in three, always on an
assertion about something else — "the console is still busy", ten seconds after
a click that had quietly missed. The cause was one layer further down again:
**a widget is mounted before the screen's first layout pass**, so between those
two moments it exists with a zero-width region and `pilot.click` resolves to
coordinates that hit nothing. The wait is on the button *having a size* now, and
`approve()` asserts the screen actually closed — so a missed click fails at the
click rather than somewhere unrelated later.

Also measured while there: `app.query("#approve")` returns 0 while
`app.screen.query("#approve")` returns 1 on the same frame. The app-level query
searches the default screen, not the pushed modal, while `pilot.click` resolves
against the top of the stack — so the obvious predicate waits forever for a
button that is on screen and clickable.

## Phase 5 — The concurrency defect ✅

- [x] `JobStore.run` wrapped work in `redirect_stdout`, and `sys.stdout` is
      process-global. Two jobs on two threads clobbered each other's capture
- [x] The console refuses a second run by name
- [x] **Fixed: capture is per-thread.** `sys.stdout` is replaced once by a
      router that dispatches on the calling thread's id; a job registers a
      writer for its own thread and every other thread reaches the real stdout
      untouched. `proto serve` gets this for free

Installed once and **left in place** rather than swapped around each job.
Restoring on the last unregister looks tidier and races — a second job
registering while the first restores loses its routing, which is the class of
bug being replaced. With no writer registered every call delegates to the
original object, and everything that is not `write`/`flush` is proxied through,
so a library asking `isatty()` or `fileno()` still gets the truth about the
process.

**The buffer is gone entirely**, which fixes a second defect rather than the
same one twice. Output used to accumulate in a `StringIO` and land in the
`finally`, so anything reaching the log via `print` rather than `job.log`
arrived *when the job ended* — one block, twenty-one minutes late. Phase 1
measured that buffer at 0 bytes, so it was latent: the first pass that printed
instead of logging would have reinstated it silently. A `_JobWriter` now turns
writes into `job.log` calls a line at a time, live.

Both defects are held by tests that were confirmed to see them: planting a
single process-wide writer fails the concurrency test, and planting a
hold-until-flush writer fails the liveness test. The concurrent test uses a
`Barrier` and 50 interleaved lines each, because with one print apiece a run
where the two happened not to overlap would pass and prove nothing.

**The console still runs one job at a time, and the reason changed.** It began
as a guard around this defect; what remains is a view constraint — these panes
answer "what is happening" once, and a second run would have nowhere to go.
Worth stating because a guard whose reason has expired is how a stale comment
starts.

## Phase 6 — Tested with no key and no daemon ✅

- [x] The console drives `--offline` end to end in the suite through Textual's
      `App.run_test` pilot — the same mechanism `verify_tui` uses, so no new
      test dependency. An idea in, a real tree out, no key and no daemon
- [x] A run that fails still renders: the error and the last stage in the pane,
      and a red run names its stage and points at `RUNBOOK.md`

The event fold is a **pure function over dicts** in `console/progress.py`, with
no Textual import, and is tested as one. Asking a rendered pane whether attempt
2 was counted is a hard way to learn it.

### Two things the tests only caught by planting

**`pilot.click` coalesces repeat clicks at the same position.** Measured on a
minimal app: three clicks delivered two presses. A click-based test of the
"second run refused" case would have passed whether the refusal worked or not,
so that test uses the `ctrl+r` binding — a real user path, not coalesced — while
every other test still exercises the button.

**A test can describe a property without testing it.** The by-name matching test
asserted that a pass is matched by `name` and not `index`, using an event with no
`plan` — where both strategies fall through to "append a new pass" and both look
right. Planting index-matching left the file green. It now folds a plan *and* a
disagreeing index, where the two strategies give different answers.

## Acceptance

- [x] `./pp check pre-push` green — 594 tests
- [x] Phase 1's numbers exist and are recorded, whichever way they fell
- [x] `proto console`, offline, generates a prototype end to end with no key, no
      daemon and no browser
- [x] Output appears **while** generation runs, demonstrated by asserting on a
      partial log mid-run rather than on the final one. The runner is held open
      on an event and the panes are read while it is blocked, so the assertion
      cannot accidentally be made against a finished job
- [x] `proto new` and `proto serve` are unchanged and green
- [x] A second concurrent generation is refused by name, not interleaved

All six phases are done. What ships is a console that generates, streams,
lists, reviews and refuses — and a `jobs.py` whose capture is per-job, which
`proto serve` gets for free.

## Dropped, and why

**Embedding the running prototype in a pane — dropped, then done.** The
reasoning here was sound and the conclusion was wrong, which is worth leaving
visible: two Textual `App`s genuinely cannot share one process, because
`App.run()` owns the terminal. What that rules out is running the prototype
*in* the console's process. It does not rule out running it in **another** one.

`protopilot/tui_stream.py` boots the generated app under `App.run_test` — which
composites to a buffer instead of to a terminal — holds it open, and answers a
newline-delimited JSON protocol: send a key, get the frame it produced; ask for
a frame, get the current one. `ctrl+l` in the console starts it, forwards
keystrokes, and polls at 10Hz, so an app driving itself from `set_interval`
animates. No PTY, no terminal-emulator widget, and the isolation the probe was
built for is kept — a `compose()` that raises ends that process and is
reported, rather than taking the console down.

**The mistake was reasoning from the obstacle to the verdict.** "Two apps
cannot share a process" is true and was treated as "a live preview needs a
terminal emulator", which does not follow. The thing that made it cheap was
already in the tree and had been for a week: `tui_probe.py` renders a generated
app to a string without a terminal, because that is how the terminal target
verifies at all. A second process was the only missing piece.

What it is not: a terminal emulator. It cannot show a program that writes
escape sequences itself, only a Textual app that composites — which is every
tree this target generates.

`ctrl+`-chords are never forwarded, so the reader keeps a way out no generated
app can bind away. That guard turned out to govern less than it looked like:
a **bound** chord never reaches `on_key`, because Textual dispatches bindings
first, so `ctrl+p` stays with the console with or without it. What the guard
actually covers is every ctrl chord the console has *not* bound — which is the
set that matters, since a future binding is drawn from it. The test asserted on
`ctrl+p` first and stayed green with the guard deleted.

**The screenshot half shipped**, on 2026-09-04, the first time somebody
generated a prototype and asked where it was — which is the question this
section predicted and answered with "a Phase 3 nicety if wanted". It was
wanted, and it was nearly free: the terminal verifier already boots the app
under `App.run_test` and composites its screen to decide whether it painted at
all, then threw that away the moment it returned a verdict. `generation.build`
now holds the verifier rather than passing `make_verifier()` inline, asks it for
`last_probe["buffer"]`, and emits a `preview` event; the console shows it in a
second tab beside the log and comes forward once, on arrival.

`getattr`, so a target whose verifier has no screen emits nothing — a field
added to every target so that one of them can be asked is the shape this
avoids.

Two things worth keeping from building it. **A stale screenshot is worse than
none**, because it is a picture of something that is not what is being
generated: resetting the guard without clearing the widget left the previous
idea's screen sitting in the pane, and the test for the *second* run caught it.
And the tab comes forward **once**, not per tick — a reader who tabs back to the
log to re-read a repair must stay there, which is the same bug as the status
line that rewrote itself over its own message.

The emit itself had no test until a plant pointed at a file that did not exist
and reported "no tests ran" as if it were a result. Every console-side test
injected the event by hand, which proves the pane works and says nothing about
whether anything emits one. `test_the_generated_apps_screen_reaches_the_event_channel`
covers that seam now, and goes red both when the emit is removed and when the
verifier handle is passed inline again.

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
