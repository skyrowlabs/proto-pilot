# NOTES — the live parking lot

Open items, what got resolved, and what is worth doing next. Read before starting
work; update when you resolve something. This is the working state that does not
belong in `README.md` (the design document) or `AGENTS.md` (the rules — `CLAUDE.md`
is only a pointer at it).

> **Reconstructed 2026-08-28.** This lived at `~/skyrow.labs/proto-pilot-notes.md`,
> outside every repo, at a workspace root that is not a git repository. It was
> unbacked and it is gone; its previous contents could not be recovered. Both
> `CLAUDE.md` files pointed at it as the live parking lot, so two guides were
> describing a file that did not exist. It now lives here, in the repo, and is
> versioned like everything else.
>
> The items below are seeded from what `README.md` and `CLAUDE.md` already record
> as known-broken. Anything that was only in the old file is lost — if you
> remember an open item that is not here, add it.

## Open — pipeline gaps, in the order they bite

- **`auth: "password"` is accepted by the spec and implemented by no pass.** A
  spec can ask for it and nothing will build it. Either implement it or reject it
  at intake; silently accepting it is the worst of the three.
- **`jobs` and `external_apis` are recorded and ignored.** Same shape of problem:
  the spec captures them, no pass consumes them.
- **The offline baseline ignores `spec.screens`** and always generates its own
  CRUD set. Only the model path honours custom screens — so the thing the test
  suite exercises and the thing users get differ on exactly this point.
  **Closed by Phase 2 of [Archetypes and Theme](docs/TODO/archetypes-and-theme.md)**,
  which needs it before any archetype can have non-CRUD screens. Fix it there
  rather than separately.

## Open — the direction

- **[Archetypes and Theme](docs/TODO/archetypes-and-theme.md) is the next real
  piece of work**, and it is filed rather than summarised here. Short version:
  `Spec` is a CRUD data model, so every idea flattens into an admin panel and
  `intake.py`'s system prompt carries a five-paragraph essay compensating for
  what the type cannot say. Two orthogonal axes — `archetype` (shape) and
  `theme` (look) — with the archetype owning its questions, screens, prompt
  fragments and baseline.

  It is `planned`, not `ready`: the design is complete but unreviewed, and
  promoting a plan to `ready` is the act of handing it to an agent.

- **The improvement loop comes after it**, and is not filed yet. The primitives
  arrived with the skeletor `agentic` tier — `scripts/reporting/jobs.py`,
  `run_ledger.py` with its two rails, `agent_runner.py`'s argv contract,
  `fix_policy` defaulting to `none`, `declined` as a first-class outcome. What
  is missing and is proto.pilot's own to design is the **ratchet**: an iteration
  must leave the tree at least as green as it found it or be reverted, which the
  per-tree `git init` already makes nearly free. Note the two loops are
  different: skeletor's tier maintains *this repo*; the ratchet governs
  *generated prototypes*. They share primitives, not a schedule.

## Open — going public

- **The repo is still private.** Everything else on the public path is done
  (licence, CI, badges, tag, `develop`), but the badges render as broken images
  to anyone but the owner until the visibility flips. That flip is the one step
  here that is not a commit.
- ~~**No `CONTRIBUTING.md`, issue templates, `dependabot.yml` or `CODEOWNERS`.**~~
  All four arrived with the skeletor `governed` tier on 2026-09-01. They are
  the scaffold's generic wording and have not been read against this project;
  do that before the visibility flip, not after.

## Open — found in a neighbour, to report not fix

- **`skeletor-new --force` records files it did not generate.** Scaffolding
  into this existing tree wrote a `.skeletor.json` whose `files` map hashes
  `prototypes/kitten_chess/**`, `proto_pilot.egg-info/**`, `.pytest_cache/**`
  and every file under `protopilot/` and `skeleton/` — none of which came from
  a template. That map exists so `skeletor-upgrade` can three-way merge against
  the base it rendered, so an upgrade would treat this repo's actual source as
  template output. Found within ten minutes of being skeletor's first real
  consumer, which is the point: `bin/skeletor-verify` scaffolds into empty
  directories, so nothing in skeletor can see this.

  **Report it to skeletor; do not fix it from here** — the workspace rule is
  that the finder is not the owner. Until it is fixed, treat
  `bin/skeletor-upgrade` as unsafe on this repo.

## Traps — not bugs, but they will get you

