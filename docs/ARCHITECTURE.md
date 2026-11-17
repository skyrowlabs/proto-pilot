# Architecture

The map. **This file says what the pieces are and how they connect**; it
deliberately does not restate two things that live elsewhere:

- **What the tool is for, and how to use it** — [`README.md`](../README.md). Why
  the design is this way is argued here, in [The plan pipeline](#the-plan-pipeline).
- **The rules for changing it** — [`AGENTS.md`](../AGENTS.md), which carries the
  invariants and what softening one costs.

Linked, never duplicated. A component table that also argues for itself goes
stale in the half nobody re-reads.

## What This Is

**Planning is the whole product.** `proto plan "an idea"` turns a sentence and a
little direction into a folder of text plans: topics, how they connect, risks,
first steps, and dreams kept apart from the plan. `proto dream` adds to the pool
of dreams and settles one. Its pipeline is [below](#the-plan-pipeline).

The CLI is `plan`, `dream`, `ls`, `rm`, `prune` and `doctor`. Nothing here
generates, runs or verifies an app, nothing listens on a port, and nothing calls
Docker. The layer that did was removed on 2026-11-11; the tag `prototyping-final`
is the last commit that holds it, and [plans-first](ideas/plans-first.md) has the
argument.

Two command-line tools live in this repo and are **not** the same thing:
`proto` is the product (installed on PATH, `protopilot/`), `./pp` is this
repository's own tooling (`cli/`, `scripts/`). See AGENTS.md Rule 15.

## Data Flow

One `proto plan` run, end to end. Every arrow is a place something can be refused.

```
  idea (one sentence) + direction + brief (goal, for, horizon, must, not: each optional)
    │
    ▼
  scope ──────────────────  goal, constraints, up to three questions for you;
    │                       a field the brief states is put back over the model's
    │
    ▼
  outline ────────────────  the topics, each with a reason it matters
    │
    ▼
  ┌───────────────┐
  │ HUMAN REVIEW  │◀────── the last cheap place to fix a misreading: add,
  └───────────────┘        drop or rename topics before the rest is written
    │
    ▼
  research ───────────────  one web-only call per topic, claude-code only;
    │                       each transcript saved, so a stopped run resumes
    ▼
  connect ▶ consider ▶ start   typed links, then risks, unknowns and
    │                          decisions, then the first steps
    ▼
  collect ▶ evaluate ▶ propose   dreams; a failure here never costs the plan
    │
    ▼
  verify ─────────────────  seven structural checks, all of them, every time
    │
    ├── green ──▶ render ──▶ registry.record ──▶ the green line
    │
    └── red ────▶ repair (links and steps only) ──▶ verify again (×3)
                    │
                    └── still red ──▶ RUNBOOK.md, tree handed back anyway
```

## Components

| Component | Responsibility | Talks to |
| --------- | -------------- | -------- |
| `protopilot/cli.py` | The `proto` command: `plan`, `dream`, `ls`, `rm`, `prune`, `doctor` | everything below |
| `protopilot/plan/model.py` | **The truth.** `plan.json`, the slug rule and where a plan keeps its files | `pydantic` |
| `protopilot/plan/passes/` | One module per pass: prompt, JSON Schema, `apply`, and an offline twin | `llm.py`, `protopilot/plan/model.py` |
| `protopilot/plan/pipeline.py` | Orchestration: the halves a run stops between, the repair loop, the runbook floor, resume | `plan/passes/`, `jobs.py`, `registry.py` |
| `protopilot/plan/baseline.py` | The deterministic plan every pass's offline twin slices | `protopilot/plan/model.py` |
| `protopilot/plan/render.py` | `plan.json` ▶ every markdown page, with no model and no clock | `protopilot/plan/model.py`, `protopilot/plan/lenses.py` |
| `protopilot/plan/verify.py` | The structural checks, the verdict type and the runbook | `protopilot/plan/render.py`, `protopilot/plan/ledger.py` |
| `protopilot/plan/ledger.py` | What research fetched, read from its transcripts and never from a citation | `llm.py` |
| `protopilot/plan/lenses.py`, `protopilot/plan/dreaming.py` | The six lenses as data, and the rules of the dream pool | `protopilot/plan/model.py` |
| `protopilot/llm.py` | `LLM` Protocol + three backends (api, claude-code, offline) | `anthropic`, the `claude` CLI |
| `protopilot/runner.py` | The subprocess seam the `claude-code` backend runs through, behind a Protocol so it can be faked | `subprocess` |
| `protopilot/jobs.py` | In-process job store: `proto plan` runs on a job and emits typed events | `cli.py`, `protopilot/plan/pipeline.py` |
| `protopilot/progress.py` | A pure fold of a job's events into what a view would draw | — |
| `protopilot/registry.py` | JSON index of plan trees: what exists and where | the filesystem |
| `cli/`, `scripts/` | This repo's own gates and jobs. Never shipped to a user | — |

## The plan pipeline

`proto plan "an idea"` writes a folder of text:
`PLAN.md`, `topics/`, `dreams.md`, `sources.md` and a stored `plan.json`, with a
`RUNBOOK.md` when the plan ends red. Why is [plans-first](ideas/plans-first.md); the design and what is still to build are
[plan-prototypes](implementations/spec/plan-prototypes.md); flags are in [CLI.md](CLI.md#proto-plan), and
`proto dream`'s [beside them](CLI.md#proto-dream).

**It is the only pipeline here.** It runs on the job seam and its event
vocabulary, keeps its own files in `.protopilot/` (`PLAN_DIR`), owns the slug rule
(`SLUG_RE`, both in `model.py`), and holds the rule that a pass has an offline twin.
Model output reaches `render.write` as text inside a page, never as a path. The
one model value in a file name is a topic slug, which `model.py` checks, and
`render.py` escapes any HTML opener in plan text.

- **`plan.json` is the truth.** `model.py` defines it; every markdown file is
  drawn from it, and a re-render overwrites them, so an edit belongs in `plan.json`.
- **Rendering is deterministic.** `render.py` uses no model and no clock, so one
  plan is one set of bytes; `tests/test_plan_render.py` holds that.
- **A run is `scope`, `outline`, the review, `research`, `connect`, `consider`, `start`,
  `collect`, `evaluate`, `propose`, verification, any repair, then render.** That is eight
  model calls plus one research call per topic, five with `--no-dream`, none for research
  with `--no-research`, and up to three repair calls, one module each in `protopilot/plan/passes/`. `pipeline.py` runs them on one job, in halves, so `proto plan` can stop for
  scope's questions and the outline review. `--yes` skips both, and off a terminal
  it is required, `--offline` included, because a prompt there cannot be answered.
- **Research is one tool-using call per topic, on the `claude-code` backend only.**
  `ClaudeCodeLLM.research` holds `WebSearch` and `WebFetch` and nothing else, streams
  `stream-json`, runs in an empty directory, and throws its answer away unless every
  init event lists its tools and MCP servers, holds none but those and
  `StructuredOutput`, and no tool use names another (`llm.research_result`).
  `structured()` and `ISOLATION` are untouched. The api backend refuses research in a
  sentence, and `proto plan` refuses it before any call unless `--no-research`; its web
  search has never been run here. The offline twin reads nothing, so an offline plan
  stays stamped. `--depth` sets how many findings a topic returns and pages it may read
  (`research.EFFORT`).
- **A source is fetched only if this run's transcript says so.** `ledger.py` reads each
  `WebFetch` and its result out of the stream, never from the model's citations, and
  calls a fetch usable by a **heuristic**: a 2xx status where the CLI sends one, some
  bytes, and text that does not read as an HTTP failure, an unfollowed redirect, a bot
  wall, or a summary saying it read nothing. A topic returning more findings than its
  depth allows fails, live or replayed. Every string from a page is drawn through
  `render.md_text`, as one line with no markdown syntax left in it, and an unfetched or
  failed URL is drawn as inline code, never a link. A failed fetch carries no error
  flag. `research.apply` makes a finding cited only through a usable fetch of a whole
  http(s) URL (`WEB_URL`); any other citation becomes an assumption, its URL kept as
  `unfetched` for `sources.md`. `ledger.normal` matches URLs without a fragment or
  trailing slash, and keeps http/https, `www.` and `:443` apart, which errs toward an
  assumption. `WebFetch` returns a model's summary of a page, so a citation shows that
  summary was read, never that the claim is in the source, and the green line says so.
- **The ledger is redrawn from transcripts, so a hand edit cannot upgrade it.** Each
  topic's raw stream lands in `.protopilot/research/<slug>.jsonl`, and its sha256 in
  `plan.json`. `sources_fetched` reads the ledger and never `Source.fetched`, and
  `rerender`, `_hand_back` and `_held` redraw the ledger from the transcripts first, so
  `fetched: true`, or a fetch typed into the ledger, stays red. Each record's state is
  redrawn too (`ledger.reconciled`), from its own transcript, which must carry the topic's
  own name and the recorded sha256, and a cited finding must rest on its own topic's
  fetches. A record whose transcript fails that is `failed` with `NO_EVIDENCE`. A forged
  transcript is past any check here.
- **Page text never reaches a later pass.** What does is the findings, bounded in count
  and length by the research schema, as JSON under a note that they are untrusted data
  (`findings_block`). Topic pages say per topic whether research ran, failed, cited
  nothing, or never ran because a person promoted the topic from a dream.
- **A failed topic costs only itself, and a stopped run resumes.** A topic whose call or
  output fails is recorded `failed` and the run goes on. Before the first call the
  reviewed outline is saved as `outline.json` beside the transcripts, and each topic's
  transcript as it lands, so a run that stops, or fails at a later pass, resumes on
  rerun: `resumable` finds the outline, and a topic with a transcript is replayed, not
  asked again. `pipeline.resume_refusal` refuses a resume without research, at another
  depth, offline, or on a backend that cannot research, and the CLI asks it before
  building a backend. The outline is removed once `plan.json` lands; the transcripts stay.
- **A pass's `apply` reads only the fields it names**, so none but `research` can set
  `researched`, `sources` or a finding. `apply` refuses what a plan cannot hold, such as an edge or a step naming a missing
  topic. Order is the verifier's: a step ahead of its dependency lands in the plan and
  goes red at `start_order`.
- **Dreams are guesses, kept apart from the plan.** A `Dream` lives in `plan.json` and
  draws to `dreams.md`, never to a topic page, and nothing in one is researched.
  `lenses.py` is the six lenses as data, and `dreaming.py` is the pool's rules. `collect`
  writes dreams with no verdict and numbers them itself; `evaluate`, a separate call so
  nothing judges its own output, rates the fresh ones on `RUBRIC` and may only give
  `proposed` or `set-aside`; `propose` chooses at most three of those and sets the rest
  aside. `dropped` and `promoted` are a person's verdicts, and `evaluate` refuses them
  from a model. A pass with nothing to read makes no call.
- **The pool's cap is 44 words, and one bad dream costs only itself.** `DREAM_FIELD_WORDS`
  gives the title 6, the what-if 26 and the takes 12, and `dream_words` counts them,
  whatever joins the words. `admit` leaves out a dream that is over, blank, off its lens
  or anchor, or a repeat; `settle` leaves out one with no verdict or one that copies a
  topic. Each leaves a line, and a round cannot turn a good plan red. The `claude-code`
  backend enforces the schema's word patterns, and the API backend cannot take them, so
  `_without_patterns` turns them into descriptions and `admit` is what holds. That
  backend has never been run for these passes.
- **Dreaming cannot cost a plan.** `_guarded` turns a backend failure or bad output into
  `DreamFailed`, and any other exception stays a bug. In `proto plan`,
  `_dreamed_or_noted` keeps the plan as it stood, records `dream_failure` for `dreams.md`,
  and carries on, so the exit code is the plan's own. In `dream_round` the same failure
  is a refusal: the tree stays as it was and the CLI exits 1.
- **`dream_round`, `promote` and `drop` extend a green plan or do nothing.** `_held` refuses
  a red plan before any model call, and `_land` writes only a green result, and only if
  `plan.json` has not moved meanwhile. A page edited by hand is drawn over, with a line
  naming it. If the draw itself fails, `_put_back` restores the tree and says how far
  that got. A round whose dreams all fall out still lands, with nothing added.
- **Only `proto dream promote` turns a dream into a topic.** `dreaming.promoted` is called
  from `pipeline.promote` and nowhere else. The topic goes last, one call in
  `protopilot/plan/passes/promote.py` supplies its links and notes, and a link that does
  not touch it is refused, so what the plan had settled stays settled. It writes no
  finding, so the topic stays not researched. A promotion that stays red changes nothing.
- **Verification proves structure, never truth.** `verify.py` has one check per bullet
  of [What "verified" means](implementations/spec/plan-prototypes.md#what-verified-means-for-text):
  `topic_map`, `no_cycles`, `findings_traced`, `sources_fetched`, `start_order`,
  `dreams_shaped` and `dreams_apart`. `dreams_apart` reads what a topic says, not what
  every topic page draws, and catches a copy with a word or two changed; **a paraphrase
  passes**. Each is a pure function of a plan and its pages,
  so one check judges the pages drawn in memory and the pages read back from disk, and
  all of them always run. A check ends passed, failed or no subject, and no subject
  proved nothing. `green_line` builds its sentence from what held: *coherent and
  traceable* needs `findings_traced` and `sources_fetched` both to hold, which only a
  researched plan earns; otherwise green says the structure holds and that nothing
  traces to a source.
- **Repair reaches links and steps, and nothing else.** On red, `repaired` runs
  `protopilot/plan/passes/repair.py` up to three times, against pages drawn in memory,
  so repair only ever edits data. Its `apply` is `connect`'s then `start`'s, and `FIXES`
  names the two checks whose subject that is, `no_cycles` and `start_order`; any other
  failure goes to the floor with no call made. A dream fault never reaches it from a
  run, because `dreaming` removes the dream instead. `rejected` is the plan's shrink guard,
  judged against the plan repair started from: it throws away a repair that removes an
  edge on no loop, every link of a loop, or a healthy step, unless the step cap forced
  that out for a step a kept one waits on. `worsened` throws away one that leaves more
  wrong than it found. A thrown-away attempt counts, and its reason goes into the next.
  A repair pass that fails or changes nothing stops the loop, and offline, where the
  twin returns the plan as it stands, that is the first attempt. After a promotion
  `unsettled` adds one rule: every link and step the plan held before stays as it was.
- **The floor hands back a whole tree.** A plan still red is written anyway, with a
  `RUNBOOK.md` from `verify.runbook`, a *Not verified* banner on `PLAN.md` and every
  topic page, and no green line; `finished` says `ok=False` and the CLI exits 1.
  `_hand_back` then judges what landed, so a plan green in
  memory and red on disk takes the floor too. A failed plan pass is a different thing:
  a pass that returns nothing a plan can hold leaves no tree at all.
- **The baseline is the offline twin.** `baseline.py` builds a generic plan from the
  idea's words, and each pass's `offline` slices it. It always has the same six
  topics, so `--depth`, which asks for 4, 6 or 8, is refused on an offline backend.
- **Nothing but research reaches disk until render.** `plan.json` saves atomically, then the pages
  follow. In a fresh tree `PLAN.md` goes last, so holding it means holding every page;
  over an old one a red plan draws it first, so a write that dies midway leaves it
  marked. A failed plan pass leaves no tree unless research had begun, and a rerun
  starts from scope, losing any review edits; with research begun it resumes. A render that fails after that save keeps `plan.json`, so a rerun
  redraws it. **That order covers `PLAN.md` alone:** a write dying mid-render can leave
  old topic pages, unmarked, which is why `after_failure` says any page may be out of
  date and points at the rerun.
- **A rerun of a finished plan is a re-render, and it verifies.** No pass runs, and it
  needs neither `--yes` nor a terminal. Another idea, direction, brief or `--depth` is refused.
  `plan.json` may be hand-edited, so `rerender` judges it as it stands, and red takes
  the floor and exits 1. With no model there is no repair, so a red tree's rerun never
  retries one: a fresh attempt means removing the tree. Its runbook keeps what the
  last run tried, and adds that the re-render repaired nothing.
- **`render.write` never writes through what it did not make.** `_blockers` names a
  link, dangling or not, at a page path or at `topics/`, a directory at a page path, a
  read-only file, and a `RUNBOOK.md` that does not open with `RUNBOOK_MARK`, which is a person's. A
  green plan that is blocked draws nothing. A red one draws every page it can reach,
  so no old page goes on reading as verified, then refuses. Both refuse by name with
  exit 1, nothing is written outside the tree, and a link is neither followed nor
  removed. A green run removes a runbook only if it carries the mark, so a person's
  stays.
- **A plan tree is registered, and only a plan is ours.** `build` records it as kind
  `plan` once `plan.json` lands, green or red; a re-render records a plan made
  before plans were listed, and keeps an entry's date. What a verb does to a tree
  comes from the tree's own files (`registry.tree_kind`), never from the index:
  `plan.json` is a plan and anything else is not ours, so a tree with only research
  in progress is not, and neither is a tree holding a prototype an older version
  generated, even beside a plan. The index's kind never decides what happens to a
  folder; it decides how a row is listed and whether `proto prune` forgets it. A
  row is here (`-`) only when it is of kind `plan` and its path holds a plan.
  `proto ls` prints that state and the kind in columns, reads an `app` entry, or one
  with no kind, as `old`, and reads any other entry that is not a plan on disk as
  `gone`; it ends on a count of plans, and a line for each of the other two when there are any. `proto rm`
  deletes a plan and refuses everything else, and `proto prune` forgets `old` and
  `gone` entries and never touches a folder. A slug another path holds is recorded
  with `_2`, `_3`, so a slug names one entry.

## Critical Patterns

Patterns a change can violate **silently** — the code still runs, and the
failure surfaces somewhere else, later, as something else.

### The offline twin is half of every pass

Change a pass's prompt or schema without changing its `offline` and
`protopilot/plan/baseline.py`, and CI stays green while exercising the old
shape, because the twin is what CI runs. The suite reports on a pipeline nobody
is using. Both halves, same commit.

### Two isolations, and a pass holds exactly one

A pass that returns structured output runs under `llm.ISOLATION`: no tool, no
file, no shell. The research call runs under `RESEARCH_ISOLATION`: web search
and fetch and nothing else. Widening either works perfectly in the happy case,
which is why the violation is invisible. AGENTS.md carries the rule.

### A step's word cap binds only the first time steps are written

`start.schema` holds `action` and `why` to `model.STEP_FIELD_WORDS` with a
`pattern`, which the claude-code backend enforces, but only while the plan has
no steps. Repair and promote reuse that schema and must return every healthy
step word for word, and a step written before the cap can be longer than it.
Under the pattern they could not do both: the backend would refuse the verbatim
step, or a rewritten one would trip the shrink guard and the repair would be
thrown away. Either way an older plan could never be repaired, and nothing would
say why. There the cap is asked for in the prompt and no more. A step's length
is readability, never structure, so `apply` lands an over-long step from a
backend that ignores the pattern.

### The registry is shared, so it is written whole and under a lock

`projects.json` is written by every `proto plan`, `rm` and `prune`. Each
load-modify-save holds an exclusive `flock` on `projects.json.lock` beside it, so
two writers never lose each other's entry, and `save` writes a temporary file and
renames it over, so a reader never sees half of one. `registry.delete` trusts no
caller: it refuses a tree that is not a plan, `/`, and any path that is or holds
your home or the registry file.

### A registry row this version cannot read is kept, never dropped

`registry.load` keeps a row of a kind it does not know and ignores a key it does
not know, and `save` writes back what `load` returned. A loader that skipped
such a row would erase it on the next save, with nothing going red: the list
would just be shorter. Only `proto prune`, run by a person, forgets a row.
`Entry.port` is the same rule for one field: nothing here sets or reads it, and an
older row's port is written back as it was read.

## Decisions and Their Reasons

- **Why planning, and why only planning** — [plans-first](ideas/plans-first.md).
  The design the pipeline was built from is
  [plan-prototypes](implementations/spec/plan-prototypes.md).
- **What is unfinished, and what bit us** — [`NOTES.md`](NOTES.md), the live
  parking lot, including traps that are fixed but worth knowing.
- **Planned work** — [`TODO/README.md`](TODO/README.md). A new plan goes
  there before any code does.
- **Completed plans** — [`implementations/README.md`](implementations/README.md).
  Three of the specs filed there describe the removed layer and are kept as
  history.
