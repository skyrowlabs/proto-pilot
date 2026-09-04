---
title: "The Terminal Target"
slug: terminal-target
shelf_status: planned
priority: high
updated: 2026-09-03
tags: [target, skeleton, passes, verify, archetypes, tui]
summary: "Make the output medium an axis and build a terminal target beside the web one — gated on a measurement, because the model has seen far less Textual than FastAPI."
---

# The Terminal Target

> **Status**: 🔴 Planned — designed, unreviewed
> **Shelf-Status**: planned
> **Priority**: High — it is the direction the tool is being pointed, and the
> first phase is what decides whether the direction is affordable
> **Queue-Order**: unset until it is `ready`

## Why, in one line

The argument lives in
[`docs/ideas/sketches-not-scaffolds.md`](../ideas/sketches-not-scaffolds.md)
and is **not repeated here** — a doc lives where it changes. This plan is the
buildable slice of that direction: the `target` axis and the terminal target
that proves it. Read the idea doc first; the three decisions and the reasoning
are all there.

What this plan adds is the part the idea doc deliberately does not have: phases,
a gate, and the costs that only appear once you try to build it.

## Problem

`proto` emits one shape of thing — FastAPI, Jinja, SQLAlchemy, Postgres, Docker
Compose — and that shape is baked into five places at once: `skeleton/`,
`CODE_PASSES`, `files.py`'s allowed paths, `Verifier`, and every pass prompt.
There is no seam at which a different output medium could be inserted, because
nothing ever needed one.

## The gate comes first, and it can say no

**Phase 1 is a go/no-go and the rest of this plan does not start until it
passes.** The idea doc names one risk that could invert the whole argument:
there is far more FastAPI and Jinja in the pretraining set than Textual, so
generation may need more repair attempts — and a bad generation already costs
more than a good one, because the repair loop runs three times.

That is measurable for the price of a few live calls, and measuring it needs
**none** of the machinery below. This is the drawing-freedom Phase 5 pattern:
a rung that is taken with numbers behind it or left untaken with the numbers
recorded.

## Phase 1 — Measure the model on Textual, before building any seam

No `target` axis, no new package. A spike, thrown away after.

- [x] Take three existing `spec.json` files spanning both archetypes — a `crud`
      tracker, a `turn_based_game`, and one deliberately awkward shape
- [x] Hand-run the five pass prompts against a Textual + SQLite brief, by
      script, outside the pipeline. The point is the model's output, not the
      plumbing
- [x] Boot each result and drive it with `App.run_test`. Count: repair attempts
      to green, tokens per generation, wall-clock to first green
- [x] Compare against the same three specs generated for the web target today.
      **This is the number the whole plan turns on**
- [x] Record it in `docs/reports/occasional/` whichever way it goes. A no is
      worth exactly as much as a yes here and costs the same to obtain
- [x] **Gate:** if the terminal target needs materially more repair attempts,
      stop. Amend the idea doc with the finding and leave the web target as the
      default. Do not proceed on the strength of preferring the idea

**Gate passed 2026-09-04. Phases 2–6 proceed.** Six runs, three specs, two
targets, all green. Mean repair attempts were **identical — 2.33 against
2.33** — so the condition that would have stopped this plan was not met. The
terminal target costs 1.69× wall clock and 1.77× output tokens, concentrated
almost entirely in the `smoke` and `screens` passes: the pretraining-scarcity
risk showed up **as thinking time rather than as failure**, which is the far
better outcome because time is spent once per generation and repair attempts
compound.

Failures clustered almost perfectly — one dominant cause per target, 3/3 runs
each, and **neither is model competence**. Web: `STACK_BRIEF` claims every
`app.forms` parser takes an optional fallback, and `parse_bool` does not, so
every spec with a bool field burned an attempt on a `TypeError` the model was
told to write. Terminal: the spike's own smoke helper reads Static text via
`.renderable`, which current Textual removed, so the app rendered correctly and
the test could not see it — meaning the real `tui` figure is *better* than 2.33.

Full numbers, per-pass breakdown and every repair reason:
[`docs/reports/occasional/2026-09-04-terminal-target-go-no-go.md`](../reports/occasional/2026-09-04-terminal-target-go-no-go.md).
Three findings there change phases below; they are marked inline.

**The harness is built and the six runs are made.**
[`scripts/spikes/terminal_target/`](../../scripts/spikes/terminal_target/) is
the re-runnable measurement — three specs, a Textual brief, the five prompts, a
write guard, a boot-and-paint check, and an incrementally written JSON record
per run. Its README carries how to run the six, what comes out, and three
things found while building it that this plan under-reads. Nothing under
`protopilot/` was touched, so the gate below can still say no.

