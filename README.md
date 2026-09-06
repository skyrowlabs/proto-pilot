# proto.pilot

<p align="center">
  <a href="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml/badge.svg?branch=develop"></a>
  <a href="https://github.com/skyrowlabs/proto-pilot/tags"><img alt="Latest tag" src="https://img.shields.io/github/v/tag/skyrowlabs/proto-pilot?label=version"></a>
  <a href="https://github.com/skyrowlabs/proto-pilot/actions/workflows/ci.yml"><img alt="Python 3.11 to 3.14" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-blue"></a>
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/github/license/skyrowlabs/proto-pilot"></a>
</p>

A framework for prototyping ideas with agents.

Give it an idea and a little direction; get back a prototype you can run.

```bash
proto new "track camping gear across trips" --direction "make it feel like a checklist"
```

```
intake...

Gear List (gear_list)
  Track what gear goes on which trip, and what is still unpacked.
  target: tui
  archetype: crud
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

rendering skeleton...   19 skeleton files
  pass schema...   app/models.py
  pass smoke...    tests/test_smoke.py
  pass seed...     app/seed.py
  pass screens...  app/screens.py
  pass ui...       app/app.tcss
  verify (attempt 1)...
    failed at tests: the smoke tests failed
  pass repair...
    patched app/screens.py
  verify (attempt 2)...
    green -- HomeScreen painted 14 widget(s)

  Gear List is ready:  cd ./gear_list && make run
```

The output is a small Textual + SQLite app you run in your terminal: one
process, one file, no container. Not a starting point for production — a thing
to look at this afternoon and throw away.

`--target web` gives you the other medium instead: FastAPI + Postgres in
Docker, opened in a browser. Both are first class and both are generated in CI;
the terminal one is the default because it is the cheaper thing to look at and
because nobody mistakes it for a product. `proto targets` lists them.

## Install

```bash
git clone https://github.com/skyrowlabs/proto-pilot && cd proto-pilot
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
proto doctor          # what each target needs, the SDK, credentials, a port
```

The virtualenv is not optional advice — on a distro whose Python is externally
managed (Arch, and Debian since 3.11) a bare `pip install -e .` refuses to run.

Needs Python 3.11 or newer and Claude credentials — either `ANTHROPIC_API_KEY`,
or a Claude subscription driven through the Claude Code CLI. **Docker with
Compose v2 is needed only for `--target web`**; the default target is one
process and a SQLite file, so `proto doctor` reports a missing daemon as a
limitation on one target rather than as a failure.

**`textual` and `sqlalchemy` install with the tool, not as an extra.** The
terminal target verifies **in process** — there is no container between
proto.pilot and the tree it is checking, so a generated app's imports have to
resolve in the interpreter running `proto`. That is a real cost of the default
target and it is stated rather than hidden; the web target still needs neither
at runtime, because its tree is built and tested inside Docker.

Three optional extras: `dev` pulls the web target's stack too, because the
end-to-end test runs a generated tree in process; `browser` adds Playwright, and
without it the web target's browser verification stage is **skipped and reported
as skipped, never as green** — the terminal target's equivalent needs no extra
and is never skipped; `web` is the front end behind `proto serve`, which is
**pinned to `--target web`** and does not follow the default, because it hands
back a link you click and a terminal app has no link.

## Commands

| | |
|---|---|
| `proto new IDEA` | generate, boot, verify, hand it back |
| `proto add CHANGE` | amend the spec, regenerate, re-verify |
| `proto up` / `down` / `logs` / `test` | the obvious things |
| `proto spec` | what this project actually promised |
| `proto archetypes` | what shapes this build can generate, and what each asks |
| `proto targets` | what media it can generate into, and what each can build |
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

`up`, `down`, `logs`, `test`, `reset` and `gc` are Docker verbs and apply to a
`--target web` prototype. A terminal prototype has no container to start,
detach or orphan, so those commands refuse it by name and say what to type
instead — `make run` in the tree. There is nothing for `gc` to find either: a
terminal verify writes its throwaway SQLite files into `<tree>/.dbs/`, inside
the tree, so deleting the tree takes everything with it. `prune` is about the
registry rather than Docker and applies to any prototype.

Useful flags on `new`: `--target` (which medium; default `tui`), `--offline`
(no API calls, see below), `--no-verify` (generate without booting), `--port`,
`--attempts N`, `--yes`.

## How it works

    idea
      -> spec.json          typed, small, reviewed by a human
      -> the target's skeleton   copied, never generated
      -> five passes        each fed the previous pass's real source
      -> started and driven  observed, not assumed
      -> repair loop        bounded, with a floor

Five decisions carry most of the weight.

**The stack is fixed, not chosen.** Per target, and never per idea. The
terminal target is Textual over SQLAlchemy 2.0 and one SQLite file, in one
process. The web target is FastAPI, server-rendered Jinja, SQLAlchemy 2.0,
Postgres, and Pillow so a prototype can draw its own images instead of
hotlinking one. Neither has a JS build step, a CDN or migrations. A generator
that picks a stack per idea produces N unrunnable variants and you debug all of
them.

