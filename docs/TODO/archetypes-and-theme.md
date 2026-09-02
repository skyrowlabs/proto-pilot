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

- [x] `clarify` returns `archetype`, `theme` and up to two *extra* questions,
      alongside the `heads_up` it already returns. One call, not two: the
      archetype's own fixed questions are merged in locally from the registry,
      so nothing is spent asking the model to repeat what we wrote down
- [x] The classifier is given each archetype's `MATCHES` line, generated from the
      registry — so adding an archetype teaches the classifier by existing
- [x] A low-confidence classification falls back to `crud`. `crud` is the one
      archetype that produces something usable for any idea, which makes it the
      correct answer to "I am not sure"
- [x] **Answers stop being prose.** Fixed questions carry stable ids and land in
      `spec.answers`; model-invented questions have model-invented ids and no
      schema, so they keep going to `direction`. The split is honest about which
      answers have a contract and which do not
- [x] `answers_to_direction()` is deleted, not deprecated — a second path from
      answers to prose is how the typed one silently stops being used
- [x] The human review checkpoint can override the archetype
      (`proto new --archetype turn-based-game`), because a classifier that
      cannot be overruled is a classifier that has to be right

> **Phase 3 landed, and one live call was spent verifying the half the offline
> baseline cannot reach.** It found a real prompt defect.
>
> Asked to classify *"a cat and dog themed 3d chess app"*, the model returned
> valid structured output, extracted the theme precisely (`subject: cats and
> dogs`, `motif: paw prints`, `tone: playful`, and `palette` correctly left
> **empty** rather than invented), fired `heads_up` in the user's own words
> — *"The board can't be 3d here"* — and asked exactly two extra questions,
> neither repeating the fixed set.
>
> And it returned **`confidence: high`** for filing a chess game as `crud`.
> Correctly, by the prompt's own wording: it asked for `low` "when the idea
> genuinely could be more than one of these", and with one archetype installed
> there is nothing to be ambiguous *between*. So the signal was measuring the
> length of the list rather than the quality of the fit, which made the fallback
> dead code in exactly the case it exists for — a game confidently filed as a
> tracker. The prompt now asks about **fit**, and says outright that a one-entry
> list does not make that entry a good fit.
>
> **The fix is not verified.** One call was the budget and it was spent finding
> the bug; Phase 4's call re-tests it with two archetypes, which is also the
> first point at which discrimination is testable at all. With one archetype the
> enum has one value, so nothing about *choosing* could be tested here.
>
> Two other things that call settled. The CLI never invoked `clarify` — the plan
> did not notice, and Phase 3 had to answer it: `proto new` now classifies
> unless `--archetype` is given, and `--answer id=value` reaches the typed
> channel without a browser. And the model's own two questions were
> `play_or_record` and `rules_enforcement` — both of which are *the archetype's
> job*, and both of which become fixed questions with stable ids in Phase 4.
> That is direct evidence the axis is real: with the right archetype installed,
> those two model slots free up for something genuinely idea-specific.

## Phase 4 — `turn-based-game`, with its baseline

The archetype that proves the design, chosen because it is the one today's spec
most obviously cannot express, and because it needs **no runtime capability the
skeleton does not already have** — a grid of squares where each square is a
form button, re-rendered per submit, is a complete two-player board game.

- [x] Fixed questions with stable ids: `players`, `turn_order`, `win_condition`,
      `board_shape`
- [x] `EXTRA` fields: board dimensions, the piece vocabulary, whose turn it is
- [x] `screens()` yields a `/board` custom screen plus a minimal record set —
      not the full CRUD spread, which is the point
- [x] `brief()` fragments for routes (the turn state machine), ui (inline SVG
      pieces, the form-button grid) and smoke (a test that *takes a turn* and
      asserts the state changed — a suite that only checks for 200s cannot tell
      a working game from a static picture of one)
- [x] `offline()` — a deterministic tic-tac-toe. Small enough to be honest,
      real enough to exercise a non-CRUD screen end to end in CI
- [x] End-to-end against real Docker, not only fakes: generate, boot, take a
      turn through the browser stage, confirm the board changed

