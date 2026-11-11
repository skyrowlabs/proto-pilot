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
> **Priority**: Medium — the product after [remove-prototyping](remove-prototyping.md) is one command and a pool of dreams
> **Updated**: 2026-11-11
> **Depends on**: [`remove-prototyping.md`](remove-prototyping.md) — every phase here edits `protopilot/cli.py` and `registry.py`, which that plan rewrites

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

**Open questions for Jeston**

1. Is it acceptable to put house.fly's and Node Zero's ideas through a model on
   the `claude-code` backend, and may the resulting plans be committed to those
   repos, or do they stay local?
2. Three runs or five? Each is 10–20 minutes of research at `standard`.

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

- [ ] Characterise first: tests that pin what `outline.rename`, `outline.drop`
      and `ledger.reconciled` do to a *finished* plan today, before changing any
- [ ] `proto answer`, with its offline twin being the whole thing
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
   one group (`proto revise …`)? Top-level is shorter and matches `proto dream`;
   it also puts three more words in a `--help` that was just cut to six.
2. When an answer plainly changes a topic, should the tool say "this answer
   touches *Audience*; run `proto research audience`", or stay silent? The
   first needs a model call to judge.
3. Does a dropped topic's dream get set aside (proposed above) or dropped?

## Phase 3 — A plan as a handoff

**Problem.** A plan is read by a person and then retyped: into a prompt for a
coding agent, into `skeletor-new`'s arguments, into a message. Decision 1's
`export --single` was the ruled answer for sharing and was never built.

**Design sketch.** Two renders from `plan.json`, deterministic, no model call,
both in `protopilot/plan/render.py` beside `render()`:

- `proto export --single [--dir] [--to FILE]`: the tree as one markdown file.
  Dreams stay in their own section under their own heading, so the medium still
  enforces the label (`verify.dreams_apart` is the rule it must not break).
- `proto export --brief [--dir] [--to FILE]`: a `BRIEF.md` an agent can start
  from. Goal, audience, horizon, constraints; the first steps in order with
  their reasons; per topic, the decisions somebody must make and the risks;
  open questions; and a plain statement of what is an assumption. **It carries
  no finding as a fact unless it is cited**, and it says how many are not. A
  red plan is refused: a handoff of something known to be incoherent is worse
  than none.

The seam with skeletor is a published artifact, and the workspace rule applies:
*run the actual consumer against the actual producer before believing either.*
What proto.pilot may know about skeletor is nothing. So:

- The brief has a small front-matter block of neutral facts: `name`, `slug`,
  `tagline` (one sentence, from `goal`). Those happen to be what
  `skeletor-new --name --slug --tagline` takes. No flag names, no tier, no
  language, no command line for skeletor is written by proto.pilot. If skeletor
  wants to read a brief, that reader is skeletor's.
- The format is written down once, in `docs/ARCHITECTURE.md`, as a contract
  with a version field, because a second repo will hold an assumption about it.

Tasks:

- [ ] `render.single(plan)` and `render.brief(plan)`, byte-stable, each with a
      golden manifest beside `tests/golden/plan_offline_manifest.json`
- [ ] `proto export`, refusing a red plan and a tree that is not a plan
- [ ] A test that no dream text reaches the brief, reusing `verify.leaks`
- [ ] Run the real consumers, and record what happened here:
      hand `BRIEF.md` to a coding agent in an empty directory and read what it
      does first (~operator); scaffold with `../skeletor/bin/skeletor-new` using
      the three front-matter values and confirm the tree's gates pass (~operator)
- [ ] Report to skeletor, in its repo, that the brief exists and what its three
      fields are. Whether skeletor grows a reader is skeletor's decision
      (~operator)
- [ ] Add the brief's contract to `skyrow-workspace/strategy/seams/` once a
      second repo reads it (~operator, and a separate change in that repo)

**Done is checked by:** both goldens stable across two runs; `proto export
--brief` on a red plan exits 1 and writes nothing; and the two operator runs
are recorded with what the consumer got wrong.

**Open questions for Jeston**

1. Is the brief for an agent, for skeletor, or for a person forwarding it? One
   file cannot be tuned for all three; the sketch above picks the agent.
2. Should `BRIEF.md` be written by every `proto plan`, as an eleventh file, or
   only on request? An eleventh file moves the offline golden.

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

