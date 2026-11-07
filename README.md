<p align="center">
  <img src="docs/assets/hero.svg" alt="proto.pilot, by SKYROW.LABS: a paper plane leaves a spark of an idea and dives into an open box. Give it an idea and a little direction, and get back a plan: the topics that matter, how they connect, and where to start." width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/repo-private-7a8fa8?labelColor=1c2633" alt="repo: private">
  <img src="https://img.shields.io/badge/stage-poc-818cf8?labelColor=1c2633" alt="stage: poc">
  <img alt="Python 3.11 to 3.14" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-818cf8?labelColor=1c2633">
  <a href="#works-offline"><img alt="works offline" src="https://img.shields.io/badge/works-offline-818cf8?labelColor=1c2633"></a>
</p>

<p align="center">
  <a href="#install"><b>Install</b></a> ·
  <a href="#commands"><b>Commands</b></a> ·
  <a href="#how-a-plan-is-made"><b>How a plan is made</b></a> ·
  <a href="#prototypes-come-later"><b>Prototypes</b></a> ·
  <a href="#status"><b>Status</b></a> ·
  <a href="#working-on-this-repo"><b>Working on this repo</b></a>
</p>

<p align="center">
  <img src="docs/assets/pillars.svg" alt="Three things proto.pilot is. You steer it: you review the outline before the rest of the plan is written. Honest about its limits: every plan says what was not checked, and a model cannot claim otherwise. Works offline: every pass has a deterministic twin, so CI runs the whole pipeline with no key." width="100%">
</p>

A framework for planning ideas with agents.

Some ideas cannot be judged by building a quick version, because the unknowns are in
the territory around them: what the deeper topics are, how they depend on each other,
what could sink it, and where to begin. Give proto.pilot an idea and a little direction,
and it works that out into an organised set of text plans.

```bash
proto plan "open a small bakery that only sells sourdough" --direction "one person, rented kitchen" --depth shallow
```

```
  pass scope...
  pass outline...
Open a small bakery that only sells sourdough
  constraint: Rented kitchen rather than owned or purpose-built premises, so access is time-bound and the space is likely shared
  constraint: Sourdough only — no other product category to spread risk across or to fill slack time in the day
  open question: Is this meant to replace the person's income, or run alongside other work?
  depth: shallow (4 topics)
  topics:
    1. The fermentation clock vs. time-bound kitchen access
    2. What one person can actually bake in a session
    3. Getting bread to buyers, and the obligations each route drags in
    4. Price, break-even and the conditions for not going ahead
Estimated model calls: 12 in all, 10 still to come (research, connect, consider, start, collect, evaluate, propose), plus 0 to 3 repair calls, only if verification finds something repair can fix. Research is 4 of those calls, one per topic: about 2 minutes and $0.40 reported cost each as measured once, so about 8 minutes and $1.60 here. The reported cost is what the run would be priced at, not a subscription charge.

  pass research...
    fermentation_clock_against_rented_hours: 4 cited finding(s), 3 of 4 fetch(es) usable (105s)
    single_pair_of_hands_output_ceiling: 4 cited finding(s), 3 of 3 fetch(es) usable (64s)
    route_to_buyer_and_what_it_obliges: 2 cited finding(s), 3 of 3 fetch(es) usable (89s)
    price_breakeven_and_walkaway_points: 2 cited finding(s), 2 of 4 fetch(es) usable (94s)
  pass connect...
  pass consider...
  pass start...
  pass collect...
  pass evaluate...
  pass propose...
  verify (attempt 1)...
  pass render...
Researched 4 of 4 topics, citing 10 source(s) fetched this run.
Green: this plan is coherent and traceable, which is not the same as true. [...] Every source was fetched this run and read through a summary of the page, which is not the page: a citation shows that summary was read, never that the claim is in the source.
```

That is a real run with `--backend claude-code --yes`, shortened; it took 13 minutes. You get a folder:

```
PLAN.md              the idea, the topic map, how topics connect, where to start
topics/<topic>.md    one text plan per topic: findings, risks, unknowns, decisions
dreams.md            guesses at what else the idea could be, kept apart from the plan
sources.md           every page research cited, each one fetched during the run
```

