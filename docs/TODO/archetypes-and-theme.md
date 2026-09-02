---
title: "Archetypes and Theme"
slug: archetypes-and-theme
shelf_status: in-progress
priority: high
updated: 2026-09-01
tags: [spec, passes, intake, ux]
summary: "Give the spec a shape axis and a look axis, so a chess app and a gear tracker stop being the same CRUD app with a different adjective."
---

# Archetypes and Theme

> **Status**: 🟢 In progress — Phase 1 landed 2026-09-01
> **Shelf-Status**: in-progress
> **Priority**: High — it is the difference between output that is correct and output that is recognisable, and every later idea about guided intake depends on it existing
> **Queue-Order**: 10

## Problem

`Spec` is a CRUD data model wearing a general-purpose name. It has entities with
fields, and screens whose `kind` is one of `list`, `detail`, `form`, `custom`.
That is an admin panel. Every idea gets flattened into it.

The pipeline already knows this and is compensating in prose.
`protopilot/passes/intake.py` carries a five-paragraph essay inside its system
prompt explaining how to build a board game out of form buttons and inline SVG,
which runtime features are off-limits, and when a `custom` screen is allowed.
**That essay is doing the job a type should do.** It is untyped, unversioned,
untestable, and it is paid for on every single generation regardless of whether
the idea is a game or a gear list.

The second half is worse. `clarify` asks good, targeted questions — and then
`clarify.answers_to_direction()` joins the answers into one sentence and appends
it to `direction: str`. Structured intent is downgraded to prose *before intake
even runs*. So:

> A cat-themed chess app and a camping-gear tracker differ, in the spec, by an
> adjective inside a free-text field.

Concretely, today: ask for chess and you get `Game` and `Move` entities with
`/games`, `/games/new`, `/games/{row_id}`, `/moves`, `/moves/new`,
`/moves/{row_id}` — a CRUD admin panel over chess vocabulary. The board, if it
appears at all, is one `custom` screen the model was permitted but not required
to add, generated from a paragraph of prose rather than from anything the type
system knows about. `prototypes/kitten_chess/` in this repo is exactly that
artifact, and it is the reason this plan exists.

There is a related open item this closes on the way past: the offline baseline
ignores `spec.screens` entirely and always generates its own CRUD set, so the
thing CI exercises and the thing a user gets differ on precisely the point this
plan is about.

## Approach

Two new axes on the spec, kept deliberately **orthogonal**:

- **`archetype`** — what *shape* of thing this is. It selects the question set,
  the extra typed fields, the screen-generation rule, the prompt fragments
  handed to the code passes, and its own offline baseline.
- **`theme`** — palette, motif, tone, drawn subject. It feeds the UI pass and
  nothing else.

Keeping them apart is the whole economy of the design. Cat-themed chess is
archetype `turn-based-game` × theme `cats`. Fold theme into archetype and the
work becomes |archetypes| × |themes|; keep them apart and a theme costs one
prompt fragment and no baseline at all.

An archetype is a module under `protopilot/archetypes/`, shaped like the pass
modules it sits beside — module-level constants and two functions, no classes,
no registry file to keep in sync:

```python
NAME = "turn-based-game"
LABEL = "Something two people take turns at"
MATCHES = "chess, checkers, tic-tac-toe, a card game, anything with turns"
QUESTIONS = (...)        # fixed, hand-written, each with a stable id
EXTRA = TurnBasedFields  # a pydantic model merged into the spec
def screens(spec) -> list[dict]: ...
def brief() -> str: ...  # the fragment routes/ui/smoke are given
def offline(spec, ctx) -> dict: ...
ASSETS: tuple[str, ...] = ()
```

Discovery is by module presence, the same way `is_test_path` and the pass list
already work here — a file in the directory is a registered archetype, and there
is no second list to forget to update.

**Two constraints, both non-negotiable, both from the README's own reasoning:**

1. **An archetype may not choose a stack.** It contributes questions, typed
   fields, a screen rule, and prompt text. It does not touch `requirements.txt`,
   the Dockerfile, or the compose file. The moment an archetype can pick a
   stack, we are back to N unrunnable variants and debugging all of them.