1. One probe per plan, or one per first step? One keeps it a decision; several
   make it a checklist nobody finishes.
2. After `--broke`, should the plan go red until the topic is re-researched?
   The sketch says no: a broken assumption is knowledge, and red means
   incoherent.
3. Is the operator's note enough, or should `record` take a `--evidence` path or
   URL? A URL invites treating it as a fetched source, which it is not.

## Phase 5 — Wider research

**Problem.** Research runs on `claude-code` only. A user with API credit and no
subscription gets `API_RESEARCH` and a plan stamped *Not researched*. And the
offline baseline writes the same six topics for every idea
(`plan/baseline.py::TOPICS`), which is what the README's first run shows.

**Design sketch.**

*API backend.* `ClaudeLLM.research` exists as a refusal. Building it means the
API's server-side web search and web fetch tools on one call per topic, and the
ledger reading that response instead of a CLI transcript. The honest part:

- **The ledger is the hard half.** `ledger.fetches` reads `claude --print`'s
  `stream-json`. The API returns tool-result blocks of a different shape, and
  whether a failed or empty fetch is distinguishable there is not known. It was
  not obvious on the CLI either (plan-prototypes, Phase 1: "a failed fetch does
  not look failed"). **Measure first, as that phase did, before designing.**
- **Cost is real money on this path.** The CLI's reported price for one topic
  was $0.37–$0.53 on a subscription that did not charge it. On the API that is
  billed, plus the search tool's own per-use fee, so a `standard` plan is on the
  order of a few dollars and `deep` more. The checkpoint already prints a call
  estimate (`pipeline.call_estimate`); on this backend it must print a price
  range before the first call, and the measurement has to supply it.
- **This repo's own account has no API balance** (the owner's note, 2026-11).
  The measurement needs credit bought for it, which is why it is an operator
  task and why this phase is last.
- **Isolation is a different mechanism.** `RESEARCH_ISOLATION` is CLI flags
  checked against the stream. On the API the guarantee is the tools list sent,
  which is easier to hold and needs its own test.

*Offline baseline.* It cannot research and must not pretend to. What it can do
without a model is stop being identical: pick its topics from a few fixed sets
by cheap signals in the idea (a place, a product, an event, a piece of
software), still deterministic, still stamped *Not researched*, every finding
still an assumption.

Tasks:

- [ ] Measure one topic on the API backend with web search and fetch: time,
      billed cost, whether the schema holds with tools on, and whether each
      fetch and its failure can be read from the response. Record it here as
      plan-prototypes Phase 1 did (~operator: needs API credit)
- [ ] Decide from the measurement: build, or write the refusal's reason down as
      final and delete the "so far" from `API_RESEARCH`
- [ ] If built: `ClaudeLLM.research`, a second reader in `ledger` behind the
      same `Fetch` record, the price line at the checkpoint, and an isolation
      test over the request's tool list
- [ ] Baseline: two or three topic sets and the chooser, each with its own
      golden; the existing six stay the fallback so today's golden does not move
- [ ] `README.md`, *What a plan does not know yet*, says what each backend can
      and cannot show

**Done is checked by:** the measurement table is in this file whatever the
decision; if built, a scripted API response with one failed fetch yields a
finding labelled an assumption, as the CLI path's test does; and
`proto plan --offline` on a software idea and on a place idea give different
topic lists, each byte-stable.

**Open questions for Jeston**

1. Is API research worth buying credit to measure, given nobody but the owner
   runs this yet? If not, cut it here and keep the refusal.
2. A less generic baseline is more code that no real plan uses. Is the offline
   run a demo worth improving, or only the test suite's fixture?

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
- **Writing `skeletor-new`'s command line into the brief.** It would put
  another repo's flag names in this one and break silently when they change.
  The brief states neutral facts; the reader belongs to whoever reads.
- **Having the model judge whether its own findings are true.** A second call
  with the same blind spot. Phase 4 puts the judgement where the evidence is:
  a person who tried it.
- **Counting a recorded outcome as a source.** It was not fetched and no
  transcript vouches for it. It is rendered as the operator's word, apart.
- **Running research on several topics in parallel.** It would cut wall time,
  and plan-prototypes measured two minutes a topic in series. Left out: no
  Phase 1 run has yet said the wait is the problem, and parallel subscription
  calls are an account-limit question nobody has measured.
