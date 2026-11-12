---
title: "Living Plans"
slug: living-plans
shelf_status: planned
priority: medium
updated: 2026-11-11
tags: [plan, cli, research, verify, handoff]
summary: "Let a plan be revised, tested and handed off after it is made: answer its questions, change or re-research one topic, record what a real test showed, and emit a brief another tool can start from."
---

# Living Plans

> **Status**: 🔴 Planned
> **Shelf-Status**: planned
> **Priority**: Medium — the product after [remove-prototyping](../implementations/spec/remove-prototyping.md) is one command and a pool of dreams
> **Updated**: 2026-11-11
> **Depends on**: [`remove-prototyping.md`](../implementations/spec/remove-prototyping.md) — every phase here edits `protopilot/cli.py` and `registry.py`, which that plan rewrites

Not `ready`: Phase 1 is a person's reading, and its findings may reorder or cut
the rest. Each later phase also lists questions only Jeston can answer.

The slug is not `plan-depth` because `--depth` already means topic count
(`model.TOPIC_COUNTS`), and this plan is about a plan's life after it is made.

## Problem

A plan is finished the moment it is written. Measured against `protopilot/plan/`
at `f0e88ef`:

- **The only verbs that change a plan are the dream verbs.**
  `pipeline.dream_round`, `promote` and `drop` are the three writers after
  `build`. Running `proto plan` again with the same idea calls
  `pipeline.rerender`, which redraws and changes nothing. A different idea or
  direction in the same folder is refused by `existing_plan`.
- **A question left open stays open.** `scope` asks up to three
  (`scope.MAX_QUESTIONS`); the CLI prompts once, before the outline;
  `scope.answered` folds an answer into `constraints`. After that
  `Plan.questions` is rendered into `PLAN.md` and nothing can answer one.
- **The outline can be edited for thirty seconds.** `outline.add`, `drop` and
  `rename` exist and are reachable only inside `_review_outline`, before
  anything is researched.
- **One bad topic costs the plan.** Research is already one call and one
  transcript per topic (`pipeline._research_topic`, `.protopilot/research/`),
  but a topic whose research failed, or cited nothing, can only be fixed by
  making the whole plan again somewhere else. A promoted dream is never
  researched at all (`README.md`, *What a plan does not know yet*).
- **A plan ends at its own folder.** Decision 1 of
  [plan-prototypes](../implementations/spec/plan-prototypes.md) ruled
  `proto plan export --single` for sharing. It was never built. Nothing emits
  what a coding agent or a scaffolder would need to start.
- **The proof was given up and not replaced.** plans-first, *What this costs*:
  "a document cannot be run". The verifier proves coherence and traceability,
  never truth, and the green line says so. Nothing in a plan records what
  happened when somebody tried the first step.
- **Research has one backend.** `ClaudeLLM.research_refusal` is `API_RESEARCH`:
  the API backend's web search "has never been run here". That deferral is
  carried twice in plan-prototypes (Phases 1 and 6).

## Approach

Five phases in order of value. The first is use, not code. Every phase that
writes to a plan obeys the rules the plan package already holds, restated here
because they are what a new verb is most likely to break:

- `plan.json` is the truth; markdown is rendered from it and a hand edit is
  overwritten (Decision 4). No verb reads the markdown back.
- Every writer goes `_held` → change → `repaired` → `_land`, so a change that
  leaves the plan red is put back (`_put_back`) or handed over with a
  `RUNBOOK.md`. No new verb gets its own save path.
- Every pass has an offline twin, and the suite runs on it.
- A dream is promoted only by a person. A finding is cited only if this tree's
  transcripts show the page fetched.
- Model output is data. A new verb's model call holds `llm.ISOLATION`, or
  `RESEARCH_ISOLATION` if it researches, and nothing wider.

## Phase 1 — Use it on real ideas, and write down what was missing

**Problem.** The plan pipeline has been read by its owner on two ideas: a
bakery and a tool library. Both were invented for the README. Every later phase
here is a guess about what a real plan lacks.

**Design.** No code. Three to five runs with research on ideas somebody is
actually deciding about. The workspace has two at concept stage, which makes
them fair tests: house.fly (research notes, no code) and Node Zero (design
maturing, no code).

- [ ] `proto plan` with research, `--depth standard`, on house.fly's idea, from
      a sentence and a direction written without opening its notes (~operator)