- **A relative link to a sibling repo resolves on your machine and nowhere
  else.** Every skyrow.labs repo is a sibling checkout under one root, so
  `../skeletor` and `../../skyrow-workspace/...` are valid locally and broken
  for CI, which clones one repository, and for anyone who clones this one. It
  cost three red CI runs behind a green `./pp check pre-push`.

  Held now by `tests/test_doc_links_stay_in_repo.py`, which asks whether a link
  **escapes the repo root** rather than whether the path exists — a question
  with the same answer in both places. Name the sibling repo and its path in a
  code span; never make it a markdown link.

## Ideas — not scheduled

- **[Hosted proto.pilot](docs/hosted.md)** — put `proto new` behind a free public
  page to build a corpus for training a custom model later. Captured 2026-08-28
  as a long-term idea; would reclassify proto.pilot from an internal instrument
  to a minor product. Read the doc before acting on any part of it.

- **Make Claude optional — a local-model backend.** Captured 2026-08-28. Run Qwen
  (and whatever else is worth trying) on our own breeze.brain node and let `proto`
  drive it, so the pipeline is not bound to one vendor and a generation can cost
  electricity instead of API credit. This is the same internal-GPU-as-cost-play
  argument as the gpu-platform seam (`skyrow-workspace/strategy/seams/gpu-platform.md`,
  a sibling checkout), applied to proto.pilot instead of jam.sense, and it is what would make the free
  public tier in `docs/hosted.md` affordable at all.

  **The plumbing is nearly free.** `LLM` is a two-member Protocol — `offline: bool`
  and `structured(system, user, schema, label) -> dict`. A fourth backend is a class
  plus a name in `build_llm`, which already dispatches on `PROTOPILOT_LLM` over
  `'api' | 'claude-code' | 'offline'`. Nothing in the passes changes.

  **The real question is structured output.** `ClaudeLLM` gets a schema-valid object
  from the server (`format: {"type": "json_schema", ...}`), and every pass depends on
  that — the pipeline is built on typed per-pass schemas, not on parsing prose. A
  local model only matches that if the serving runtime does constrained decoding
  (vLLM guided decoding, llama.cpp GBNF, Ollama structured outputs). Pick the runtime
  for that property first; a backend that returns *almost* valid JSON is worse than
  no backend, because the repair loop will spend real attempts on it.

  Two smaller things to check when it happens: the stack brief is byte-identical
  across passes specifically to stay a cache prefix — that still pays off locally,
  but as a serving-side prefix cache rather than as Anthropic's, so confirm the
  runtime actually has one. And `ClaudeLLM` carries streaming and a refusal fallback
  that a local backend has no equivalent of and probably does not need; do not port
  the shape, port the interface.

  This is the engineering half. The research half — which open model, fine-tuned on
  what corpus, at what cost crossover, aimed at a public skyrow.ai — is
  R1 in the research queue (`skyrow-workspace/strategy/research.md`).

  Expectation-setting: the five passes each read the previous pass's real source, so
  context is long and quality-sensitive. Treat the first local backend as a way to
  *measure* how far a smaller model is from usable — the offline baseline already
  gives a floor and Claude gives a ceiling, so the corpus of green/red verdicts is
  the natural scoreboard. It is an experiment with a built-in grader, not a swap.

## Resolved

- **2026-09-01 — Phase 0 of the lifecycle work: both standing traps are gone.**

  **`proto ls` no longer prunes.** Reading a list must not delete from it, and
  this one did: `ls` called `prune()`, so merely *looking* at the prototypes
  removed every entry whose directory had gone — which is how the whole registry
  was lost when a scratch directory was wiped. The web front end was worse, since
  it pruned on every page view. `ls` now reports a missing tree as `gone` and
  `proto prune` is the explicit command that acts on it.

  **Docker is now a second, independent source of truth.** Every generated
  `compose.yml` and `Dockerfile` stamps `com.protopilot.slug` / `.path` /
  `.project` onto all four resource kinds — container, volume, network, image.
  `proto gc` reads them back and collects anything whose tree no longer exists.
  That closes the orphan leak properly rather than by remembering to use
  `proto rm`: the label survives `rm -rf`, a wiped scratch dir and a pruned
  registry, so an orphan stays findable when nothing on disk points at it.

  The label vocabulary lives once, in `protopilot/containers.py`, and
  `tests/test_containers.py` renders a real skeleton and fails if the writer
  stops emitting a label the reader filters on — the one defect class a
  same-file test cannot see.

  Also: `proto up` now refuses a port something else holds and offers
  `--port N`, which moves compose.yml and the spec together (the port is frozen
  into compose.yml at generation, so two prototypes generated months apart can
  collide and the docker bind error names neither). `proto down --all` stops
  everything. Verified against real Docker end to end, not just fakes: booted a
  generated tree, confirmed `ls` reported it `up`, deleted the tree with
  `rm -rf`, and `gc` found and collected all five resources.


