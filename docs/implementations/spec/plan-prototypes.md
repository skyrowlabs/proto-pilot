---
title: Plan Prototypes and Dreaming
slug: plan-prototypes
priority: high
category: spec
agent_value: 3
completed: 2026-11-07
updated: 2026-11-07
tags: [plan, research, dreaming, pipeline]
summary: Add `proto plan`, which turns an idea into a researched, connected, organised set of text plans, plus a dreaming step that collects, evaluates and proposes lighter extensions of the idea.
---

# Plan Prototypes and Dreaming

> **Status**: 🟢 Ready — all six decisions ruled and Phase 1 measured, 2026-11-06
> **Priority**: High — this is now the product; see [plans-first](../../ideas/plans-first.md)
> **Updated**: 2026-11-07

## Problem

`proto new` answers one question: *what would this look like running?* Some ideas
cannot be tested that way. "Open a neighbourhood repair café" or "start a community
tool library" has no useful thirty-second spec, because the unknowns are in the
territory around the idea: what the deeper topics are, how they depend on each
other, what could sink it, and where to begin.

Pushed through `proto new` today, such an idea is cut to 1–4 entities by intake's
*bias hard toward less* rule, and comes back as a CRUD app that tracks the idea
instead of exploring it. Nothing in the tool produces thinking as its artifact.

The second gap is that every pass narrows. Clarify, intake and the spec review all
exist to remove options, which is right for building and wrong for exploring. Nothing
ever asks *what else could this become?*, so the extensions that make an idea worth
pursuing are never collected.

## Approach

The tool's main output becomes **a prototype of a plan.** It keeps the promise in
[sketches-not-scaffolds](../../ideas/sketches-not-scaffolds.md): the output is evidence
about an idea, made to learn from. The medium changes from a running app to an
organised set of text.

```bash
proto plan "start a community tool library" --direction "one town, volunteer run"
```

```
community_tool_library/
  PLAN.md              the organised document: idea, topic map, where to start
  topics/<topic>.md    one text plan per deeper topic
  dreams.md            extensions, kept apart from the plan
  sources.md           everything research relied on
  .protopilot/plan.json   the model; every file above is rendered from it
```

**It is a sibling pipeline, not a third target.** A target varies the medium of one
`Spec`, and what fills a `Spec` (entities, fields, screens) is meaningless for a plan,
as are target entries like `SKELETON_DIR`, `ARCHETYPES` and `WRITABLE`. What it reuses is the
machinery below the spec: the `LLM` protocol, the job seam, the bounded repair loop,
the human checkpoint, and the rule that every pass has an offline twin.

### The pipeline

| Pass | Produces | Note |
| --- | --- | --- |
| `scope` | goal, audience, horizon, constraints, up to three questions | the `clarify` analogue |
| `outline` | 4–8 topics, each with a one-line reason it matters | **human checkpoint** |
| `research` | per topic: findings, each cited or labelled an assumption | one call per topic; the only pass needing tools |
| `connect` | typed edges: `depends-on`, `informs`, `conflicts-with` | run after research, so links rest on findings |
| `consider` | per topic: risks, unknowns, decisions someone must make | |
| `start` | an ordered first few steps, each with its reason | see below |
| `dream` | collect, evaluate, propose | see below |
| `verify` | structural checks, bounded repair | see below |
| render | every markdown file | deterministic, no model call |

The review stays at the outline because that is the last cheap place to fix a
misreading, for the same reason the spec review sits before generation. A topic list
can be read in thirty seconds; a finished document cannot.

**Where to start is derived, not just written.** `start` must choose from topics with
no unmet `depends-on`, and should prefer whichever retires the riskiest unknown soonest.
The model writes the reasoning; the graph constrains the choice, and the verifier
checks that it did.

### What "verified" means for text

*Verified by running* is the tool's first pillar, and a document cannot be run. The
replacement checks structure, and it must be honest about its limit: **it proves the
plan is coherent and traceable, never that it is true.** The green line says so.

- every topic is in the map; every edge names two topics that exist
- `depends-on` has no cycles
- every finding has a source in `sources.md`, or is labelled an assumption
- every source was fetched with usable content during this run, not typed by the model
- the first step in `start` has no unmet dependency
- every dream has an anchor topic, a verdict, and fits its word cap
- no dream text appears in a topic file