- [ ] The same for Node Zero (~operator)
- [ ] One to three more: one idea that is not software, and one Jeston already
      knows well enough to catch a wrong finding (~operator)
- [ ] For each run, record under *Dogfood record* below: wall time, topics
      researched / failed / nothing cited, and the operator's read in five
      lines — the topic he would not have thought of, the finding that was
      wrong or empty, the open question he wanted to answer and could not, what
      he did next with the plan, and what he wished it had handed him
      (~operator)
- [ ] Compare each plan to what the project's own docs already say, after the
      read is written, not before (~operator)
- [ ] Rewrite the order of Phases 2–5 from the record, cut any phase no run
      asked for, and say so in *Dropped, and why*
- [ ] Any defect a run shows goes through `./pp bug`, not into this plan

**Done is checked by:** the record holds at least three runs, each with all
five lines, and the phase order below carries a sentence saying which run put
each phase where it is.

**Ruled by Jeston, 2026-11-11:** house.fly's and Node Zero's ideas may go
through the model, and the resulting plans may be committed to those repos. Each
commit is a change in that repo, under its own rules.

**Ruled by Jeston, 2026-11-11:** three runs first, then decide whether two more are worth it.

### Dogfood record

_Empty until Phase 1 runs._

## Phase 2 — Revise a plan after it is made

**Problem.** See the first four bullets of *Problem*.

**Design sketch.** A `proto plan` that is a group would break
`proto plan "an idea"`, so the verbs sit beside it, shaped like `proto dream`'s:
a positional for the thing, `--dir` defaulting to the current folder, one job
each, exit 1 on red.

| Verb | Model calls | Reuses |
| --- | --- | --- |
| `proto answer [N] [--dir]` | 0, plus repair | `scope.answered` |
| `proto topic add TITLE --why WHY` | `consider` for it, `connect`, `start`, repair | `outline.add`, `dreaming.promoted`'s landing path |
| `proto topic drop SLUG --why WHY` | `start` if a step named it, repair | `outline.drop` |
| `proto topic rename SLUG TITLE` | 0 | `outline.rename` |
| `proto research SLUG [--deeper]` | 1 research call, then `connect`, repair | `pipeline._research_topic`, `ledger` |

How a partial rerun behaves, which is the part that has to be decided before
any of it is built:

- **Answering a question changes nothing else by itself.** The answer becomes a
  constraint, the question leaves `questions`, the tree is redrawn. It does not
  re-run `outline` or research: a person who wants the answer to move a topic
  runs `proto research` on that topic, and the answer is in its prompt because
  `constraints` already is.
- **A slug is an identity.** `rename` changes the title and keeps the slug,
  the file name, the edges, the steps, the dream anchors and the research
  record. Today `outline.rename` runs before any of those exist; check what it
  does to the slug and split it if it re-slugs.
- **Dropping a topic removes what pointed at it, and says what it removed.**
  Edges from or to it go. A step on it goes, and `start` runs again if that
  leaves the first step with an unmet dependency (`verify.start_order` is the
  check). A dream anchored to it is not deleted: it is set aside with the
  reason "its topic was dropped", because what was ruled out is kept. The
  topic's transcript stays in `.protopilot/research/` and its sources leave
  `sources.md` only if no other topic cites them. `MIN_TOPICS` still binds.
- **The dropped topic is remembered**, as a dropped dream is, so a later
  `proto topic add` of the same title is told it was dropped and why. That
  needs one new list on `Plan`, omitted from `plan.json` when empty, as
  `research` is.
- **Re-research replaces one topic's record, never merges.** The new transcript
  is written beside the old under a new name, `TopicResearch` for that slug
  points at the new one, and the topic's findings are replaced. Findings from a
  transcript the ledger no longer points at would otherwise be cited to a fetch
  nothing vouches for. `ledger.reconciled` already redraws the ledger from
  transcripts on load; it must be shown to pick the current one. `connect`
  runs again because edges rest on findings; `consider` for that topic runs
  again; other topics' text is not touched.
- **`--deeper`** raises that one call's findings and page budget one step
  (`research` reads them from `Plan.depth`). It is per call and not stored, so
  `depth` keeps meaning what the outline was asked for.
