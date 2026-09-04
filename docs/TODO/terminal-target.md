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

- [ ] Take three existing `spec.json` files spanning both archetypes — a `crud`
      tracker, a `turn_based_game`, and one deliberately awkward shape
- [ ] Hand-run the five pass prompts against a Textual + SQLite brief, by
      script, outside the pipeline. The point is the model's output, not the
      plumbing
- [ ] Boot each result and drive it with `App.run_test`. Count: repair attempts
      to green, tokens per generation, wall-clock to first green
- [ ] Compare against the same three specs generated for the web target today.
      **This is the number the whole plan turns on**
- [ ] Record it in `docs/reports/occasional/` whichever way it goes. A no is
      worth exactly as much as a yes here and costs the same to obtain
- [ ] **Gate:** if the terminal target needs materially more repair attempts,
      stop. Amend the idea doc with the finding and leave the web target as the
      default. Do not proceed on the strength of preferring the idea

Two things to watch for that the headline number will hide. Whether the
failures **cluster** — a recurring mistake is a prompt fix or a `skeleton/`
file, which is cheap, while scattered failures are a competence ceiling, which
is not. And whether structured output holds: every pass depends on
schema-constrained JSON, and that is a property of the serving runtime rather
than of the target, so it should be unaffected — confirm rather than assume.

## Phase 2 — `target` becomes an axis, with nothing behind it yet

Mirrors `archetype` exactly, because that axis landed on this code and the shape
is proven.

- [ ] `Spec.target: str = "web"` — **defaulted**, so every `spec.json` written
      before this loads and generates the app it always did. This is the same
      guarantee `archetype: str = "crud"` gives and it is tested the same way
- [ ] `protopilot/targets/`, discovered by module presence like
      `protopilot/archetypes/`. A target owns four things the archetype axis
      does not touch:

      | Owns | Today | Why the target and not the archetype |
      |---|---|---|
      | skeleton directory | `render.SKELETON_DIR` | the fixed stack *is* the target |
      | pass tuple | `build.CODE_PASSES` | a terminal app may not split five ways |
      | allowed write paths | `files.ALLOWED` | different tree, different five paths |
      | verifier | `Verifier` | `Verifies` is already a Protocol — no refactor |

- [ ] `Spec.summary()` prints the target at the review checkpoint. A person
      approving a generation must be able to see which kind of thing it is
- [ ] Round-trip test: a spec saved and reloaded keeps its target; a spec
      written before this plan loads as `web` and generates byte-identically

**The one that will hurt: `target` and `archetype` multiply.** Every archetype
needs a baseline per target, and today's two archetypes against two targets is
four baselines to keep green in CI, growing as either axis does.

- [ ] A target declares which archetypes it supports. An unsupported pair is
      refused **at intake, by name**, not generated into something broken. A
      matrix with holes stated is honest; a matrix with holes discovered at
      verify time is the tool lying about its own coverage

## Phase 3 — The terminal skeleton

- [ ] `skeleton/` becomes `skeleton/web/` and `skeleton/tui/`. The move is
      mechanical and must be byte-identical for the web target — a
      characterisation test proves the existing tree is unchanged, exactly as
      Phase 2 of the archetypes plan did for CRUD
- [ ] Textual + SQLite, one process. No compose file, no second service, no
      port allocation. `app.py`, `db.py`, the base screen, `tests/conftest.py`
- [ ] **What `proto gc` / `proto prune` / the Docker resource labels do for a
      tui-target tree is an open question, not a task.** They exist because a
      tree removed with `rm -rf` orphans a container, a volume and a network. A
      single process with a SQLite file orphans nothing. Do not delete them —
      the web target still needs them — but do not pretend they apply

## Phase 4 — The passes, and how many there are

- [ ] `schema → smoke → seed → routes → ui` maps roughly to
      `models → smoke → seed → screens → styling`, but a Textual app is often
      one file with a `compose()` method, so **the split may not be five**.
      Decide this from Phase 1's spike output rather than by symmetry
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