The links between topics are data, not prose, and they decide where the plan starts.
In that run the bakery's first step was asking each shared kitchen, in writing, whether
dough may sit unattended between bookings, because every other topic depends on it and
it is the one answer that could end the idea in a week.

A finding is cited only if the run fetched that page, which is read through a model's
summary of it, so a citation shows what was read, not that it is true. Anything else is
labelled an assumption. `--no-research` makes a plan in a minute or two, stamped
*Not researched*.

A plan is not a finished answer. It is the cheapest way to see the shape of an idea
before spending anything on it, and it is what a prototype should be built from later.

## Install

```bash
git clone https://github.com/skyrowlabs/proto-pilot && cd proto-pilot
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
proto doctor          # what each target needs, the SDK, credentials, a port
```


The virtualenv is not optional advice — on a distro whose Python is externally
managed (Arch, and Debian since 3.11) a bare `pip install -e .` refuses to run.

Needs Python 3.11 or newer and Claude credentials: either `ANTHROPIC_API_KEY`, or a
Claude subscription through the Claude Code CLI. The API is the default, and the tool
never falls back from one to the other by itself, because they bill differently. To use
a subscription, pass `--backend claude-code` or set `PROTOPILOT_LLM=claude-code`.

Planning needs nothing else. Docker is only for `proto new --target web`.

## Commands

| | |
|---|---|
| `proto plan IDEA` | scope it, outline it with you, connect the topics, weigh the risks, pick first steps, dream a little, check the structure, write the folder |
| `proto dream [DIR]` / `dream promote ID` / `dream drop ID --why WHY` | run another round of dreams; turn one into a topic; rule one out, with the reason kept |
| `proto doctor` | why it will not work here |