Everything in `skeleton/<target>/` is copied byte for byte into every app, so
it is debugged once rather than once per prototype — the Dockerfile, the
compose file and the stylesheet on the web side; `app/main.py`, `app/db.py`,
`app/base.py` and the test harness on both. Which tree a spec gets is
`spec.target`, and a target owns rather more than the tree — fifteen things,
where the design predicted four. Six of the eleven it did not predict are
sentences this tool prints about itself that turned out to be true only of
Docker: a port, a URL, `make up`, "Container logs".
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#what-a-target-owns) has the
contract.

**The model can only write a handful of paths**, and the list belongs to the
target. On the web target: `app/models.py`, `app/routes.py`, `app/seed.py`,
`app/templates/*.html` (except `base.html`), and `tests/test_smoke.py`. On the
terminal target: `app/models.py`, `app/screens.py`, `app/seed.py`,
`app/widgets.py`, `app/app.tcss` and `tests/test_smoke.py`. Everything else is
refused by `files.py` before it reaches disk — and `files.py` holds no list of
its own, so a second target cannot inherit the wrong one by default. Model
output is data, not authority, and the parts of the tree that are known to work
are the parts the model must not be able to touch.

Enforcing that takes two guards. `files.py` decides what the model's *answer*
may write, and `llm.ISOLATION` decides what the process producing that answer
can do — the `claude-code` backend shells out to a CLI that has a filesystem
and a shell by default, so without the second guard the first one is a rule
about JSON rather than about the disk.

**Tests are generated before the code they test.** The pass order is
`schema -> smoke -> seed -> routes -> ui` on the web target and
`schema -> smoke -> seed -> screens -> ui` on the terminal one. Smoke tests come
second, generated from the spec, when nothing they test exists yet — so they
describe what was asked for rather than what got built, and the fourth pass is
handed them as its target. Tests written after the code describe whatever the
code happened to do.

**Each pass reads the previous pass's real source**, not a description of it.
A routes pass told "there is a Trip model" invents a field name; one handed
`models.py` does not. The UI pass goes last and gets `routes.py`, because a
template referencing a context key no route passes is the single most common
way a generated app 500s.

**Nothing is handed back unobserved.** On the web target `verify.py` brings the
stack up, waits on `/healthz` (which checks the database, so it stays red while
Postgres is still coming up), runs the smoke suite inside the container, and
captures the logs — `build -> health -> tests -> browser`. On the terminal
target `verify_tui.py` imports the tree, starts it under `App.run_test`, drives
it, runs the smoke suite and compares the rendered screen buffer to that of an
application with nothing in it — `import -> boot -> tests -> paint`, with no
daemon, no port and no health race. On red, the repair pass gets the stage, the
output, whatever the app printed and every generated file, and returns a
minimal patch. Three attempts.

Then a floor: if it cannot get to green, the tree is handed back anyway with a
`RUNBOOK.md` saying exactly which stage is red, what the last error was, and
what was tried. A prototype whose broken shape you know beats a mystery, and
both beat a loop that never terminates.

One guard the prompt cannot enforce: if a repair shrinks the smoke suite, the
file is reverted. Green because there is nothing left to fail is the only
failure mode here that nobody would notice.

The last stage exists because every other one is blind to what was drawn. On
the web target `/healthz` returns 200 for a page that paints nothing and the
smoke suite runs through an in-process client that never executes a script tag,
so with the `browser` extra installed there is a stage that loads every screen
for real; without Playwright it is skipped and reported as skipped, never as
green. The terminal target's equivalent is two strings — the app's screen
buffer against an empty application's — so it needs no extra, is never skipped,
and is the same check on every machine.

On the terminal target that last stage is a **backstop rather than the first
line**, and it is worth knowing which fires. `skeleton/tui/tests/test_boots.py`
already asserts a non-empty buffer, and it is skeleton, so every generated tree
carries it — a blank app goes red at `tests`, one stage earlier. `paint` catches
the case the tree's own suite cannot: an app that mounts, answers every query
and shows nothing, with a smoke suite that never thought to look.

## The offline baseline

Every pass has two implementations — a prompt and a deterministic generator in
`baseline.py`, plus `baseline_tui.py` for the three files whose content depends
on the medium. `--offline` runs the second one: no API calls, no key, a plain
CRUD app in whichever medium the target names.

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

The generated tree is the test, once per target. `tests/test_generate.py`
generates a two-entity parent/child web app offline and runs *that app's own
smoke suite* against SQLite in a subprocess; `tests/test_tui_target.py` does the
same for a terminal app and then `tests/test_tui_verify.py` drives it through
the real verifier, blank-screen check included. Both exercise the generated
models, seed data and form coercion without needing Postgres, Docker or a
browser.
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

(The third gap that used to be listed here — the offline baseline ignoring
`spec.screens` — was closed on 2026-09-01. `spec.screens` is now authoritative
and every custom screen gets a route, a template and a smoke test.)

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
