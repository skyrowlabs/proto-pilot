# Squirrel survival — a worked example

One real `proto plan` run, read end to end. The tree it wrote is
[`squirrel_survival/`](squirrel_survival/PLAN.md), committed as written apart
from its research transcripts (see [the shelf's rules](README.md#rules-for-the-trees)).

> **Run:** 2026-11-16, `claude-code` backend (model `claude-opus-5`, effort high),
> `--depth standard`, research on, dreaming on, `--yes`. **Result:** green,
> exit 0. 6 of 6 topics researched, 22 sources cited, 6 dreams (2 proposed,
> 4 set aside). Research took about 17 minutes, 96–127 s a topic.

## The input

The idea is one sentence. Everything else is the **brief**, and every field of
it is filled in here, to show what each flag does:

```bash
proto plan "a survival game where you play a squirrel getting through its first winter" \
  --goal "decide whether a small playable slice is worth building, and what to build first" \
  --for "players who like short survival games that are cozy but tense" \
  --horizon "about three months of evenings and weekends, one developer" \
  --must "2D and single-player" \
  --must "one forest and one winter, start to finish" \
  --not "multiplayer" \
  --not "monetisation and a storefront launch" \
  --backend claude-code --yes --dir squirrel_survival
```

| Flag | Became | Who decides it |
| ---- | ------ | -------------- |
| `--goal` | **Goal** in `PLAN.md`, kept as written | You |
| `--for` | **Audience**, kept as written | You |
| `--horizon` | **Horizon**, kept as written | You |
| `--must` (×2) | The first two **Constraints** | You; the model may add more after them |
| `--not` (×2) | **Out of scope**, its own section, and told to every pass after scope | You |
| *(nothing given)* | Engine, art pipeline, what counts as evidence | Left blank, so scope asked about them |

Without a terminal you can type all of that as flags, as above. At a terminal,
`proto plan` with no idea asks for each field in turn, and Enter on any of them
leaves it to the model.

`--yes` was passed because this run was made unattended. A person would normally
drop it, answer scope's questions and edit the outline at the review.

## What the review showed

This is the checkpoint a person would have edited. `(yours)` marks what came from
the brief, so you can tell your words from the model's at a glance:

```
A survival game where you play a squirrel getting through its first winter
  goal: decide whether a small playable slice is worth building, and what to build first (yours)
  audience: players who like short survival games that are cozy but tense (yours)
  horizon: about three months of evenings and weekends, one developer (yours)
  constraint: 2D and single-player (yours)
  constraint: one forest and one winter, start to finish (yours)
  constraint: Multiplayer is out of scope
  constraint: Monetisation and a storefront launch are out of scope
  out of scope: multiplayer
  out of scope: monetisation and a storefront launch
  open question: What would count as evidence that the slice is worth continuing ...?
  open question: Does the developer already have an engine and 2D toolchain ...?
  open question: Is art and audio production part of this three months ...?
  depth: standard (6 topics)
  topics:
    1. What makes it cozy and tense at once (cozy_tense_contract)
    2. The hoarding loop and what the player remembers (caching_and_memory_loop)
    3. Shape of one winter, start to finish (winter_arc_pacing)
    4. Being small, cold and hunted in 2D (prey_animal_verbs)
    5. How much real squirrel behaviour to simulate (simulation_versus_legibility)
    6. What the first slice contains and how it is judged (slice_scope_and_evidence)
```

The two unmarked constraints repeat the `--not` items. That is a defect in the
scope prompt this run was made with, and it was fixed in the same change (see
[What this run found](#what-this-run-found)). It is left in the tree because the
tree is the run, not a cleaned-up version of it.

## Reading the plan

**Start at [`PLAN.md`](squirrel_survival/PLAN.md).** It holds the brief, the
topic map, how the topics connect, and five ordered first steps.

- **The topics are about this game, not about "a project".** None of the six is a
  generic heading like *audience* or *resources*. The run's best one is
  [the hoarding loop](squirrel_survival/topics/caching_and_memory_loop.md): it
  frames caching as a choice between bookkeeping, navigation and recall, and the
  rest of the plan keys off that choice.
- **Research found real comparables.** *Winter Burrow*, a cozy mouse survival
  game, is cited for exactly the risk this plan carries: reviewers found its
  gathering a chore. *Shelter*, *Don't Starve*, *The Flame in the Flood* and
  *Rain World* appear too, along with a fox-squirrel "spatial chunking" study,
  which the hoarding topic turns into a player-facing memory structure. Every
  page is listed in [`sources.md`](squirrel_survival/sources.md).
- **Uncited findings say so.** Each topic ends its findings with one or two
  **Assumption:** lines: the model's recommendations, kept apart from what a page
  backed.
- **The first steps follow the dependencies.** Step 1 is the 2D camera decision,
  side-on or top-down, because *Being small, cold and hunted in 2D* depends on
  nothing and nearly everything depends on it. The slice definition comes last,
  because it depends on all four topics before it.
- **Dreams stay out of the plan.** [`dreams.md`](squirrel_survival/dreams.md)
  proposes two. *d2, "You win by forgetting"* turns lost acorns into saplings, so
  the score is the forest you leave. *d4, "One night, one cache, five minutes"*
  is a weekend build judged by whether playtesters lower their voices. The four
  set aside each keep their reason. d5 broke the `--not "multiplayer"` line, and
  the evaluator set it aside for exactly that.

To act on a dream, a person runs `proto dream promote d4` inside the tree. No
pass can do it.

## What this run found

These are observations from reading the run. They are not the operator's
five-line read that
[living-plans Phase 1](../TODO/living-plans.md#phase-1--use-it-on-real-ideas-and-write-down-what-was-missing)
asks for. That read is a person's, and it is still open in the *Dogfood record*.

1. **Fixed in this change:** the scope model restated every `--not` item as a
   constraint, so each appeared twice. The scope prompt now names out-of-scope
   items as already recorded. **Checked 2026-11-16:** with the fixed prompt and
   the same brief, 0 of 5 live samples restated a `--not` item (four calls of
   the scope pass alone and one full `--no-research` run). In all five the model
   added no constraints of its own and returned only questions. It is still a
   prompt fix with no deterministic guard, so five clean samples make it likely,
   not certain.
2. **The steps are walls of text.** Each *Where to start* entry runs 150–200
   words, because the action and its reason render as one paragraph. A reader
   wants the action first and short. **Fixed after this run:** the start pass now
   holds `action` to 30 words and `why` to 25, and `PLAN.md` puts the reason on
   its own *Why here* line. On the same brief, a live `--no-research` run then
   wrote steps of 20–24 and 19–22 words (this tree's were 80–106 and 76–88).
   The first try at the cap lost every comma and full stop, until the prompt said
   punctuation was allowed. This tree keeps its long steps, because it is the
   record of its run.
3. **No step answers an open question.** Scope asked whether an engine is already
   chosen, and nothing in the plan comes back to it. Open questions are rendered
   and then never used, which is
   [living-plans](../TODO/living-plans.md)' *"a question left open stays open"*,
   seen on a real run.
4. **An Assumption line can still name things.** *"Rust allows five"* (map
   markers) sits under **Assumption:** in the hoarding topic. It is labelled
   honestly, but it is a checkable claim that research did not check.
5. **The research transcripts fingerprint the machine** that ran them: home
   paths, installed skills and plugins, the Claude Code version. That is why this
   tree was committed without them. Filed as
   [#51](https://github.com/skyrowlabs/proto-pilot/issues/51).

## Rerunning it

The same command in an empty folder writes a different plan, because both the
model and the web move. To compare, run it into a new `--dir`.

**Do not rerun it on the committed tree.** A rerun there is a re-render: no model
is called, but every page is overwritten. With the transcripts absent the plan
goes red at `sources_fetched`, is stamped *Not researched* and *Not verified*,
gains a `RUNBOOK.md`, and exits 1. That is the ledger working as designed (it
believes only what it can see was fetched), and it is the wrong thing to commit.
To try it, copy the tree somewhere else first.
