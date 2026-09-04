# Can the model build a terminal app as well as a web one?

> **Analyzed at:** v0.1.0 +35 commits (`6e02c85`)
> Phase 1 of [`docs/TODO/terminal-target.md`](../../TODO/terminal-target.md),
> the go/no-go the rest of that plan is gated on.

**The gate passes, and the metric it was written around turns out to measure
nothing.** Six runs, three specs, two targets, all green. Mean repair attempts
were **identical** — 2.33 against 2.33 — so the risk the plan was built to
catch did not appear. What did appear is a cost gap the plan never predicted,
and a failure distribution that is almost entirely made of two fixable defects
rather than of model competence.

## The hypothesis under test

From [`docs/ideas/sketches-not-scaffolds.md`](../../ideas/sketches-not-scaffolds.md):

> **Model competence is the open risk.** There is far more FastAPI + Jinja in
> the pretraining set than Textual. Fewer examples means more repair attempts
> […] **This is the one thing that could invert the whole argument.**

Phase 1's gate: *if the terminal target needs materially more repair attempts,
stop.*

## What was run

Three specs spanning both archetypes — `field_notes` (crud, 2 entities),
`kitten_chess` (turn-based-game, 2), `seating_plan` (crud, 3, chosen as the
awkward shape: seating is constraint-satisfaction wearing a CRUD costume). Each
generated for both targets. `claude-opus-5`, effort `high`, backend
`claude-code`, 3 repair attempts allowed, verified by boot + smoke suite.

The web half is the **real pipeline** — `build.CODE_PASSES`, `run_pass`,
`drive_to_green`, `verify.Verifier` — not a reimplementation, so the number it
produces is what the tool actually does today.

## Results

| run | green | attempts | wall | calls | output tok | cost |
|---|---|---|---|---|---|---|
| tui/field_notes | ✅ | 2 | 912s | 6 | 78,333 | $3.08 |
| tui/kitten_chess | ✅ | 3 | 1664s | 7 | 143,015 | $5.68 |
| tui/seating_plan | ✅ | 2 | 1258s | 6 | 110,577 | $4.01 |
| web/field_notes | ✅ | 3 | 697s | 7 | 44,297 | $2.51 |
| web/kitten_chess | ✅ | 2 | 792s | 6 | 70,159 | $2.91 |
| web/seating_plan | ✅ | 2 | 776s | 6 | 73,044 | $3.13 |

|  | green | mean attempts | mean wall | mean output | mean cost |
|---|---|---|---|---|---|
| **tui** | 3/3 | **2.33** | 1278s | 110,642 | $4.26 |
| **web** | 3/3 | **2.33** | 755s | 62,500 | $2.85 |

Terminal costs **1.69× wall clock, 1.77× output tokens, 1.49× dollars**, and
**1.00× repair attempts**.

## The gate: pass

The terminal target does not need materially more repair attempts. It needs
exactly as many. Costs are stated below rather than buried, but the condition
the plan wrote down is not met and **the plan proceeds**.

Worth being precise about what this does and does not establish. It says the
model can carry a Textual + SQLite app to green as reliably as a FastAPI one, on
three specs. It does not say the resulting app is as *good* — nothing here
measures whether a human would rather look at it, which is the thing the pivot
is actually for and which no automatic oracle reaches.

## Where the cost actually is

Not spread. Two passes:

| | tui | web | ratio |
|---|---|---|---|
| `smoke` | 307 / 465 / 267s | 51 / 55 / 45s | **~6.4×** |
| `screens` vs `routes` | 195 / 580 / 515s | 54 / 154 / 84s | **~4.3×** |
| everything else | comparable | comparable | ~1.2× |

`schema`, `seed` and `ui` are near parity. The terminal premium is bought
almost entirely in generating the smoke suite and the screens — which is the
scarcity hypothesis showing up **as time rather than as failure**. The model
gets Textual right; it thinks longer to do it.

That is a much better position than the plan feared, because thinking time is
bought once per generation and repair attempts compound.

## The failures cluster, and it is not close

The plan flagged this as the thing the headline number would hide:

> whether the failures **cluster** — a recurring mistake is a prompt fix or a
> `skeleton/` file, which is cheap, while scattered failures are a competence
> ceiling, which is not.

They cluster almost perfectly. **One dominant cause per target, three of three
runs each.**

### Web: the prompt lies about the skeleton — 3/3

`STACK_BRIEF` tells every pass:

> `app.forms` -> `parse_str`, `parse_int`, … `parse_bool` … **Every one takes
> the raw form value and an optional fallback and never raises.**

`parse_bool` does not take a fallback. Every web run with a bool field called
`parse_bool(value, False)`, got `TypeError` at request time, and burned a repair
attempt. Three runs, three independent rediscoveries, three different fixes
(a `checkbox()` helper, dropping the argument, rewriting the call sites).

The model was doing exactly what it was told. **This is a one-line defect in
either the brief or the skeleton and it is the web target's entire failure
mode.** It is also, precisely, a producer and a consumer inside one repo
disagreeing about a published artifact — the class the workspace rule says a
repo's own suite cannot find, arriving at home.