**Structured output holds.** Confirmed live on 2026-09-03: a `structured()`
call with a Textual prompt and the `FILES_SCHEMA` shape returned a well-formed
`{files: [{path, content}], notes}`. Confirmed rather than assumed, as this
phase asks — and it held for the reason it was expected to, schema-constrained
decoding being a property of the serving runtime rather than of the target.

Two things to watch for that the headline number will hide. Whether the
failures **cluster** — a recurring mistake is a prompt fix or a `skeleton/`
file, which is cheap, while scattered failures are a competence ceiling, which
is not. And whether structured output holds: every pass depends on
schema-constrained JSON, and that is a property of the serving runtime rather
than of the target, so it should be unaffected — confirm rather than assume.

## Phase 2 — `target` becomes an axis, with nothing behind it yet

Mirrors `archetype` exactly, because that axis landed on this code and the shape
is proven.

- [x] `Spec.target: str = "web"` — **defaulted**, so every `spec.json` written
      before this loads and generates the app it always did. This is the same
      guarantee `archetype: str = "crud"` gives and it is tested the same way.
      **The field default and the CLI default are different decisions** and this
      is only the first — see Phase 6. The field default stays `web` forever,
      because its whole job is to say what a spec that predates the axis meant
- [x] `protopilot/targets/`, discovered by module presence like
      `protopilot/archetypes/`. A target owns four things the archetype axis
      does not touch:

      | Owns | Today | Why the target and not the archetype |
      |---|---|---|
      | skeleton directory | `render.SKELETON_DIR` | the fixed stack *is* the target |
      | pass tuple | `build.CODE_PASSES` | a terminal app may not split five ways |
      | allowed write paths | `files.ALLOWED` | different tree, different five paths |
      | verifier | `Verifier` | `Verifies` is already a Protocol — no refactor |

- [x] `Spec.summary()` prints the target at the review checkpoint. A person
      approving a generation must be able to see which kind of thing it is
- [x] Round-trip test: a spec saved and reloaded keeps its target; a spec
      written before this plan loads as `web` and generates byte-identically

**The one that will hurt: `target` and `archetype` multiply.** Every archetype
needs a baseline per target, and today's two archetypes against two targets is
four baselines to keep green in CI, growing as either axis does.

- [x] A target declares which archetypes it supports. An unsupported pair is
      refused **at intake, by name**, not generated into something broken. A
      matrix with holes stated is honest; a matrix with holes discovered at
      verify time is the tool lying about its own coverage

> **Phase 2 landed 2026-09-04.** The characterisation held in the only way it
> could: the offline CRUD generation of a two-entity spec changed **one file**,
> `.protopilot/spec.json`, by gaining a `target` key. Every generated
> application file — models, routes, seed, templates, smoke suite — and every
> skeleton file hashed identically, which is the byte-for-byte half of what the
> acceptance criterion asks for. `tests/golden/crud_offline_manifest.json` was
> regenerated for that one line and nothing else.
>
> Four things the plan's table under-reads, found by doing it.
>
> **The table lists what a target owns and not where it lived.** All four were
> *moved*, not copied: `render.SKELETON_DIR`, `build.CODE_PASSES` and
> `files.WRITABLE`/`PROTECTED` are gone from those modules, and
> `tests/test_targets.py` asserts their absence — a leftover constant is a
> second definition that silently wins somewhere. `files.check_path` and
> `files.write_all` grew `writable`/`protected` parameters as a consequence:
> the guard is mechanism, the list is the target's, and a default value there
> would have been a third place the default target is decided.
>
> **The write guard now follows the spec, not the import.** `run_pass` resolves
> `targets.for_spec(spec)` at the moment of writing, so a pass that returns
> `app/screens.py` into a web tree is refused with the web list named in the
> error. That is the seam Phase 4 needs and it exists now rather than later.
>
> **An unknown target raises where an unknown archetype falls back.** A
> deliberate divergence from "mirrors `archetype` exactly", and the reasoning
> is in `protopilot/targets/__init__.py`: `archetypes.for_spec` can default
> because a tree of the wrong *shape* still builds, while a target picks the
> skeleton, the passes and the verifier — so the same fallback hands somebody a
> FastAPI app because they asked for a terminal one. That is precisely the
> "generated into something broken" this phase's last task refuses.
>
> **`--target` and `proto targets` shipped with it**, because an axis nothing
> can select is not an axis. `targets.DEFAULT` is what `proto new` uses and it
> is a **separate constant** from `Spec.target`'s field default; they are equal
> today and Phase 6 moves only the first. `target` also joined
> `MODEL_OWNED_EXCLUSIONS`, which put it in `CARRIED_THROUGH_AMEND` for free —
> so `proto add` cannot silently rebuild a terminal app as a web one, which is
> exactly the defect that list was derived to prevent for `archetype`.

