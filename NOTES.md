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

## Open — docs

- **`README.md`'s Status section is stale in four known ways.** It claims the
  `passes/` prompts have never been run live (they have), and it omits Pillow,
  the browser stage, and the venv requirement. Fix the README rather than
  propagating it; this note exists because the drift keeps getting re-copied.

## Open — repo state

- **`feat/subscription-backend-and-front-end` is 15 commits ahead of `main` and
  unmerged.** It carries the web front end, the subscription (`ClaudeCodeLLM`)
  backend, prototype lifecycle commands, the registry, the browser stage, and
  `CLAUDE.md` itself. Almost everything true about this repo is on that branch.
  Landing it is a prerequisite for anything else.

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

_(nothing recorded yet — the pre-2026-08-28 history was lost with the old file)_