- **2026-09-01 — the repo was re-housed on skeletor's `agentic` shell.**
  `skeletor-new . --force --tier agentic --cli pp`, then the pipeline was kept
  and the old hand-written shell replaced. Only **seven** files collided
  (`README.md`, `CLAUDE.md`, `pyproject.toml`, `.gitignore`, `.env.example`,
  `tests/conftest.py`, `.github/workflows/ci.yml`) and each was merged by hand
  rather than overwritten — `pyproject.toml` mattered most, because the
  scaffold's copy is tool config with no `[project]` block at all, so taking it
  whole would have silently deleted the packaging and the `proto` entry point.

  What moved unchanged: `skeleton/`, every module under `protopilot/`, and the
  whole existing test suite. This was a re-housing, not a rewrite.

  Decisions worth not re-litigating:

  - **Two CLIs.** `proto` is the product (installed, `[project.scripts]`);
    `./pp` is this repo's tooling (repo-root, `cli/`). Separate env prefixes,
    `PROTOPILOT_*` and `PP_*`. AGENTS.md Rule 15.
  - **Direct commits to `develop` are normal here**, recorded in AGENTS.md
    Rule 7 with its expiry: the exemption ends the day the repo goes public.
  - **The scaffold's CI does not run on pushes to `develop`** — it ships
    `push: [main]` plus pull-request events, which is right for a PR-only flow
    and would have left every commit here ungated. `develop` was added to the
    push trigger, and the 3.11–3.14 matrix was carried over from the old
    workflow because it is the only thing that checks `requires-python`.
  - **Line length 120**, the scaffold's default, kept rather than fought:
    black at 120 produced a *smaller* diff over the existing code than at 88.
  - `CLAUDE.md` is now a pointer to `AGENTS.md`. **Rules go in `AGENTS.md`.**

  Cost paid, for the record: `pytestmark = pytest.mark.unit` added to all
  thirteen test modules (the unit job selects by marker), 24 files reformatted,
  four unused imports removed, and three type-honesty fixes — `drive_to_green`
  now takes a `Verifies` Protocol rather than the concrete `Verifier`, which is
  what makes the fake in `tests/fakes.py` an honest second implementation
  instead of a lie the type checker was right about.


- **2026-08-30 — prepared to go public: licence, CI, badges, tag, `develop`.**
  MIT `LICENSE` added (there was none, which was the only hard blocker). CI went
  from one Python 3.12 job on `checkout@v4` to a 3.11–3.14 matrix on v7 actions
  with `concurrency`, `permissions: contents: read` and `workflow_dispatch` — the
  matrix is the first thing to actually *check* `requires-python = ">=3.11"`,
  which until now was a claim nothing verified. `v0.1.0` tagged, since
  `pyproject.toml` had carried that version with no tag behind it and the version
  badge would have rendered empty. Four badges added to the README.

  `develop` cut at the same time, mirroring what sky.boss did the day *it* went
  public — see [Branches in `CLAUDE.md`](CLAUDE.md). The workspace table in
  `../skyrow-workspace` still lists proto.pilot as neither public nor on
  `develop`; that is a separate repo and a separate commit.

- **2026-08-30 — the README's stale Status section is fixed.** It had claimed the
  `passes/` prompts were never run live, and omitted Pillow, the browser stage
  and the venv requirement. All four corrected in place; the Install section now
  says why the venv is mandatory and what the three extras are for. Going public
  is what forced it — the drift had been getting re-copied for weeks because
  nobody outside was reading it.

- **2026-08-28 — `feat/subscription-backend-and-front-end` landed on `main`, and the
  branch is deleted.** It carried the web front end, the `ClaudeCodeLLM` subscription
  backend, prototype lifecycle commands, the registry, the browser stage, and
  `CLAUDE.md` itself — almost everything true about this repo lived on one unmerged
  branch, which is why it was worth naming here. `main` is now the only branch.

_(nothing before that: the pre-2026-08-28 history was lost with the old file.)_