## Phase 3 — The terminal skeleton

- [x] `skeleton/` becomes `skeleton/web/` and `skeleton/tui/`. The move is
      mechanical and must be byte-identical for the web target — a
      characterisation test proves the existing tree is unchanged, exactly as
      Phase 2 of the archetypes plan did for CRUD
- [x] Textual + SQLite, one process. No compose file, no second service, no
      port allocation. `app.py`, `db.py`, the base screen, `tests/conftest.py`
- [x] **From Phase 1**: the smoke helper must probe several text attributes, not
      just `.renderable` — current Textual keeps `Static` text on `_content` as
      a `Content`. All three terminal runs failed on this and diagnosed it
      independently; a fourth would be waste. A screen whose only content is a
      `Static` is invisible to a buffer-reading harness, so either the helper
      probes (`TEXT_ATTRS`, the shape one run settled on) or generated screens
      carry text through `Screen.sub_title`, a `DataTable` or a `Button`
- [x] **What `proto gc` / `proto prune` / the Docker resource labels do for a
      tui-target tree is an open question, not a task.** They exist because a
      tree removed with `rm -rf` orphans a container, a volume and a network. A
      single process with a SQLite file orphans nothing. Do not delete them —
      the web target still needs them — but do not pretend they apply

> **Phase 3 landed 2026-09-04.** The move is proved rather than inspected:
> `tests/golden/web_skeleton_manifest.json` was captured from `skeleton/` at
> `51f1b31`, before a single `git mv` ran, and
> `tests/test_skeleton_move_characterisation.py` recomputes it from
> `targets.web.SKELETON_DIR`. All 24 files, byte for byte, unmoved in content.
> It hashes **source bytes**, unrendered and unnormalised, which the CRUD
> characterisation cannot: that one hashes a rendered tree and would not have
> noticed a file copied rather than moved.
>
> `skeleton/tui/` is 19 files against the web tree's 24, and most of the
> difference is Docker. It runs its own three-test suite green with no daemon,
> no browser and no port.
>
> **The helper became a skeleton file, and that is the real answer to Phase 1's
> constraint.** The plan offered two options — probe several attributes, or make
> generated screens carry text through `sub_title`/`DataTable`/`Button` — and
> `skeleton/tui/tests/screen.py` does the first while `app/screens.py`
> demonstrates the second, so the fix holds from both ends. Making it *skeleton*
> rather than generated is the part the plan did not say: a helper the model
> rewrites per prototype is a helper it gets wrong per prototype, which is
> precisely what was measured happening three times out of three.
>
> **The attribute has moved a third time.** Phase 1 found `.renderable` gone and
> the text on `_content` as a `Content`. On the Textual installed here (8.2.8)
> `_content` is gone too: the text is `Static.content`, a plain `str`, with
> `_Static__content` behind the mangling. All four names are in `TEXT_ATTRS`.
> A constraint that changes between the measurement and the implementation is
> the argument for the tuple rather than a branch, and for testing the shipped
> file rather than a copy of it — `tests/test_tui_skeleton.py` imports
> `screen.py` out of the skeleton and demonstrates it on a hand-written app.
>
> **Two things deliberately not done, both in the plan's own order.** There is
> no `protopilot/targets/tui.py`: a registered target whose `CODE_PASSES` and
> `verifier()` do not exist is a `proto new --target tui` that half-works, and
> Phase 6's note says exactly why that is the wrong order. The module arrives
> with the passes in Phase 4. And the gc question is recorded in `NOTES.md` and
> at `cli.py`'s `gc` as an open question rather than answered — the useful half
> found while writing it down is that `proto prune` is about the *registry* and
> so probably applies to a terminal tree unchanged, while `gc` and the labels
> are the half that does not apply and cannot be settled before Phase 5 says
> what a terminal verify leaves behind.

## Phase 4 — The passes, and how many there are

- [ ] `schema → smoke → seed → routes → ui` maps roughly to
      `models → smoke → seed → screens → styling`, but a Textual app is often
      one file with a `compose()` method, so **the split may not be five**.
      Decide this from Phase 1's spike output rather than by symmetry. **Answered:
      it is five.** Phase 1 ran all five and they all did work; the expensive
      two are `smoke` (~6.4× the web pass) and `screens` (~4.3×), while
      `schema`, `seed` and `ui` are at parity. If the split is revisited, that
      is where the money is