Useful flags on `plan`: `--direction` (scope, emphasis, constraints), `--depth`
(`shallow`, `standard` or `deep`: 4, 6 or 8 topics, and how many findings and pages
research gives each), `--dir`, `--backend`, `--offline` (no API calls, see below),
`--yes` (skip the questions and the review), `--no-research` (a plan in a minute or two,
stamped *Not researched*), `--no-dream` (skip dreaming; `proto dream` can start the pool
later). [`docs/CLI.md`](docs/CLI.md#proto-plan) has every flag.

Off a terminal, `--yes` is required, so a script is refused rather than left waiting.
Run on a folder that already holds a plan for the same idea and direction, it redraws
the pages and checks the plan again with no model call, and exits 1 if the plan is red.

**Rendered pages are not for editing.** The plan is stored as data in the folder, every
page is drawn from it, and a re-render overwrites them.

The prototype commands are under [Prototypes come later](#prototypes-come-later).

## How a plan is made

| Pass | Produces | |
|---|---|---|
| `scope` | goal, constraints, up to three questions for you | built |
| `outline` | the topics, each with a reason it matters | built, and **you review it** |
| `research` | findings per topic, each cited or labelled an assumption | built, on `claude-code` only |
| `connect` | typed links: `depends-on`, `informs`, `conflicts-with` | built |
| `consider` | per topic: risks, unknowns, decisions someone must make | built |
| `start` | the first few steps, each with its reason | built |
| `collect`, `evaluate`, `propose` | dreams: extensions of the idea, gathered, judged in a separate call, the top few kept | built |
| `verify` | structural checks, with a bounded repair | built |
| render | every page | built, no model call |

**The review sits at the outline** because that is the last cheap place to fix a
misreading. A topic list can be read in thirty seconds and a finished document cannot.
Add, drop or rename topics there before the rest is written.

**Where to start is checked, not just written.** The first step must have no unmet
dependency, each later step must follow what it depends on, and `depends-on` links may
not form a loop. Output naming a topic that does not exist is refused outright.

**Verified means the structure holds, never that the plan is true.** The checks prove
the topics, links and steps agree with each other, and the green line says only what
held. A check with nothing to read reports that, and never counts as passed.

**Red gets a bounded repair, then a floor.** Repair has three attempts and can only
change links and steps. It cannot reword a healthy step, drop a real dependency or make
things worse. If the plan is still red you get the whole folder anyway, with a
`RUNBOOK.md` saying what is wrong, "Not verified" banners on the pages, and exit 1.

**Model output is data, not authority.** A pass can only fill the fields it owns. It
cannot mark a plan researched, add a source, promote a dream or remove the stamp, and the
only model text that reaches a file name is a checked slug.

**A plan pass that fails before research leaves no folder.** A rerun starts over from
`scope`, and review edits are lost. Once research has begun, the reviewed outline and each
topic's transcript are kept in `.protopilot/research/`, and rerunning the same command
resumes without asking a finished topic again. A dream pass is the other exception, below.

### Dreaming

Every other pass narrows, so this one widens. Six fixed lenses each ask what else the
idea could be: who else, the opposite, ten times bigger, the smallest version, remove the
main constraint, borrow from another field. A second call scores each dream, and a third
keeps at most three, saying what would change if one were adopted. A plan dreams once
through each lens. `proto dream` goes wider, and adds to the pool without rewriting it.

**Dreams are guesses, not findings.** A dream is unresearched, at most 44 words across its
title, what-if and what it would take, and lives in `dreams.md`, never in a topic file.
From a real run on a community tool library, shortened:

```
### Six tools and a wall tally (d13)

What if the first year were six tools and a chalked tally of everything townspeople asked for that the library did not have

- Lens: the smallest version
- Would take: One volunteer willing to say no and write it down
- Scores: pull high, reach medium, cost low, fit high
```

**Only a person promotes.** `proto dream promote d13` makes that a topic, connected and
checked, and still Not researched: a person chose it, nothing checked it. If the result
stays red, nothing changes and it exits 1.

**A dream never costs a plan.** If dreaming fails during `proto plan`, the plan is written
anyway, a line says what stopped, and a green plan still exits 0. A failed `proto dream`
round changes nothing and exits 1. A red plan is refused by all three verbs with no model
call, because a dream extends a plan that holds.

Two limits. The check that keeps dreams out of topic files catches copies and misses
paraphrase. And the API backend has never been run for these passes.

### What a plan does not know yet

**Research reads the web through a summary.** Each topic gets one call on the
`claude-code` backend holding web search and web fetch and nothing else. A finding is
cited only if that run fetched the page and got usable content back, which is judged by a
heuristic. But a fetch returns a model's summary of the page, not the page, so a citation
shows the summary was read, never that the claim is in the source. Everything else is an
assumption, and a URL the model cited without a usable fetch is listed in `sources.md` as
text, never as a link.

**Some plans are not researched at all.** `--no-research` and `--offline` stamp the plan
*Not researched*. The API backend's web search has never been run here, so with
`--backend api` the command refuses before any call unless `--no-research` is given. A
topic whose research fails says so on its page, and a promoted dream is never researched.
Treat an unresearched topic as a well-organised set of questions and reasoning, not as
facts: only the prompt stops a model stating a fact inside a risk or a reason.

## Works offline

Every plan pass has two implementations: a prompt and a deterministic twin. `--offline`
runs the second: no API calls and no key, a generic topic skeleton with every finding
labelled an assumption, dreams that are templates and say so, and the same bytes on every
run.

It is what the test suite runs, so the whole pipeline is exercised on every commit. A
pipeline that can only be tested with a network call and a credit card stops being
tested.

## Prototypes come later

proto.pilot started as a tool that turned an idea into a running app. That still works
and gets upkeep, but no new features: a prototype is worth more once an idea is concrete
enough to give agents something to build, and a plan is how it gets there.
[`docs/ideas/plans-first.md`](docs/ideas/plans-first.md) has the reasoning, and a later
step is to build a prototype from one topic of a plan.

```bash
proto new "a shared list of who has borrowed which tool" --direction "make it feel like a ledger"
```

It writes a small spec, shows it to you, generates the app, then boots and drives it
rather than assuming it works. Red gets a bounded repair loop, and if that fails the tree
comes back with a `RUNBOOK.md` saying what is broken. The result is something to look at
and throw away, not a starting point for production. The default is a Textual and SQLite
app in your terminal. `--target web` gives you FastAPI and Postgres in Docker, and needs
Docker with Compose v2.

| | |
|---|---|
| `proto new IDEA` | generate, boot, verify, hand it back |
| `proto add CHANGE` | amend the spec, regenerate, re-verify |
| `proto up` / `down` / `logs` / `test` | run a `--target web` prototype; a terminal one uses `make run` |
| `proto spec` | what this project actually promised |
| `proto archetypes` | what shapes this build can generate, and what each asks |
| `proto targets` | what media it can generate into, and what each can build |
| `proto ls` | every prototype on this machine, and which are running |
| `proto rm` | delete one: containers, data and the tree |
| `proto prune` | forget registry entries whose directory is gone |
| `proto gc` | collect Docker resources a deleted tree left behind |

Three optional extras: `dev` pulls the web target's stack, `browser` adds Playwright (without
it the web target's browser stage is reported as skipped, never as green), and `web` is
the front end behind `proto serve`.

Known gaps: `auth: "password"` is accepted by the spec and built by no pass, and `jobs`
and `external_apis` are recorded and otherwise ignored.

How it all works, including what a target owns and why the model can write so few paths,
is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#how-a-prototype-is-built).

## Testing

```bash
./pp test unit          # or: python -m pytest -q
```

The unit suite needs no key, no network and no Docker daemon. Plans are tested through
their offline twins and a fake model, with hostile model output as a first-class case.
Prototypes are tested by generating a tree and running that tree's own smoke suite, with
Docker and the API faked (`tests/fakes.py`) for the verify and repair loops.

## Model usage

Claude Opus 5, adaptive thinking, `effort: high`, structured output against a JSON Schema
per pass. Override with `PROTOPILOT_MODEL` / `PROTOPILOT_EFFORT`.

## Status

**The direction changed on 2026-11-06:** planning is the product, and prototyping waits
until a plan is concrete enough to feed it.

Early, and honest about it. `proto plan` runs against a real model today and writes a
real plan, researched topic by topic on the `claude-code` backend, with its structure
checked and a pool of dreams beside it.
`NOTES.md` is the live parking lot: open items, what got resolved, and what is worth doing next.

## Working on this repo

Two command-line tools live here and they are deliberately not the same thing.
**`proto` is the product** — installed onto your PATH, run from wherever you
want a plan. **`./pp` is this repository's own tooling** — its gates,
generators and scheduled jobs, run from the repo root and never shipped to a
user. One `--help` serving a person planning an idea and a person maintaining
the tool would serve neither.

The repo shell is generated by **skeletor** — a sibling checkout, not part of
this repository — at the `agentic` tier;
`.skeletor.json` records exactly how, and `bin/skeletor-upgrade` carries
template changes in. That means the docs lifecycle, the rules in `docs/rules/`,
the marker-based test suites and the scheduled-job machinery are not local
inventions — they are one shared shell, debugged once.

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt && .venv/bin/python scripts/install_project.py
.venv/bin/pre-commit install --install-hooks && .venv/bin/python scripts/git/install_merge_drivers.py
./pp check pre-push      # every CI gate this host can run
./pp test unit           # the fast suite
```

`check pre-push` is not quite everything CI blocks on, and the gap is named
rather than implied: the **integration suite** needs the stack up, so it runs on
CI only. `tests/test_pre_push_covers_ci.py` recomputes both sets — the gates in
`ci.yml` and the gates in `pp check pre-push` — and fails when one appears in
neither, so this sentence cannot quietly go stale. It said "everything" until
2026-09-06, when it was measurably false: two gates CI blocks on and this host
runs fine were missing from the bundle, and the word stopped anyone looking.

[`AGENTS.md`](AGENTS.md) is the rules — read it before changing anything.
[`docs/README.md`](docs/README.md) indexes the rest;
[`.github/DOCS_INDEX.md`](.github/DOCS_INDEX.md) is the routing table an agent
reads so it loads two documents instead of all of them.

## Licence

[MIT](LICENSE) © SKYROW LABS LLC
