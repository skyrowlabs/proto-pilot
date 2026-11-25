<p align="center">
  <img src="docs/assets/hero.svg" alt="proto.pilot, by SKYROW.LABS: a paper plane leaves a spark of an idea and dives into an open box. Give it an idea and a little direction, and get back a plan: the topics that matter, how they connect, and where to start." width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/repo-public-818cf8?labelColor=1c2633" alt="repo: public">
  <img src="https://img.shields.io/badge/stage-poc-818cf8?labelColor=1c2633" alt="stage: poc">
  <img alt="Python 3.11 to 3.14" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-818cf8?labelColor=1c2633">
  <img alt="works offline" src="https://img.shields.io/badge/works-offline-818cf8?labelColor=1c2633">
  <img alt="skeletor version" src="docs/assets/skeletor-version.svg">
</p>

<p align="center">
  <a href="#get-started"><b>Get started</b></a> ·
  <a href="#an-example"><b>An example</b></a> ·
  <a href="#going-further"><b>Going further</b></a>
</p>

<p align="center">
  <img src="docs/assets/pillars.svg" alt="Three things proto.pilot is. You steer it: you review the outline before the rest of the plan is written. Honest about its limits: every plan says what was not checked, and a model cannot claim otherwise. Works offline: every pass has a deterministic twin, so CI runs the whole pipeline with no key." width="100%">
</p>

Some ideas cannot be judged by building a quick version, because the unknowns are in
the territory around them: what the deeper topics are, how they depend on each other,
what could sink it, and where to begin. Give proto.pilot an idea and a little direction,
and it works that out into a folder of text plans.

A plan is not a finished answer. It is the cheapest way to see the shape of an idea
before spending anything on it.

## Get started

```bash
git clone https://github.com/skyrowlabs/proto-pilot && cd proto-pilot
python -m venv .venv && . .venv/bin/activate
pip install -e .
proto doctor          # the SDK, and credentials for each backend
```

Needs Python 3.11 or newer and Claude credentials: either `ANTHROPIC_API_KEY`, or a
Claude subscription through the Claude Code CLI. Research runs on the subscription
backend, so pass `--backend claude-code` (or set `PROTOPILOT_LLM=claude-code`). Nothing
else is needed: no Docker, no browser, no database.

Your first plan:

```bash
proto plan "open a small bakery that only sells sourdough" --direction "one person, rented kitchen" \
  --depth shallow --backend claude-code
```

It asks up to three questions and shows you the outline, where you can add, drop or
rename topics, then researches and writes the rest. `--no-research` gives a plan in a
minute or two, stamped *Not researched*; `--offline` makes no model calls at all.

## An example

A real run from 2026-11-16, with every field of the brief filled in:

```bash
proto plan "a survival game where you play a squirrel getting through its first winter" \
  --goal "decide whether a small playable slice is worth building, and what to build first" \
  --for "players who like short survival games that are cozy but tense" \
  --horizon "about three months of evenings and weekends, one developer" \
  --must "2D and single-player" --must "one forest and one winter, start to finish" \
  --not "multiplayer" --not "monetisation and a storefront launch" \
  --backend claude-code --yes --dir squirrel_survival
```

Green: six topics researched and 22 sources cited, with research taking about 17
minutes. It wrote:

```
PLAN.md              the idea, the topic map, how topics connect, where to start
topics/<topic>.md    one text plan per topic: findings, risks, unknowns, decisions
dreams.md            guesses at what else the idea could be, kept apart from the plan
sources.md           every page research cited, each one fetched during the run
```

Where the plan says to start:

1. Being small, cold and hunted in 2D
2. What makes it cozy and tense at once
3. The hoarding loop and what the player remembers
4. Shape of one winter, start to finish
5. What the first slice contains and how it is judged

The order is computed from the links between topics, not written by hand: the camera
question comes first because three other topics depend on it. Read the
[plan it wrote](docs/examples/squirrel_survival/PLAN.md), or the
[walkthrough](docs/examples/squirrel-survival.md) that reads it end to end.

A finding is cited only if the run fetched that page, read through a model's summary of
it, so a citation shows what was read, not that it is true. Everything else is labelled
an assumption, and a green plan means the structure holds, never that the plan is right.

## Going further

- [`docs/CLI.md`](docs/CLI.md): every command and flag: `plan`, `dream`, `ls`, `rm`, `prune`, `doctor`
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how a plan is made, pass by pass, and why
- [`docs/examples/`](docs/examples/README.md): worked runs

## Working on this repo

`proto` is the product; `./pp` is this repository's own tooling (its gates,
generators and scheduled jobs), never shipped to a user. The repo shell is generated
by [skeletor](https://github.com/skyrowlabs/skeletor).

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt && .venv/bin/python scripts/install_project.py
.venv/bin/pre-commit install --install-hooks && .venv/bin/python scripts/git/install_merge_drivers.py
./pp check pre-push      # every CI gate this host can run
./pp test unit           # the fast suite
```

Read [`AGENTS.md`](AGENTS.md) before changing anything;
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) has the rest.

## Licence

[MIT](LICENSE) © SKYROW LABS LLC