- [ ] Whatever the split, the two invariants hold and are tested: smoke is
      generated **before** the code it tests, from the spec; and each pass is
      handed the previous pass's **real source**, never a description of it
- [ ] The stack brief for this target is byte-identical across passes and repair
      attempts, for the cache-prefix reason the web brief already has

## Phase 5 — Verify, which is where this target is better than the web one

The reason to be optimistic about the whole plan.

- [ ] A `Verifies` implementation for the terminal target: start the app under
      `App.run_test`, drive the pilot, run the smoke suite, capture output
- [ ] The blank-screen check. This is the direct analogue of `PAINTED_JS` and
      of the browser stage, and it is **cheaper and more deterministic than
      either**: compare the rendered screen buffer to an empty one. No browser,
      no headless Chrome, no optional extra that gets reported as skipped
- [ ] `/healthz`, the Postgres wait, and the race the whole verify loop is built
      around all disappear. Assert that they are gone rather than left dead
- [ ] The repair loop is unchanged in shape: same three attempts, same floor,
      same `RUNBOOK.md` naming the red stage. Only the stages differ

## Phase 6 — The offline baseline, without which none of this is tested

- [ ] A deterministic Textual CRUD app in `baseline.py`'s terminal equivalent,
      good enough that CI exercises the whole pipeline for this target with no
      key and no Docker. **This is not optional and it is not last because it
      is least important** — it is last because it needs the four phases above
      to exist. A target without a baseline is a target the suite cannot see
- [ ] `--offline` produces a running terminal app end to end
- [ ] The characterisation discipline: the offline output for a fixed spec is
      byte-stable, so the golden manifests do not churn
- [ ] **`proto new` defaults to `--target tui`, and writes it explicitly into
      every new `spec.json`.** Decided 2026-09-04 on Phase 1's numbers: equal
      competence, a cost paid in thinking time rather than in failure, and the
      medium enforcing the disclaimer the tool exists to make. This is the last
      task in the plan and not the first, because a default pointing at a target
      that is not yet green breaks `proto new` for everyone including CI.

      Two things it must not do. It must not touch `Spec.target`'s field default
      — an old spec with no `target` key still means `web`, and always will; the
      flip is about what a *new* spec is born with. And it must not demote the
      web target beyond the default: it stays reachable by `--target web`, keeps
      its passes, its skeleton, its verifier and its offline baseline green, and
      keeps being generated in CI. It is the only control this repo has — when
      the terminal target regresses, "is this the target or the change?" is
      answerable only against a second target that still works

## Acceptance

- [ ] `./pp check pre-push` green
- [ ] Phase 1's numbers exist and are recorded, whichever way they fell
- [ ] A `spec.json` written before this plan loads, and generates a web app
      byte-identical to what it generated before
- [ ] `proto new "<idea>" --target tui --offline` produces a terminal app that
      starts, renders a non-empty screen, and passes its own smoke suite — with
      no key, no Docker, and no Playwright
- [ ] A terminal app whose screen renders nothing **fails verify**, demonstrated
      by generating one, not asserted
- [ ] An unsupported archetype × target pair is refused at intake, naming both
- [ ] The web target's five passes, skeleton and verifier are reachable and
      green, unchanged
- [ ] `proto new "<idea>"` with no `--target` produces a terminal app, and a
      `spec.json` written before this plan still produces a web one

## Dropped, and why

**Rewriting rather than adding an axis.** Deleting the web target now would
throw away five tested pass prompts, 24 skeleton files and the browser stage in
exchange for a target whose feasibility is unmeasured. The axis costs one
defaulted field and a package, and it makes Phase 1's comparison possible at
all — you cannot compare against a thing you deleted.

**Committing to Textual before Phase 1.** Named throughout because it is the
obvious candidate and has the headless-testing story this plan leans on, but
Phase 1 measures the model's competence at *a terminal UI library*, and if
Textual is where it is weakest that is a finding about Textual.

**Deciding Docker here.** The idea doc lists it as an open question and it stays
one. A single Textual process with a SQLite file may not need it, but the
argument that it is fine to run model-authored code unsandboxed on your own
machine is a decision, not a drift, and it belongs to the open-source release
rather than to this plan.

**Making `Screen.path` medium-neutral.** It is described as a URL path and a
terminal app has no URLs. Tempting to generalise it now; wrong, because the
right abstraction is not knowable until a second target exists, and a premature
one is harder to remove than a duplicated field. Let Phase 4 discover it.

**Folding `proto`'s own TUI into this plan.** The idea doc lists "does `proto`
become a TUI itself" as separable and it is. A dashboard over the five passes is
useful today, against the web target, with none of this built. It is its own
plan and it does not block or depend on this one.