- **Verify and repair run on the whole plan every time**, as now. The repair
  pass may edit any part of `plan.json`; on a partial rerun it is told which
  topic changed and a repair that alters a different topic's findings is
  rejected, the way the dream path already holds a plan (`held` in
  `pipeline.repaired`).
- **An unresearched plan stays stamped.** Researching one topic of a plan made
  with `--no-research` gives per-topic stamps, which `render._topic_stamp`
  already draws; `Plan.researched` and the `PLAN.md` stamp need a third state,
  "partly". Check `render._stamp` and `verify.sources_fetched` for the
  assumption that it is all or none.
- **Offline:** `answer`, `rename` and `drop` need no model. `topic add
  --offline` lands as an offline promote does: no risks, unknowns or decisions,
  not researched. `research --offline` is refused in a sentence.

Tasks:

- [x] Characterise first: tests that pin what `outline.rename`, `outline.drop`
      and `ledger.reconciled` do to a *finished* plan today, before changing any
- [x] `proto answer`, with its offline twin being the whole thing
- [ ] `proto topic rename`, then `drop`, then `add`, each landing through `_land`
- [ ] The dropped-topics list on `Plan`, with a test that an old `plan.json`
      without it loads and saves byte-identical
- [ ] `proto research SLUG`, resumable as the first run's research is
- [ ] The held-topic guard on repair, with a planted repair that rewrites
      another topic
- [ ] The partly-researched stamp, with a planted-failure test per check it
      touches, as `test_every_check_has_a_planted_failure` requires
- [ ] `docs/CLI.md`, `README.md` commands, and `ARCHITECTURE.md`'s plan pipeline
      section, in the same change

**Done is checked by:** on the offline tool-library plan, `proto topic drop`
then `proto topic add` then `proto answer` each exit 0, `git diff` on the tree
shows only the pages that name the changed topic plus `PLAN.md`, and every other
topic file is byte-identical. With a scripted research backend,
`proto research SLUG` changes that topic's file, `sources.md` and `PLAN.md` and
nothing else.

**Open questions for Jeston**

1. `proto answer` and `proto topic` and `proto research` as top-level verbs, or
   one group (`proto revise …`)? **Ruled 2026-11-11: top-level.** Each
   is a noun a plan already has, it matches `proto dream`, and a group makes
   `proto revise topic add` three words deep. The cost is a longer `--help`.
2. When an answer plainly changes a topic, should the tool say "this answer
   touches *Audience*; run `proto research audience`", or stay silent? The
   first needs a model call to judge.
3. Does a dropped topic's dream get set aside (proposed above) or dropped?
   **Ruled 2026-11-11: set aside, with the reason.**

## Phase 3 — A plan as a handoff

**Problem.** A plan is read by a person and then retyped: into a prompt for a
coding agent, into `skeletor-new`'s arguments, into a message. Decision 1's
`export --single` was the ruled answer for sharing and was never built.

**Design sketch.** Two renders from `plan.json`, deterministic, no model call,
both in `protopilot/plan/render.py` beside `render()`:

- `proto export --single [--dir] [--to FILE]`: the tree as one markdown file.
  Dreams stay in their own section under their own heading, so the medium still
  enforces the label (`verify.dreams_apart` is the rule it must not break).
- `proto export --brief [--dir] [--to FILE]`: a `BRIEF.md` with two readers in
  order (ruled 2026-11-11): **a person, who understands, directs and approves
  it, and then an agent, which implements it.** It opens with what a person
  needs to rule on in one screen, and the agent's section follows. Goal, audience, horizon, constraints; the first steps in order with
  their reasons; per topic, the decisions somebody must make and the risks;
  open questions; and a plain statement of what is an assumption. **It carries
  no finding as a fact unless it is cited**, and it says how many are not. A
  red plan is refused: a handoff of something known to be incoherent is worse
  than none.

**skeletor is not a reader of the brief** (ruled 2026-11-11). It carries no
front matter shaped for `skeletor-new` and nothing here is reported to skeletor.

- The person's part comes first: the goal, what was assumed and not checked,
  the decisions the plan leaves to them, and the first step. They direct by
  revising the plan (Phase 2) and exporting again, never by editing the brief.