Red runs the repair loop against the failing check, then hands back what is still
wrong, as a RUNBOOK does for a broken app.

### Dreaming

Planning converges and dreaming diverges, so a dream gets **less detail by design and
wider reach**. Three steps, each a separate call so that nothing judges its own output:

**Collect.** The model writes extensions through a fixed set of lenses, because "give
me ideas" returns the same five each time. Starting lenses: *who else*, *the opposite*,
*ten times bigger*, *the smallest version*, *remove the main constraint*, *borrow from
another field*. The schema enforces the lightness: a dream is a title, a *what if*
sentence, the topic it extends, and what it would take, under a hard word cap. No
research and no phases. A dream that needs a paragraph is a topic.

**Evaluate.** A second call sees the plan and the dreams, and scores each on a short
rubric: **pull** (does it make the idea more worth doing), **reach** (does it open
something the plan cannot), **cost** (what it would take), **fit** (does it fight the
stated constraints). Each dream gets a verdict and a sentence of reasoning, not one
blended number. Near-duplicates merge here.

**Propose.** The top few go into `dreams.md` as proposals, each saying what would
change if adopted. The rest stay listed under *Set aside*, with the reason, because
what was ruled out is the expensive half and because an idea set aside today may fit
when the constraints move.

Three rules keep dreams honest:

- **The medium enforces the label.** Dreams live in `dreams.md` and never in a topic
  file. A reader must not be able to mistake one for a researched finding.
- **The pool accumulates.** `proto dream` runs another round against an existing plan
  and adds to it, so dreaming is something you return to, not a step that ends.
- **Only a person promotes.** `proto dream promote <id>` turns a dream into a topic,
  which then gets researched and connected like any other. Nothing crosses by itself.

## Phase 1 — Measure research before designing around it

Research is the one capability the tool lacks. `structured()` is a single call with no
tools: `ClaudeCodeLLM` passes `ISOLATION`, which is `--tools ""` and an empty MCP
config, deliberately, and `ClaudeLLM` sends no tools.

- [x] Run a throwaway research call on the CLI backend with only `WebSearch` and
      `WebFetch` allowed; record tokens, time and whether `--json-schema` holds
- [x] Establish whether the URLs actually retrieved can be read from the run
- [x] Record the result here and confirm or revise Decision 5
- [ ] (~deferred) Same on the API backend with its server-side web search, once there
      is API credit to run it

**Measured 2026-11-06:** two calls on one topic, one per output format, so a small sample.

| | `json` | `stream-json` |
| --- | --- | --- |
| Time | 133s | 122s |
| Turns | 16 | 15 |
| Reported cost | $0.53 | $0.37 |
| Valid structured output | yes | yes |

- **`--json-schema` holds with tools on**, so research needs no split into two calls.
- **`stream-json` shows every retrieval.** All six cited URLs in that run matched a
  `WebFetch` that returned content, and the assumption was labelled. `json` output
  cannot show this, so research must use `stream-json`.
- **A failed fetch does not look failed.** A 403 and an unfollowed redirect both came
  back with no error flag, as text in the result. The ledger must read that text, and
  it is a heuristic.
- **`WebFetch` returns a model's summary of the page, not the page.** So *retrieved
  this run* proves the source was read through that summary, not that the claim is in
  the original. The verifier's limit should say so.
- **Budget:** about two minutes a topic, so 4–8 topics take 8–17 minutes in series.
  The reported cost is what the run would be priced at, not a subscription charge.

Decision 5 is confirmed.

## Phase 2 — The model, the offline twin, the renderer

- [x] `protopilot/plan/model.py`: `Plan`, `Topic`, `Finding`, `Source`, `Edge`,
      `Step`, `Dream`, pydantic, stored at `.protopilot/plan.json`
- [x] Deterministic baseline: `proto plan --offline` builds a generic topic skeleton
      from the idea, with every finding labelled an assumption and the document
      stamped *not researched*
- [x] Renderer: `Plan` to the file tree, byte-stable for one input
- [x] `proto plan` command behind the job seam, so progress works like `proto new`

