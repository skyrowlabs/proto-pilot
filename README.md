# proto.pilot

<p align="center">
  <a href="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml/badge.svg?branch=develop"></a>
  <a href="https://github.com/skyrowlabs/proto-pilot/tags"><img alt="Latest tag" src="https://img.shields.io/github/v/tag/skyrowlabs/proto-pilot?label=version"></a>
  <a href="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml"><img alt="Python 3.11 to 3.14" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-blue"></a>
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/github/license/skyrowlabs/proto-pilot"></a>
</p>

A framework for prototyping ideas with agents.

Give it an idea and a little direction; get back a prototype running in Docker.

```bash
proto new "track camping gear across trips" --direction "make it feel like a checklist"
```

```
intake...

Gear List (gear_list)  ->  port 8080
  Track what gear goes on which trip, and what is still unpacked.
  entities:
    Trip
      title: str
      starts_on: date
    Item (belongs to Trip)
      name: str
      packed?: bool
  screens:
    /                        custom   Home
    /trips                   list     Trips
    ...

Generate this? [Y/n]

rendering skeleton...   24 skeleton files
  pass schema...  app/models.py
  pass smoke...   tests/test_smoke.py
  pass seed...    app/seed.py
  pass routes...  app/routes.py
  pass ui...      5 templates
  verify (attempt 1)...
    failed at tests: the smoke tests failed
  pass repair...
    patched app/templates/trips_list.html
  verify (attempt 2)...
    green -- app is up on http://localhost:8080

  Gear List is up:  http://localhost:8080
```

The output is a small FastAPI + Postgres app you can open, click through, and
throw away. Not a starting point for production — a thing to look at this
afternoon.

## Install

```bash
git clone https://github.com/skyrowlabs/proto-pilot && cd proto-pilot
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
proto doctor          # checks Docker, the SDK, credentials and a free port
```

The virtualenv is not optional advice — on a distro whose Python is externally
managed (Arch, and Debian since 3.11) a bare `pip install -e .` refuses to run.

Needs Python 3.11 or newer, Docker with Compose v2, and Claude credentials —
either `ANTHROPIC_API_KEY`, or a Claude subscription driven through the Claude
Code CLI.

Three optional extras: `dev` pulls the generated app's stack too, because the
end-to-end test runs a generated tree in process; `browser` adds Playwright, and
without it the browser verification stage is **skipped and reported as skipped,
never as green**; `web` is the front end behind `proto serve`.

## Commands

| | |
|---|---|
| `proto new IDEA` | generate, boot, verify, hand back a URL |
| `proto add CHANGE` | amend the spec, regenerate, re-verify |
| `proto up` / `down` / `logs` / `test` | the obvious things |
| `proto spec` | what this project actually promised |
| `proto ls` | every prototype on this machine, and which are running |
| `proto rm` | delete one: containers, data and the tree |
| `proto prune` | forget registry entries whose directory is gone |
| `proto gc` | collect Docker resources a deleted tree left behind |
| `proto doctor` | why it will not work here |

`ls` is read-only, and `down --all` stops everything at once. `gc` exists
because only `proto rm` cleans up after itself: a tree removed with `rm -rf`
leaves a container, a volume, a network and an image with nothing on disk
pointing at them. Every generated `compose.yml` stamps the tree's absolute path
onto each resource as a Docker label, so those orphans stay findable by asking
Docker — after the registry has been pruned, wiped, or never written.

Useful flags on `new`: `--offline` (no API calls, see below), `--no-verify`
(generate without booting), `--port`, `--attempts N`, `--yes`.

## How it works

    idea
      -> spec.json          typed, small, reviewed by a human
      -> skeleton           copied, never generated
      -> five passes        each fed the previous pass's real source
      -> docker compose up  observed, not assumed
      -> repair loop        bounded, with a floor

Five decisions carry most of the weight.

**The stack is fixed, not chosen.** FastAPI, server-rendered Jinja, SQLAlchemy
2.0, Postgres, and Pillow so a prototype can draw its own images instead of
hotlinking one. No JS build step, no CDN, no migrations. A generator that picks
a stack per idea produces N unrunnable variants and you debug all of them.
Everything in `skeleton/` — the Dockerfile, the compose file, `app/main.py`,
`app/db.py`, the stylesheet, `tests/conftest.py` — is copied byte for byte
into every app, so it is debugged once rather than once per prototype.

**The model can only write five paths.** `app/models.py`, `app/routes.py`,
`app/seed.py`, `app/templates/*.html` (except `base.html`), and
`tests/test_smoke.py`. Everything else is refused by `files.py` before it
reaches disk. Model output is data, not authority, and the parts of the tree
that are known to work are the parts the model must not be able to touch.

**Tests are generated before the code they test.** The pass order is
`schema -> smoke -> seed -> routes -> ui`. Smoke tests come second, generated
from the spec, when no route exists yet — so they describe what was asked for
rather than what got built. The routes pass is then handed those tests as its
target. Tests written after the code describe whatever the code happened to
do.