- Approval is recorded in `plan.json` (who is not stored; the date and the
  plan's state at that moment are), and the brief says whether the plan it was
  drawn from is the approved one. A plan changed after approval says so.
- The format is written down once, in `docs/ARCHITECTURE.md`, with a version
  field, because an agent prompt somewhere will hold an assumption about it.

Tasks:

- [ ] `render.single(plan)` and `render.brief(plan)`, byte-stable, each with a
      golden manifest beside `tests/golden/plan_offline_manifest.json`
- [ ] `proto export`, refusing a red plan and a tree that is not a plan
- [ ] A test that no dream text reaches the brief, reusing `verify.leaks`
- [ ] The approval record, written by a verb that calls no model and lands
      through `_land`; a test that a plan changed after approval exports a brief
      saying so
- [ ] Run the real readers, and record what happened here: Jeston reads a
      `BRIEF.md` from a Phase 1 plan and says whether he could approve from it
      alone (~operator); the approved brief is handed to a coding agent in an
      empty directory, and what it does first is read (~operator)

**Done is checked by:** both goldens stable across two runs; `proto export
--brief` on a red plan exits 1 and writes nothing; and the two operator runs
are recorded with what each reader got wrong.

**Open questions for Jeston**

1. Does approving need its own verb (`proto approve`), or is it a flag on
   `proto export --brief`? A verb keeps "I read it" apart from "I made a file".
   **Ruled 2026-11-11: its own verb, and the approval is recorded in the plan.**
2. Should `BRIEF.md` be written by every `proto plan`, as an eleventh file, or
   only on request? **Ruled 2026-11-11: only on request**, so the offline golden
   does not move.

## Phase 4 — Earn back "verified by running"

**Problem.** plans-first, *What this costs*: the strongest proof the tool had
is gone, and "a later prototype that tests a plan's riskiest assumption is the
most likely way to earn that back". With prototyping removed, the test is the
person's to run. The plan can still name it and keep the result.

**Design sketch.**

- A new record on `Plan`: `Probe` — `id`, `topic`, `assumption` (the exact text
  of one `Finding` with `assumption: true`, or one `unknown`), `test` (the
  cheapest thing that would show it false), `would_change` (what in the plan
  moves if it is false), and an optional `outcome`.
- A new pass, `probe`, after `start`: it picks **one** assumption, the one the
  most steps rest on through `depends-on`, and writes the test. The graph
  constrains the choice and the model writes the reasoning, as `start` does.
  Its offline twin picks the first assumption of the first step's topic.
- A new check, `probe_grounded`: the probe's text is one of the plan's own
  assumptions or unknowns, verbatim, and its topic exists. This is what stops
  the model inventing a risk the plan does not hold.
- `proto probe record --held | --broke --note "what happened" [--dir]` writes
  the outcome. It calls no model. `Outcome` holds the verdict, the note, and
  the date, and is marked as **the operator's word**: rendered under its own
  heading as evidence a person reported, never as a cited finding, and
  `findings_traced` does not count it as a source.
- On re-render: `PLAN.md` leads with the probe and its outcome. `--held` moves
  nothing else. `--broke` marks the finding as contradicted on its topic page
  and prints the `would_change` line with the verb to run
  (`proto research SLUG`); it does not rewrite the plan by itself.
- The green line changes only in what it claims: "one assumption was tested by
  a person on DATE" when an outcome exists. It still never says true.

Tasks:

- [ ] `Probe` and `Outcome` on the model; old `plan.json` loads and saves
      byte-identical when neither is present
- [ ] `passes/probe.py` with its twin, wired into `pipeline._passes`
- [ ] `verify.probe_grounded`, with its planted failure
- [ ] `proto probe record`, landing through `_land`
- [ ] `render`: the probe block in `PLAN.md`, the contradicted mark on a topic
      page, the green line's new clause
- [ ] The offline golden moves in this phase, deliberately; record the new
      manifest in the same commit and say why in its body
- [ ] One real probe carried out and recorded on a Phase 1 plan (~operator)

**Done is checked by:** `test_every_check_has_a_planted_failure` covers the new
check; a plan with `--broke` recorded re-renders with the finding marked and
exits 0 if its structure holds; and the operator's one real probe is in the
*Dogfood record*.

**Open questions for Jeston**

1. One probe per plan, or one per first step? **Ruled 2026-11-11: one open
   probe at a time.** One keeps it a decision; several make a
   checklist nobody finishes. Once an outcome is recorded the plan may name the
   next, and recorded probes are kept as history.
2. After `--broke`, should the plan go red until the topic is re-researched?
   The sketch says no: a broken assumption is knowledge, and red means
   incoherent. **Ruled 2026-11-11: no, it stays green.**
3. Is the operator's note enough, or should `record` take a `--evidence` path or
   URL? A URL invites treating it as a fetched source, which it is not.

## Phase 5 — Research stays on the subscription

**Ruled by Jeston, 2026-11-11:** no API credit is bought. Research is done from
subscription usage, which is the `claude-code` backend, and the API backend's
research is not built or measured.

**Problem.** `ClaudeLLM.research_refusal` (`API_RESEARCH`) still reads as a
deferral: the API backend's web search "has never been run here". And the
offline baseline writes the same six topics for every idea
(`plan/baseline.py::TOPICS`), which is what the README's first run shows.

**Design sketch.**

- The refusal becomes final and says what to do: research needs the
  `claude-code` backend and a Claude subscription. The two deferrals carried in
  plan-prototypes (Phases 1 and 6) are closed by pointing here.
- *Offline baseline.* It cannot research and must not pretend to. What it can do
  without a model is stop being identical: pick its topics from a few fixed sets
  by cheap signals in the idea (a place, a product, an event, a piece of
  software), still deterministic, still stamped *Not researched*, every finding
  still an assumption.

Tasks:

- [ ] Reword `API_RESEARCH` as a final refusal that names the backend to use,
      and update the test that pins its text
- [ ] `README.md`, *What a plan does not know yet*, says research runs on a
      subscription only and why

**Done is checked by:** `proto plan --backend api` without `--no-research` says
in one sentence which backend researches.

**Open questions for Jeston**

1. A less generic baseline is more code that no real plan uses. Is the offline
   run a demo worth improving, or only the test suite's fixture?
   **Ruled 2026-11-11: fixture only. The baseline task above is cut.**

## Acceptance

- [ ] `./pp test unit` green, no network and no key, after each phase
- [ ] Phase 1's record holds at least three operator reads
- [ ] A `plan.json` written before this plan loads and saves byte-identical
      after every phase (one fixture, asserted in each phase's tests)
- [ ] Every new verify check has a planted failure
- [ ] Every new verb that changes a plan either lands it green or puts the old
      `plan.json` back, shown by a test that makes the landing fail
- [ ] `proto --help` and `docs/CLI.md` agree, by
      `tests/test_docs_name_real_commands.py`

## Dropped, and why

- **A plan viewer in the browser or the terminal.** Removed with both front
  ends on 2026-11-11. A plan is markdown and every editor already reads it.
  Possible later, and Phase 3's `--single` is the cheap version of it. Not in
  scope here: a reader should be designed from what Phase 1 shows people do
  with a plan, not from what the old console did with a build.
- **Editing the rendered markdown and reading it back.** Decision 4 of
  plan-prototypes stands. A verb per kind of change is more typing and keeps
  one truth; two-way sync is where a guess becomes a finding unnoticed.
- **Regenerating the whole plan when anything changes.** It is what exists
  today by another name, costs every topic's research again, and loses the
  topics a person already read.
- **`proto new --from-plan`.** Deferred in plan-prototypes Phase 7; now there is
  no `proto new` to feed. Phase 3's brief is the handoff, and what builds from
  it is somebody else's tool.
- **Handing the plan to the Improvement Loop for repeat research rounds.** Also
  deferred there. That design is filed as dropped; `proto research SLUG` is the
  one-topic version a person asks for.
- **Having the model judge whether its own findings are true.** A second call
  with the same blind spot. Phase 4 puts the judgement where the evidence is:
  a person who tried it.
- **Counting a recorded outcome as a source.** It was not fetched and no
  transcript vouches for it. It is rendered as the operator's word, apart.
- **A less generic offline baseline.** Ruled out 2026-11-11: the offline run is
  the test suite's fixture, and no real plan is made with it.
- **Research on the API backend.** Ruled out 2026-11-11: it needs API credit
  bought to measure it, and research is to come from subscription usage.
- **A brief shaped for `skeletor-new`.** Ruled out 2026-11-11: the brief's
  readers are a person and then an agent.
- **Running research on several topics in parallel.** It would cut wall time,
  and plan-prototypes measured two minutes a topic in series. Left out: no
  Phase 1 run has yet said the wait is the problem, and parallel subscription
  calls are an account-limit question nobody has measured.