## Phase 3 — The passes and the checkpoint

- [x] `scope`, `outline`, `connect`, `consider`, `start` under `protopilot/plan/passes/`,
      each with its offline twin
- [x] Outline review with add, drop and rename, in the CLI and via `--yes`
- [x] `--depth shallow|standard|deep`, setting topic count and research effort, with
      the estimated call count printed at the checkpoint

## Phase 4 — Verifier and repair

- [x] One check per bullet in *What "verified" means*, each with a planted-failure test
- [x] Repair pass bounded as `proto new`'s is, editing `plan.json` only
- [x] Green line states the limit in words

## Phase 5 — Dreaming

Comes before research because it needs no tools and can be judged on offline outlines.

- [x] Lenses as data; `collect`, `evaluate`, `propose` as three passes
- [x] Word cap enforced by the schema, and tested by the verifier
- [x] `proto dream [dir]`, `--lens`, merging into the existing pool
- [x] `proto dream promote <id>` and `proto dream drop <id> --why "…"`
- [x] `--no-dream` on `proto plan`
- [x] Judge one real idea by hand: are the lenses producing different dreams, and does
      the evaluation separate them? (~operator) Decided 2026-11-07, on the tool
      library run (17 dreams): the lenses differ, and the evaluation separates them.

## Phase 6 — Research

- [x] The tool-using call on the `LLM` protocol, as Phase 1 decided; `structured()` and
      `ISOLATION` stay untouched for every other pass
- [x] `research` pass, one call per topic, resumable so one failure does not cost the
      topics already done
- [x] Source ledger feeding `sources.md` and the verifier
- [x] Page text is untrusted input: it reaches later passes only as cited findings, and
      the research call holds no write or shell tools
- [ ] API-backend research, with its server-side web search (~deferred): it refuses in a
      sentence until it can be run