> **Phase 4 landed, and the design holds.** `turn-based-game` replaces all five
> baseline generators; `crud` replaces none. Those are the two ends of the
> interface and both work.
>
> **Three defects, none of which a unit test found.**
>
> 1. *Winning silently started a new game.* `/board` showed the most recent
>    **unfinished** match, so the instant somebody won, the result was replaced
>    by a fresh empty board. Found by playing it. The generated suite had
>    passed — it never played as far as a win. Fixed, and the generated suite
>    now carries `test_playing_to_a_win_shows_the_result`, which is the one
>    assertion a static picture of a board cannot satisfy.
> 2. *The seed order was load-bearing and wrong.* The board shows the most
>    recent match, so seeding the finished game **second** opened the app on a
>    finished board where every move was refused — indistinguishable from a
>    broken game.
> 3. *The CLI hardcoded `crud.screens()` regardless of archetype*, so a
>    generated board game was checked for `/kittens`, `/kittens/new` and
>    `/kittens/1`. **Only the browser stage could find this**: every unit test
>    built its spec by calling the right archetype directly, so the real call
>    path was the one nothing exercised. `archetypes.screens_for()` now owns it
>    at every call site, and intake no longer sets screens at all — it does not
>    know which archetype it is.
>
> **The second live call.** Same idea as Phase 3's, so the two are comparable.
> With both archetypes installed it classified *"a cat and dog themed 3d chess
> app"* as `turn-based-game`, high confidence, and still refused the 3D
> honestly. Discrimination works.
>
> It found a second prompt defect on the way: the model returned `rules_depth`
> beside the archetype's own fixed `rules_enforcement`. The prompt told it not
> to repeat the fixed questions and **never showed them** — and could not defer
> that, because the questions are wanted in the same response as the choice. The
> generated menu now carries each archetype's question ids. Unverified, like the
> Phase 3 confidence fix; both re-test on the next live call.
>
> The low-confidence path is still undemonstrated live. It needs an idea that
> fits neither shape, which is a third call and has not been spent.

## Phase 5 — Theme

Cheap, high-visibility, and the axis that does the most for "relatable" per unit
of work.

- [x] `theme` reaches the UI pass only. No other pass reads it, and a test
      asserts that: a theme that can change routes or models is an archetype
      wearing the wrong name
- [x] The UI brief asks for drawn inline SVG on-theme — the existing prompt
      already insists artwork is drawn rather than emoji, and this gives that
      instruction a subject
- [x] The offline baseline ignores `theme` and produces the plain look. Themes
      cost nothing in baseline maintenance, which is exactly why they are a
      separate axis
- [x] **Phase 2's deferred item, now that it has somewhere to go.** The
      board-game essay leaves `intake.SYSTEM` and `turn-based-game.brief()`
      keeps it — which required wiring the brief *into* intake, because intake
      is the one pass with no spec to read the archetype off. Removing the
      prose without that would have been a deletion, not a move

> **Phase 5 landed, and the axis paid off exactly as designed.** The rule was
> not true when the phase started, which is the first thing checking it found:
> `spec_block()` dumps the entire spec as JSON into every code pass, so every
> pass *was* being shown the theme. "The UI pass only" was a claim about
> prompts that nothing could check. It is now a property of one tuple —
> `_shared.PASS_HIDDEN` — with `ui.theme_block()` the only thing that puts the
> theme back. Reverting that tuple to `()` fails three tests, which is the
> check that the gate bites rather than decorates.
>
> **One live call, on the UI pass only.** Everything before it was the offline
> baseline, so the call bought exactly the question the baseline cannot
> answer: does a theme that exists only as prompt text reach the templates?
>
> It generated six templates for a `turn-based-game` themed *cats and dogs,
> warm ginger and slate blue, paw prints, playful*. A drawn ginger kitten and
> a slate-blue puppy, both real vector shapes; the paw print defined once as a
> Jinja macro and reused as bullet, accent and board marker; every colour a
> `fill` or `stroke` presentation attribute. **No `<style>`, no CSS, no
> JavaScript** — the three things the block forbids in the same breath as it
> asks for a palette, which was the part most likely to fail.
>
> Then the load-bearing check: the live templates were run against the
> **offline baseline's own generated suite**, and passed 12/12 including
> `test_playing_to_a_win_shows_the_result`. Same models, same routes, same
> tests, different look. That is the axis being real, measured rather than
> asserted — a theme that had reached anything but the templates would have
> broken one of those twelve.
>
> **The call found a prompt defect, as every one of these has.** The UI task's
> screen-shape rules told it a detail page carries Edit and Delete controls.
> That is CRUD's shape, stated unconditionally, and `turn-based-game`'s routes
> define neither endpoint — so the instruction was asking for a form posting
> to a path no route serves, which is a 405. The model caught it and said so
> in its notes rather than complying, which is the good outcome and not one to
> rely on. The rule now says to read `routes.py` and offer only what it
> serves.
>
> Worth naming: that is the same class as the intake prose this phase moved —
> a shape-specific instruction living somewhere every shape pays for it. The
> axis keeps finding them because it is the first thing that ever made the
> distinction visible.

