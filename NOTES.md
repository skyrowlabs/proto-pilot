# NOTES — the live parking lot

Open items, what got resolved, and what is worth doing next. Read before starting
work; update when you resolve something. This is the working state that does not
belong in `README.md` (the design document) or `CLAUDE.md` (the rules).

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

## Open — going public

- **The repo is still private.** Everything else on the public path is done
  (licence, CI, badges, tag, `develop`), but the badges render as broken images
  to anyone but the owner until the visibility flips. That flip is the one step
  here that is not a commit.
- **No `CONTRIBUTING.md`, issue templates, `dependabot.yml` or `CODEOWNERS`.**
  sky-boss has all four. None of them block going public; they are what stops
  the first outside issue from arriving shapeless.

## Traps — not bugs, but they will get you

- **`proto ls` calls `prune()`, which deletes registry entries whose directory is
  missing.** Running `ls` merely to look at the list is what emptied the whole
  registry when `/tmp` was wiped. Do not point generated prototypes at a volatile
  scratch dir.
- **Orphaned Docker volumes survive a deleted tree.** `registry.delete` drops
  them; a tree removed any other way leaks one.

## Ideas — not scheduled

- **[Hosted proto.pilot](docs/hosted.md)** — put `proto new` behind a free public
  page to build a corpus for training a custom model later. Captured 2026-08-28
  as a long-term idea; would reclassify proto.pilot from an internal instrument
  to a minor product. Read the doc before acting on any part of it.

- **Make Claude optional — a local-model backend.** Captured 2026-08-28. Run Qwen
  (and whatever else is worth trying) on our own breeze.brain node and let `proto`
  drive it, so the pipeline is not bound to one vendor and a generation can cost
  electricity instead of API credit. This is the same internal-GPU-as-cost-play
  argument as [the gpu-platform seam](../skyrow-workspace/strategy/seams/gpu-platform.md),
  applied to proto.pilot instead of jam.sense, and it is what would make the free
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
  [R1 in the research queue](../skyrow-workspace/strategy/research.md).

  Expectation-setting: the five passes each read the previous pass's real source, so
  context is long and quality-sensitive. Treat the first local backend as a way to
  *measure* how far a smaller model is from usable — the offline baseline already
  gives a floor and Claude gives a ceiling, so the corpus of green/red verdicts is
  the natural scoreboard. It is an experiment with a built-in grader, not a swap.

## Resolved

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
