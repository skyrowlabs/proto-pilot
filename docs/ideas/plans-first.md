# Plans first — the pivot to architectural planning

> **Status: a direction, decided.** Jeston, 2026-11-06. It supersedes decision 1
> of [sketches-not-scaffolds](sketches-not-scaffolds.md). The plan that builds it
> is [`plan-prototypes`](../implementations/spec/plan-prototypes.md); this doc holds the argument
> and the plan holds the phases.

## The decisions

1. **proto.pilot's product is now planning.** `proto plan` and `proto dream` are
   what the tool is for: research, topics and how they connect, things to consider,
   where to start, and extensions of the idea.
2. ~~Physical prototyping is tabled, not deleted.~~ **Superseded 2026-11-11.**
   Jeston ruled that the physical prototyping layer is removed outright and the
   written plan is featured: the generator, both targets and both front ends left
   the tree, and the CLI is `plan`, `dream`, `ls`, `rm`, `prune` and `doctor`.
   The plan that did it is
   [remove-prototyping](../TODO/remove-prototyping.md), and the last commit that
   holds both layers is the tag `prototyping-final`.
3. **A physical prototype comes later in an idea's life, if at all.** It belongs
   after the idea is concrete and agents have more to work with. Since
   2026-11-11 nothing in this tree builds one, so a later prototype would be
   designed from what a plan needs rather than revived; that is a possibility,
   not a commitment.

This changes the original intent, and that is accepted: the output is more usable.

## Why

`proto new` makes its biggest decisions when it knows the least. Intake has to
reduce an idea to 1–4 entities before anything about it has been examined, so the
prototype reflects a first guess. A plan is useful earlier, and it gives any later
prototype something real to build from.

It also fits the portfolio better. skeletor starts a repo once you know what you
are building; nothing here helped work out what that is.

## What carries over

- **From sketches-not-scaffolds:** decision 2 holds, since a plan is also evidence
  to learn from. Decision 3, shipping as a tool others run, is untouched by this.
- **From the pipeline:** the `LLM` protocol, the job seam, the bounded repair loop,
  the human checkpoint and the offline twins. These are what the plan pipeline
  kept when the rest was removed.

## What this costs

*Verified by running* was the tool's strongest proof, and a document cannot be run.
The plan's checks prove coherence and traceability, never truth. A later prototype
that tests a plan's riskiest assumption is the most likely way to earn that back,
and since 2026-11-11 it would have to be built anew: the code that ran one is
readable at the tag `prototyping-final` and nowhere on a branch.

## What changes when

The two plans that were parked on this direction
([Improvement Loop](../implementations/dropped/improvement-loop.md),
[Drawing Freedom](../implementations/dropped/drawing-freedom.md)) were dropped on
2026-11-11, never built: the layer they extend was removed. The README leads with
`proto plan`, says what it does not do yet, and describes no other product.