**Each pass reads the previous pass's real source**, not a description of it.
A routes pass told "there is a Trip model" invents a field name; one handed
`models.py` does not. The UI pass goes last and gets `routes.py`, because a
template referencing a context key no route passes is the single most common
way a generated app 500s.

**Nothing is handed back unobserved.** `verify.py` brings the stack up, waits
on `/healthz` (which checks the database, so it stays red while Postgres is
still coming up), runs the smoke suite inside the container, and captures the
logs. On red, the repair pass gets the stage, the output, the container logs
and every generated file, and returns a minimal patch. Three attempts.

Then a floor: if it cannot get to green, the tree is handed back anyway with a
`RUNBOOK.md` saying exactly which stage is red, what the last error was, and
what was tried. A prototype whose broken shape you know beats a mystery, and
both beat a loop that never terminates.

One guard the prompt cannot enforce: if a repair shrinks the smoke suite, the
file is reverted. Green because there is nothing left to fail is the only
failure mode here that nobody would notice.

With the `browser` extra installed there is a further stage, and it exists
because every other one is blind to the browser: `/healthz` returns 200 for a
page that paints nothing, and the smoke suite runs through an in-process client
that never executes a script tag. The browser stage loads every screen for real
and fails a page that rendered nothing visible. Without Playwright it is skipped
and reported as skipped — never as green.

## The offline baseline

Every pass has two implementations — a prompt and a deterministic generator in
`baseline.py`. `--offline` runs the second one: no API calls, no key, a plain
CRUD app.

It exists for three reasons, in increasing order of importance. It is a fast
free path to a working skeleton. It is the worked example each prompt is
written against. And it is what the test suite runs, so the whole pipeline —
skeleton, five passes, write guard, repair loop — is exercised on every commit
with no key and no Docker daemon. A pipeline that can only be tested with a
network call and a credit card stops being tested.

`proto add` needs the model; the baseline cannot read a change request.

## Testing

```bash
./pp test unit          # or: python -m pytest -q
```

The generated tree is the test. `tests/test_generate.py` generates a
two-entity parent/child app offline and runs *that app's own smoke suite*
against SQLite in a subprocess — which exercises the generated models, routes,
templates, seed data and form coercion without needing Postgres or Docker.
Docker and the API are faked (`tests/fakes.py`) so the verify and repair loops
— the two parts most likely to be wrong and least likely to be covered by an
end-to-end run — are tested directly.

## Model usage

Claude Opus 5, adaptive thinking, `effort: high`, structured output against a
JSON Schema per pass, streaming (code generation runs long enough that a
non-streaming request trips the SDK's HTTP timeout). The stack brief is
byte-identical across passes and repair attempts so it stays a cache prefix.
Server-side refusal fallback is on by default, so a safety refusal on one pass
does not abandon a generation that is most of the way done. Override with
`PROTOPILOT_MODEL` / `PROTOPILOT_EFFORT`.

## Status

Early, and honest about it. Known gaps, in the order they will bite:

- `auth: "password"` is accepted by the spec and not implemented by any pass.
  Either it gets built or intake should reject it; silently accepting it is the
  worst of the three.
- `jobs` and `external_apis` are recorded and otherwise ignored — a spec that
  needs either will generate an app that does not have it.
- The offline baseline ignores `spec.screens` and always generates its own
  CRUD set. Only the model path honours custom screens, so the thing the test
  suite exercises and the thing you get differ on exactly that point.

The prompts in `passes/` have been run against the live API; the baseline is
what CI covers, for the reason given above. `NOTES.md` is the live parking lot —
open items, what got resolved, and what is worth doing next.

## Working on this repo

Two command-line tools live here and they are deliberately not the same thing.
**`proto` is the product** — installed onto your PATH, run from wherever you
want a prototype. **`./pp` is this repository's own tooling** — its gates,
generators and scheduled jobs, run from the repo root and never shipped to a
user. One `--help` serving a person generating an app and a person maintaining
the generator would serve neither.

The repo shell is generated by **skeletor** — a sibling checkout, not part of
this repository — at the `agentic` tier;
`.skeletor.json` records exactly how, and `bin/skeletor-upgrade` carries
template changes in. That means the docs lifecycle, the rules in `docs/rules/`,
the marker-based test suites and the scheduled-job machinery are not local
inventions — they are one shared shell, debugged once.

```bash
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
.venv/bin/pre-commit install --install-hooks
./pp check pre-push      # everything CI blocks on
./pp test unit           # the fast suite
```

[`AGENTS.md`](AGENTS.md) is the rules — read it before changing anything.
[`docs/README.md`](docs/README.md) indexes the rest;
[`.github/DOCS_INDEX.md`](.github/DOCS_INDEX.md) is the routing table an agent
reads so it loads two documents instead of all of them.

## Licence

[MIT](LICENSE) © SKYROW LABS LLC