2. **An archetype ships with its offline baseline in the same change.** This is
   already the rule for passes (AGENTS.md, "the offline baseline is the test
   suite") and it is what bounds this plan's size. It is the reason Phase 4 adds
   *one* archetype and not four.

`ASSETS` is declared and left empty on purpose — see *Dropped* below.

## Phase 1 — The spec grows two axes

No behaviour change. The pipeline runs exactly as it does today, with two fields
carried that nothing reads yet.

- [x] `Spec.archetype: str = "crud"` — defaulted, so every existing
      `spec.json` (including `prototypes/kitten_chess/`) still validates and
      `proto add` on an old tree still works
- [x] `Spec.theme: Theme | None = None` — `palette`, `motif`, `tone`, `subject`,
      all optional strings, no enums (a closed set of themes is a set someone
      immediately wants to be outside of)
- [x] `Spec.answers: dict[str, str]` — answers to *fixed* questions, keyed by
      their stable id
- [x] `Spec.summary()` prints both axes at the review checkpoint. The checkpoint
      is the only human gate in the tool; an axis it does not show is an axis
      nobody reviews
- [x] `protopilot/archetypes/__init__.py` — `all()`, `get(name)`, and a
      `MissingArchetype` that names what was asked for and lists what exists
- [x] Round-trip test: a spec saved and reloaded keeps both axes; a spec written
      before this change loads with `archetype == "crud"`

> **Phase 1 landed.** One decision the plan had not specified: the intake
> schema is generated from `Spec` and `_strictify` marks every property
> required, so the three new fields would have become fields the model *must*
> invent. `MODEL_OWNED_EXCLUSIONS` in `spec.py` now removes them — `archetype`
> and `theme` are the clarify pass's to classify and `answers` is assembled
> from what the human chose, so an intake guess would be a confident second
> opinion silently overwriting the first. The registry is real but empty; the
> test suite asserts that rather than asserting a future.

## Phase 2 — Extract `crud`, and prove nothing moved

The safest possible first archetype: the one that already exists.

- [x] `protopilot/archetypes/crud.py`, taking `standard_screens()` from
      `baseline.py` as its `screens()` and the CRUD half of the intake prompt as
      its `brief()`
- [~] `intake.SYSTEM` loses the archetype-specific prose it no longer owns and
      keeps only what is true of every app — **partially done, deliberately.**
      The CRUD screen rule moved to `crud.screens()`. The board-game prose
      did not: prose only stops being intake's when something else owns it,
      and `turn-based-game` does not exist until Phase 4. Stripping it now
      would regress the model path for exactly the ideas this plan is about,
      with nothing to catch it — the offline baseline cannot read a prompt.
      Moves in Phase 4, where it lands in `brief()`.
- [x] `baseline.py` honours `spec.screens` instead of regenerating its own CRUD
      set — closing the standing NOTES item, and the precondition for any
      archetype whose screens are not CRUD
- [x] **Characterisation test**: the offline generation of a two-entity spec is
      byte-identical before and after this phase. If `crud` is a faithful
      extraction this is free; if it is not, this is the only phase where that
      is cheap to discover

> **Phase 2 landed.** The characterisation held: byte-identical output at every
> step, `tests/golden/crud_offline_manifest.json` captured from `77c3772` before
> a line of the extraction was written.
>
> Two things worth knowing for Phase 4. `crud.offline()` delegates to
> `baseline.py` rather than moving seven hundred lines, because baseline *is*
> the CRUD baseline — it was written when CRUD was the only shape there was. A
> second archetype does not get to do that; it writes its own. And `brief()`
> exists but is **not wired into any pass yet**: the fragment has to reach the
> model through the per-pass user message and never through `passes/_shared.py`,
> which is byte-identical across passes on purpose so it stays a prompt-cache
> prefix. Text that varies by archetype must not go there or it stops being one.

## Phase 3 — Clarify becomes the classifier, and answers stay typed

- [ ] `clarify` returns `archetype`, `theme` and up to two *extra* questions,
      alongside the `heads_up` it already returns. One call, not two: the
      archetype's own fixed questions are merged in locally from the registry,
      so nothing is spent asking the model to repeat what we wrote down
- [ ] The classifier is given each archetype's `MATCHES` line, generated from the
      registry — so adding an archetype teaches the classifier by existing
- [ ] A low-confidence classification falls back to `crud`. `crud` is the one
      archetype that produces something usable for any idea, which makes it the
      correct answer to "I am not sure"
- [ ] **Answers stop being prose.** Fixed questions carry stable ids and land in
      `spec.answers`; model-invented questions have model-invented ids and no
      schema, so they keep going to `direction`. The split is honest about which
      answers have a contract and which do not
- [ ] `answers_to_direction()` is deleted, not deprecated — a second path from
      answers to prose is how the typed one silently stops being used
- [ ] The human review checkpoint can override the archetype
      (`proto new --archetype turn-based-game`), because a classifier that
      cannot be overruled is a classifier that has to be right

## Phase 4 — `turn-based-game`, with its baseline

The archetype that proves the design, chosen because it is the one today's spec
most obviously cannot express, and because it needs **no runtime capability the
skeleton does not already have** — a grid of squares where each square is a
form button, re-rendered per submit, is a complete two-player board game.

- [ ] Fixed questions with stable ids: `players`, `turn_order`, `win_condition`,
      `board_shape`
- [ ] `EXTRA` fields: board dimensions, the piece vocabulary, whose turn it is
- [ ] `screens()` yields a `/board` custom screen plus a minimal record set —
      not the full CRUD spread, which is the point
- [ ] `brief()` fragments for routes (the turn state machine), ui (inline SVG
      pieces, the form-button grid) and smoke (a test that *takes a turn* and
      asserts the state changed — a suite that only checks for 200s cannot tell
      a working game from a static picture of one)
- [ ] `offline()` — a deterministic tic-tac-toe. Small enough to be honest,
      real enough to exercise a non-CRUD screen end to end in CI
- [ ] End-to-end against real Docker, not only fakes: generate, boot, take a
      turn through the browser stage, confirm the board changed

## Phase 5 — Theme

Cheap, high-visibility, and the axis that does the most for "relatable" per unit
of work.

- [ ] `theme` reaches the UI pass only. No other pass reads it, and a test
      asserts that: a theme that can change routes or models is an archetype
      wearing the wrong name
- [ ] The UI brief asks for drawn inline SVG on-theme — the existing prompt
      already insists artwork is drawn rather than emoji, and this gives that
      instruction a subject
- [ ] The offline baseline ignores `theme` and produces the plain look. Themes
      cost nothing in baseline maintenance, which is exactly why they are a
      separate axis

## Phase 6 — The journey, in the front end

Last, deliberately: the web form is a *rendering* of the question set, and until
Phases 3–4 exist there is nothing to render.

- [ ] `clarify.html` shows the archetype it inferred and lets the user change it
      before answering — the classification is the highest-leverage thing to
      correct, and the cheapest moment to correct it is before any tokens
- [ ] Fixed and model-generated questions render distinguishably, because they
      are not the same kind of thing
- [ ] Theme gets its own small control rather than being buried in a free-text
      box
- [ ] `proto serve` stays a second *caller* of the pipeline, never a second
      implementation — the existing rule, restated because this phase is where
      it is most tempting to break

## Acceptance

- [ ] `./pp test unit` green, and `./pp check pre-push` green
- [ ] Phase 2's characterisation test: offline CRUD generation is byte-identical
      to `a79e41b`'s output for the same spec
- [ ] `proto new "cat themed chess" --offline` produces a spec whose
      `archetype == "turn-based-game"` and whose screens include a board that is
      not a `list`, `detail` or `form`
- [ ] The same idea with `--archetype crud` produces the CRUD spread instead —
      proving the axis is real and not the classifier's opinion baked in
- [ ] A `spec.json` written before this plan loads without error and generates
      the same app it did before
- [ ] Grep proves it: no archetype module imports `requirements.txt`, the
      Dockerfile or the compose file, enforced by a test rather than a rule
- [ ] `theme` appears in the UI pass's prompt and in no other pass's, enforced
      by a test
- [ ] A generated `turn-based-game` boots and a turn can be taken through the
      browser stage

## Dropped, and why

**A `simulator` archetype in this plan.** It was the third example in the
original ask and it is the one that does not fit. A traffic simulator with a
full page reload per tick is a poor demo, so `simulator` needs a bounded
relaxation of the no-JavaScript rule — a vendored `app/static/*.js` copied
byte-for-byte into the skeleton, never generated, giving exactly a tick loop and
a canvas hook. That is a change to a load-bearing invariant and it deserves its
own plan and its own argument.

What this plan does instead is **design the seam without walking through it**:
`ASSETS` is declared on the archetype module and is empty for both archetypes
here. So the decision is deferred rather than pre-empted, and when it is made it
is a value in a tuple rather than a refactor. An earlier framing of this work
treated the JavaScript question as gating Phase 1. It is not — board games need
nothing beyond what the skeleton has today, and the only thing that genuinely
needed deciding was whether an archetype *could ever* contribute a static file.

**Letting an archetype choose a stack.** The obvious next step and the one that
destroys the tool. Covered above; restated here because it is the thing a future
reader will most want to do.

**A menu of archetypes before the user types anything.** It converts an open
prompt into a form, which is a worse first impression and a narrower funnel, and
it forces a taxonomy decision onto someone who has not described their idea yet.
Classify from the sentence, then let them correct it.

**Theme as an archetype property.** Multiplies the work by the product of the
two axes, and gets the abstraction backwards: "cats" is not a kind of
application.

**A closed enum of themes.** Whatever set we pick, the first real user wants the
one outside it, and a rejected theme is a worse outcome than an unrecognised one
the UI pass interprets loosely.

**Keeping `answers_to_direction()` alongside the typed path.** Two routes from
an answer to a pass means the typed one gets quietly bypassed and we are back to
prose with extra steps.

**Doing more than two archetypes here.** Each one costs a baseline, and the
baseline is what keeps CI honest. Two is enough to prove the axis is real; the
third is evidence about the *second* archetype's abstraction, which is worth
having before paying for a fourth.