### Terminal: the smoke harness cannot see what the app renders — 3/3

Every tui run failed `tests`, and in all three the app was correct. The
generated smoke helper reads Static content via `.renderable`, which current
Textual removed — content now lives on `_content` as a `Content` object. So
every `Static` on every screen read as empty text while `DataTable` rows and
`Button` labels came through normally.

The three runs diagnosed it independently and correctly, and two of the three
fixed the *helper* rather than weakening the assertion. One noted that setting
`renderable` from the app "would have satisfied the check without rendering
anything, which is why the helper was the fix" — the model refusing to make a
test pass by lying to it.

**This is a defect in the spike's own skeleton, not in the model.** It inflates
the terminal repair count by roughly one attempt per run, which means the real
`tui` figure is *better* than 2.33 and the true gap favours the terminal target.

Consequence for Phase 3, and it is a design constraint rather than a bug fix:
*any generated screen whose only content is a `Static` is invisible to a
buffer-reading smoke harness.* The terminal skeleton must either expose text
through `Screen.sub_title`/`DataTable`/`Button`, or its helper must probe
several attributes. One run adopted `TEXT_ATTRS` as a module-level tuple, which
is the shape to carry forward.

### The third thing, which belongs to neither target

Three separate runs emitted **stray non-ASCII or envelope text into source
files**:

- `web/field_notes` — Tibetan `U+0F72`/`U+0F66` inside a `relationship()` call,
  making `models.py` unparseable, so uvicorn died at import and never bound.
- `tui/kitten_chess` — a literal `</content>` marker after `db.commit()` in
  `seed.py`, a `SyntaxError` at line 118.
- (and in the earlier trial run, a Cyrillic `м` in `мapped_column`.)

Both targets, three instances, all trivially repaired and all costing a full
attempt. **This is a decoding or envelope artifact of the serving path, not a
property of either target**, and it is currently paying for itself in repair
attempts on both sides of the comparison. It cancels out of the ratio and
should not be read as either target's cost. Worth its own investigation: a
cheap post-generation validity check (does this file parse?) before writing
would catch all three without a model call.

## The measurement was nearly invalid, and the security fix rescued it

The implementer's trial run recorded passes taking **18 and 33 turns** — the
model standing up scratch trees and iterating inside a single pass, where the
plan's headline metric cannot see it. A run scoring "1 repair" was hiding a
factor of thirty.

The cause was that `claude --print` runs with its full tool set. Fixing that as
a **product** defect — `files.py` guards what the model's answer may write and
had no authority over the process producing it, see `llm.ISOLATION` and
[`AGENTS.md`](../../../AGENTS.md) — removed the tools, and every call in these
six runs is **exactly 1 turn**.

So "repair attempts to green" is an honest metric here only because the write
guard was closed first. That is worth recording as a coincidence that went the
right way: **a measurement harness and a security boundary wanted the same
thing, and if the bug had been found second the six runs would have had to be
thrown away.**

A side effect on cost: the ambient system prompt fell from ~32k to ~3.6k cached
tokens, so these figures are also far closer to what the `api` backend would
produce than the trial run's were.

## What this changes in the plan

- **Phase 1 gate: passed.** Phases 2–6 proceed.
- **Phase 4's open question is answered by data.** "The split may not be five" —
  it is five, and the two expensive ones are `smoke` and `screens`. If the split
  is ever revisited, that is where the money is.
- **Phase 3 gains a constraint**: the terminal skeleton's smoke helper must
  probe multiple text attributes. Three runs found this independently; do not
  make a fourth.
- **Phase 5 is validated cheaply.** The blank-screen check ran with no browser,
  no Playwright and no Docker on the terminal side, exactly as predicted.
- **One thing to fix that is not in this plan at all**: `parse_bool`'s brief.
  It is the web target's whole failure mode and it is costing a repair attempt
  on most real generations today.

## Reproducing

**The harness is gone.** It was deleted on 2026-09-04, once the terminal target
it gated was green through Phase 6 — which is exactly what a spike is for, and
what [`scripts/spikes/README.md`](../../../scripts/spikes/README.md) says
happens to one. This section is kept rather than removed because a report that
silently drops its method reads like an assertion.

It ran as:

```bash
.venv/bin/python scripts/spikes/terminal_target/run.py \
  --target tui --spec field_notes --backend claude-code --out tmp/phase1
```

at commit `6e02c85`, writing records, prompts, generated trees and per-attempt
stage output under `tmp/phase1/<run_id>/`, one summary line per run in
`runs.jsonl`. Recover it with `git show 6e02c85:scripts/spikes/terminal_target/`.

**What the numbers above describe still ships.** The five task blocks and the
terminal stack brief were *moved* into `protopilot/passes/tui/_brief.py`, not
rewritten, so the per-pass costs here are about strings that are still in the
tree. Three sentences differ, and each is a finding on this page landing: the
brief no longer says `app.main` pushes the home screen, it names the skeleton's
`tests/screen.py` as the text reader every one of these runs wrote wrong, and
it says the stylesheet and widgets files already exist.