**Built 2026-11-07.** How it works is in
[ARCHITECTURE.md](../../ARCHITECTURE.md#the-plan-pipeline). Choices this phase made:

- **Placement:** after the review and before `connect`, as the pipeline table says.
- **A failed topic is recorded and the run goes on**; a stopped run resumes from
  `.protopilot/research/`, so both kinds of failure keep the topics already done.
- **The CLI does send a status code.** Phase 1 read the text; `tool_use_result.code` is
  there too. The ledger reads both, and the text check stays because the field is not
  a documented contract.
- **The ledger is redrawn from transcripts on every load**, which closes the hand-typed
  `fetched: true` hole. A forged transcript is out of reach and the code says so.
- **A topic is researched only if it cites a page it fetched**; a call that cites nothing
  is recorded `nothing cited`, so `researched` never claims a plan with no source.
- **URL matching errs toward an assumption:** http and https, `www.` and `:443` count as
  different pages, so a citation spelt unlike its fetch is labelled an assumption.

**Run once, 2026-11-07,** on the README's bakery idea at `--depth shallow`, `claude-code`:
764s end to end, research 352s for 4 topics (64–105s each). Green, every check held.
14 fetches, 11 judged usable (one tool error, one 404, one PDF whose summary said it read
nothing); 12 findings cited 10 sources, every cited URL matched a usable fetch, and 4
findings were labelled assumptions. A re-render from disk stayed green.

## Phase 7 — The surfaces that assume an app

These are the sentences that turn out to be *true only of apps*, which the second
target showed cost more than the seam looks.

- [x] `registry.Entry` gains a `kind`; `proto ls` shows it; `port` means nothing for a plan
- [x] `registry.delete` refuses any tree without `spec.json`, so `proto rm` would refuse
      a plan, and it runs `docker compose down -v` first. It needs both changed
- [x] `proto up`, `down`, `test`, `add`, `reset`, `logs` refuse a plan tree with a sentence
      that says what to do instead
- [x] `proto console`: decide whether a plan appears, and read-only is enough at first
- [x] Update `README.md` (*a prototype you can run* is no longer the whole claim),
      `docs/CLI.md` and `docs/ARCHITECTURE.md`
- [ ] (~deferred) `proto new --from-plan <dir> --topic <topic>`, building a running
      prototype of one topic
- [ ] Hand the plan to the Improvement Loop for repeat research rounds (~deferred)

**Built 2026-11-07.** Choices this phase made:

- **`proto plan` registers its tree** as kind `plan`, with no port, once `plan.json`
  lands, green or red, so `ls`, `rm` and `prune` reach it. A re-render registers a plan
  made earlier, and a listed one keeps its date. An entry with no `kind` is an app.
- **What a tree is comes from its files**, never the index: `spec.json` is an app,
  `plan.json` a plan, anything else is refused by `rm`, research in progress included.
- **Slugs are unique across the registry**: a slug another path holds gets `_2`, `_3`, so
  an app and a plan from one idea are both reachable on the web, which finds by slug.
- **The web asks the tree, not the entry**, as the CLI does, so a stale entry reaches no
  Docker call and no delete.
- **`spec` and `export` refuse a plan too**, with the same sentence, since both read a `Spec`.
- **`proto console` lists no saved trees**, app or plan, and its actions reach only the run
  it just made, so a plan does not appear there. `proto serve`, which does list them,
  shows a plan read-only.

## Open decisions

All six were decided on 2026-11-06.

1. **One document or a tree?** Ruled: a folder, with `PLAN.md` as the entry, so topics
   can grow alone. `proto plan export --single` flattens it for sharing.
2. **Sibling pipeline or third target?** Ruled: sibling, for the reasons under *Approach*.
3. **Dreaming on by default?** Ruled: yes, at a small count. `--no-dream` turns it off.
4. **Can a person edit the rendered markdown?** Ruled: no. `plan.json` is the truth and
   a re-render overwrites.
5. **Which research path?** Ruled, and confirmed by Phase 1: the CLI backend with only
   `WebSearch` and `WebFetch`, for the research pass alone, using `stream-json`. API-backend
   research can follow the first version.
6. **What is the command called?** Ruled: `proto plan` and `proto dream`. "Plan" already means
   a `docs/TODO/` file in this repo, but only to people working on the repo.

## Acceptance

- [x] `./pp test unit` green, with no network and no key: 2445 passed 2026-11-07 as uid 1000 in a user and net namespace with only `lo` up, key unset, and an outside address unreachable
- [x] `proto plan "…" --offline --yes` writes the whole tree, twice, byte-identical
- [x] Each verifier check goes red on its planted failure, from a green baseline
      (`test_plan_verify.py`: `test_every_check_has_a_planted_failure`,
      `test_a_planted_failure_turns_its_check_red`)
- [x] A plan's `dreams.md` holds proposals and set-aside entries, each with a verdict,
      and no dream text appears under `topics/` (`dreams_apart`;
      `test_a_proposal_says_what_would_change_and_the_rest_sit_under_set_aside`)
- [x] `proto dream` run twice grows one pool, without duplicates
- [x] `proto dream promote <id>` produces a verified topic, and no other path does
      (`test_promote_offline_adds_a_verified_topic_tied_to_its_anchor`,
      `test_only_a_promoted_dream_may_name_a_topic`)
- [x] `proto up` on a plan tree refuses and exits non-zero; `proto rm` removes it and
      never calls Docker
- [x] `proto new` output is unchanged: the golden manifests do not move
- [x] (~operator) One real idea run end to end with research, read by a person, who can
      name a topic they would not have thought of and a first step they would act on.
      Decided 2026-11-07, on the bakery run (shallow research, 10 of 10 cited
      sources fetched): yes, a new topic and a first step.

## Dropped, and why

- **A third target.** See *Approach*: it would need a `Spec` with nothing in it, and
  stubs for the contract entries that assume generated code.
- **One big prompt writing the document.** Nothing to verify, no checkpoint, no
  resuming, and connections asserted rather than recorded as data.
- **Dreams inline beside the topics they extend.** The most readable layout, and the
  one where a guess reads as a finding.
- **A single score per dream.** It hides why a dream ranked where it did, and a costly
  far-reaching idea ties a cheap dull one.
- **Rendering with the model.** It would make output unstable, untestable offline, and
  able to drift from the data the verifier checked.
- **Claiming the verifier checks truth.** No deterministic check can, and a green line
  implying otherwise is worse than no line.