## Phase 6 — The journey, in the front end

Last, deliberately: the web form is a *rendering* of the question set, and until
Phases 3–4 exist there is nothing to render.

- [x] `clarify.html` shows the archetype it inferred and lets the user change it
      before answering — the classification is the highest-leverage thing to
      correct, and the cheapest moment to correct it is before any tokens.
      Landed in Phase 3; overruling is a GET with no model call
- [x] Fixed and model-generated questions render distinguishably, because they
      are not the same kind of thing. Landed in Phase 3
- [x] Theme gets its own small control rather than being buried in a free-text
      box. Landed in Phase 3
- [x] `proto serve` stays a second *caller* of the pipeline, never a second
      implementation — the existing rule, restated because this phase is where
      it is most tempting to break. **This was the one that was false**, and
      the only real work left in the phase

> **Phase 6 landed, and the last item was not a restatement.** The first three
> had already been built by Phases 3 and 4; the fourth was a claim the code
> did not support. `web/app.py`'s own docstring said it was "a second caller of
> the pipeline, not a second implementation of it" while assigning the same
> seven spec fields `cli.py` assigns, in parallel. They agreed only because one
> person wrote both — and adding `PassContext.archetype` in Phase 5 needed an
> edit in each, with nothing to fail had only one been made.
>
> That is the workspace's seam rule playing out inside a single repo, so the
> fix is the same shape: one implementation (`build.spec_from_idea`,
> `build.amend_spec`) and a test that recomputes the offenders rather than
> listing them — every assignment to a spec attribute anywhere in the package
> must live in the module that owns the decision.
>
> **It was already broken, and silently.** `proto add` builds its updated spec
> from an amend response, and the amend schema is the intake schema — which
> omits `MODEL_OWNED_EXCLUSIONS`. So a model that answered perfectly still
> could not return `archetype`, `theme`, `answers` or `extra`, and nothing
> carried them across. One `proto add "add a timer"` on a `turn-based-game`
> project reset it to `crud`, dropped the theme and the answers, reverted the
> board to the default, and the next generation built a tracking app over a
> game's entities. Nothing went red at any point.
>
> The set that survives an amend is now **derived** from
> `MODEL_OWNED_EXCLUSIONS` rather than written down, so the next field added
> there is carried without anybody remembering this rule exists. A hand-written
> list is what turned a Phase 1 decision into a Phase 6 defect in the first
> place.

## Acceptance

- [x] `./pp test unit` green, and `./pp check pre-push` green
- [x] Phase 2's characterisation test: offline CRUD generation is byte-identical
      to `a79e41b`'s output for the same spec
- [x] ~~`proto new "cat themed chess" --offline` produces a spec whose
      `archetype == "turn-based-game"`~~ — **this criterion was unachievable as
      written, and correcting it is more useful than ticking it.** `--offline`
      means the classifier does not run: the offline baseline cannot read an
      idea, so it returns the default by design, and asking it to infer
      `turn-based-game` from the words "cat themed chess" was asking the
      baseline to do the one thing it exists not to do. The criterion was
      written in Phase 0, before the classifier's shape was settled. Split in
      two, both verified by running them:
      `proto new "cat themed chess" --archetype turn-based-game --offline`
      yields `/`, `/board`, `/matches`, `/matches/{row_id}` — a board that is
      not a `list`, `detail` or `form`; and the live classifier's half is the
      Phase 4 call, which chose `turn-based-game` for this idea unprompted
- [x] The same idea with `--archetype crud` produces the CRUD spread instead —
      `/`, `/cats`, `/cats/new`, `/cats/{row_id}`. Same words in, different
      shape out, so the axis is real and not the classifier's opinion baked in
- [x] A `spec.json` written before this plan loads without error and generates
      the same app it did before — `prototypes/kitten_chess/` loads with
      `archetype == "crud"` and no theme
- [x] Grep proves it: no archetype module imports `requirements.txt`, the
      Dockerfile or the compose file, enforced by a test rather than a rule
- [x] `theme` appears in the UI pass's prompt and in no other pass's, enforced
      by a test
- [x] A generated `turn-based-game` boots and a turn can be taken through the
      browser stage — Phase 4, played to a win over HTTP

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
