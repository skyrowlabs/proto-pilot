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

## Resolved

_(nothing recorded yet — the pre-2026-08-28 history was lost with the old file)_
