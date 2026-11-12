# NOTES — the live parking lot

Open items, what got resolved, and what is worth doing next. Read before starting
work; update when you resolve something. This is the working state that does not
belong in `README.md` (what the tool is for) or `AGENTS.md` (the rules — `CLAUDE.md`
is only a pointer at it).

> **Reconstructed 2026-08-28.** This lived at `proto-pilot-notes.md`,
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

Nothing is open here for the plan pipeline. What a plan cannot do yet is in the
README, under *What a plan does not know yet*. Every item this section held was
about `proto new`, and is under *Resolved*, removed 2026-11-11.

## Open — the direction

**2026-11-11: prototyping was removed; planning is the whole product.** Planning
became the product on 2026-11-06, and five days later the layer that generated,
ran and verified apps left the tree. See
[`docs/ideas/plans-first.md`](ideas/plans-first.md); the tag `prototyping-final`
is the last commit that holds it.

- ~~**Archetypes and Theme is the next real piece of work.**~~ **Shipped
  2026-09-01**, all six phases, and filed at
  [docs/implementations/spec/](implementations/spec/archetypes-and-theme.md).
  `Spec` now has two orthogonal axes — `archetype` (shape) and `theme` (look) —
  with the archetype owning its questions, screens, prompt fragments and
  offline baseline, and the theme reaching the UI pass and nothing else.

  Read the landed-notes rather than this paragraph. Each phase spent one live
  call on the half the offline baseline cannot reach, and **every one of them
  found a prompt defect** — a confidence signal measuring the length of a list
  rather than the quality of a fit, a menu that forbade repeating questions it
  never showed, a CRUD-shaped instruction telling a board game to render a
  delete form for a route that does not exist. None was findable from inside
  the test suite.


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

- **proto.pilot's footprint in skyrow-workspace, so the next session does not
  guess at it.** Reporting the pivot, I flagged `strategy/seams/gpu-platform.md`
  and `strategy/seams/model-hosting-handoff.md` as possibly leaning on the
  hosted-tier framing. **Neither mentions proto.pilot at all** — `grep -ci proto`
  returns 0 for both. The framing was in `strategy/research.md` R1 and in the
  brief, both since amended by them.

  I reasoned from which docs *ought* to own that framing instead of grepping a
  sibling checkout that was right there, having already grepped a different
  sibling twice the same day. The tell is in the wording I used — "worth knowing
  *if* the seam doc leans on it anywhere" is the sentence you write instead of
  checking.

  **That list was wrong too, and both of us got it wrong differently.** I
  scoped my grep to `strategy/`; two files sit above it, and one is
  `workspace.md` — which *is* the workspace CLAUDE.md, reached through the
  symlink at the workspace root's `CLAUDE.md`, carrying seven mentions including the
  branch rule about this repo. **A `strategy/`-scoped grep is structurally blind
  to the guide that governs the workspace.** Theirs used `grep -i proto`, which
  matches `prototype`, so it carried three files that never mention us.

  So I recorded the matcher-blindness lesson in this file and committed the same
  error inside the hour — not by failing to grep this time, but by *choosing a
  scope* and then reading the result as the whole answer. The blindness moved
  from the pattern to the path, and nothing in the output said so.

  The settled list, verified here with `grep -rn -E 'proto\.pilot|proto-pilot|`proto`'`
  over the whole repo — nine documents, plus two neither of us had:

  | hits | file |
  | ---- | ---- |
  | 20 | `strategy/research.md` — **more than the brief**; R1 is the real blast radius |
  | 16 | `strategy/projects/proto-pilot.md` |
  | 7 | `workspace.md` (the workspace CLAUDE.md) |
  | 3 | `strategy/naming.md` |
  | 2 | `strategy/portfolio.md`, `status.md` |
  | 1 | `strategy/{sequencing,README,map}.md`, `scripts/refresh-status.py`, `project-diagram.drawio` |

  **Not the seams** — `grep -ci proto` returns 0 for both. Relative paths into a
  sibling are prose only, never a markdown link, per the trap above.

  Their R1 observation is the one worth carrying, and it is recorded in
  [sketches-not-scaffolds](ideas/sketches-not-scaffolds.md): tabling the
  hosted page **detaches** the service ambition rather than killing it, so R1
  can no longer assume proto.pilot is skyrow.ai's front door.

- **`check_doc_tables.py` was green having looked at 4 documents out of 24, and
  I had seen the reason and called it harmless.** `_DOC_PATH` was
  `docs/[A-Za-z0-9_-]+\.md` — no slash in the character class — so every nested
  row was invisible in **both** directions. It could not satisfy a registration,
  and a row left pointing at a deleted nested doc could never be reported
  dangling: the reverse half of that check had never once worked below the top
  level.

  **I looked straight at that pattern earlier the same day.** I worked out that
  a row for `docs/ideas/hosted.md` would be neither registered nor dangling, and
  wrote *fine* — because the only question I was asking was whether moving a doc
  into a subfolder would strand a row. It would not. I never turned it around
  and asked what else the pattern could not see. skeletor did, and the eight
  invisible rows here included `docs/ideas/README.md` — the row I had just
  added, and described as the thing that keeps that folder from being a hole.

  My first framing was "a fact used to answer one question does not stay used".
  skeletor's is sharper and is the one to keep:

  > **A negative result from a matcher means either the thing is absent or the
  > matcher is blind, and nothing in the output distinguishes them.**

  I asked "does this row become dangling?" and got *no*. The other reading of
  the same *no* is "this row cannot be seen at all", and one query cannot tell
  them apart. The habit that catches it is asking a matcher what it **did**
  match, not only whether it matched the thing you feared.

  Same shape, three instances now: `check docs` printing "4 doc(s), all
  registered" over a tree of 24; `pyright` printing `0 errors` over however many
  files, including zero (see below); and this. The remedy in all three is for a
  check to report its **scope** beside its verdict, which `check_doc_tables.py`
  now does.

- **`pyright` reports its verdict and its scope in the same breath, and we were
  reading only the verdict.** `pp check lint` takes the exit code, and "0
  errors, 0 warnings, 0 informations" is what a clean run and an *empty* run
  both print. Rename a directory named in `pyrightconfig.json`'s `include` and
  the gate stays green having checked nothing, with no line of output that
  differs. Found by following skeletor's aside about their template asserting
  `filesAnalyzed`; ours never had it.

  Not currently broken — 72 files analysed, genuinely clean. Held now by
  `tests/test_pyright_scope.py` (the template's, since 2026-11-05), which asserts the *precondition*
  (every `include` path resolves and holds at least one `.py`) rather than the
  result, so it stays fast and needs no pyright installed. The realistic way
  this empties is a directory that moved, which is what that catches.

  Fixed here to skeletor's predicate: a subfolder is routed by its own README
  **or its own path**, and a routed folder is not descended into, so
  `docs/implementations/spec/` is out of scope by construction rather than by
  exception. Two regexes rather than one, because a folder is routed by a row
  for *itself* — `docs/reports/regular/README.md` must not vouch for
  `docs/reports/`. Held by `tests/test_doc_routing_predicate.py`.

  The finding it produced: `docs/reports/` had three README-bearing subfolders
  nothing pointed at. Closed with one `docs/reports/README.md` owning all three
  rather than three rows, so a fourth report kind needs no table edit.

- **The archive strip in `add_frontmatter.py` is unreachable, in their template
  and therefore in every tree they have scaffolded.** `_derive(plan,
  archive=True)` pops `shelf_status` / `blocked_on` / `queue_order` from a filed
  plan, but line 79 skips any doc that already has frontmatter unless `--force`,
  and a plan being filed always has some. `regen.py` never passes `--force`, so
  `pp docs file` cannot strip them. Our first filed plan sat in the archive for
  two days saying `shelf_status: in-progress` with all six phases ticked.

  **The second layer is the one that matters.** Even reached, the strip would
  not fix it: `plans.py:104` reads the body header `> **Shelf-Status**:` *before*
  frontmatter, and no generator anywhere rewrites body headers. So the header
  outranks the field the strip repairs, and there is no command to fix — which
  is why the gate here is a test rather than one more careful step in `regen.py`.

  **Why no suite could see it.** `gen_impl_index.py` pops the same three keys
  when it builds the index, commenting that a stale `shelf_status` in the
  archive is "actively misleading" — so the problem was already known and the
  fix went into the **derived** artifact. The index renders clean while the
  document keeps the lie, and `regen.py --check` can never go red on a field it
  never renders. `pp check docs` was green on all five gates the whole time.
  A check made to look away from the thing it was written about.

  Reported 2026-09-03. **skeletor reproduced both layers, fixed both in
  `d15fd2b`, and corrected my placement** — the useful half of the exchange.

  I said the header needed a test because no generator could fix it. False:
  `docs file` is a generator, just not the one I was looking at. The backfill
  runs on every `docs index` and must not rewrite prose; a filing is a one-time
  deliberate move and may. So the strip belongs at the move, and the test is a
  ratchet for the hand-`git mv` route rather than the mechanism. Taken as
  theirs, `plans.strip_tank_headers()` owning it.

  They also found the half I missed while quoting the code around it: the same
  unreachable branch is the only thing that *adds* `category`, `completed` and
  `agent_value`, so those were absent from every archived doc this template has
  ever produced. On screen the whole time.

  And my `test_archive_is_not_empty` guard was wrong — it asserts a property of
  the corpus inside a test about documents, so it is red in a fresh tree that
  has done nothing wrong. Dropped; `test_docs_lifecycle.py` now constructs the
  corpus and reads the filed document back instead.

  **The line worth keeping is theirs: the nearest test to a defect is not a test
  for it.** `test_docs_lifecycle.py` had been filing a plan since the day it was
  written, with a fixture carrying the status in both forms, and asserted on
  index slugs without ever opening the result. Same mistake as the one in
  `gen_impl_index.py`, at a different distance — checking the artifact you
  generate instead of the artifact you produced.

- **`skeletor-new --force` records files it did not generate.** Scaffolding
  into this existing tree wrote a `.skeletor.json` whose `files` map hashes
  `prototypes/kitten_chess/**`, `proto_pilot.egg-info/**`, `.pytest_cache/**`
  and every file under `protopilot/` and `skeleton/` — none of which came from
  a template. That map exists so `skeletor-upgrade` can three-way merge against
  the base it rendered, so an upgrade would treat this repo's actual source as
  template output. Found within ten minutes of being skeletor's first real
  consumer, which is the point: `bin/skeletor-verify` scaffolds into empty
  directories, so nothing in skeletor can see this.

  Reported 2026-09-01. **skeletor confirmed it, fixed it, and corrected the
  half I had inferred rather than verified** — which is the useful part of the
  exchange and the reason the report said which was which.

  I guessed `skeletor-upgrade` would treat this repo's source as template
  output and merge over it. It would not: `cross_check()` renders the base and
  requires every recorded hash to match a file that base produces, so all 114
  foreign entries fail and it **refuses outright** before the merge loop runs.
  So nothing was ever going to be overwritten. The real damage was narrower and
  more annoying — `bin/skeletor-upgrade` was permanently unusable on the one
  case skeletor's own AGENTS.md calls "the usual case", failing with a message
  that reads as though *this* tree is at fault.

  So the accurate word is **unusable, not unsafe**. Stopping to report rather
  than running it was still right, but for a weaker reason than I gave.

  Their fix records what the scaffolder *did* rather than what it found, and is
  gated by `populated_tree_gate` in `bin/skeletor-verify`, which scaffolds into
  a seeded directory and an empty one and requires identical manifest keys.

  **Closed 2026-09-01.** The manifest is repaired and the upgrade has run;
  skeletor is at `v0.2.1`. Kept because the sequence is the record of a class
  of defect neither repo could find alone, and because the recipe changed twice
  while we followed it.

  Pruning the 228 entries to 114 got us to a *second* message class — not a
  surplus entry but a **wrong hash** on `.github/DOCS_INDEX.md`, which pruning
  cannot repair: a prune removes an entry that should not exist, and this one
  should exist with a different value. The cause was the same defect one layer
  in — `register_shipped_docs` scans the tree it writes into, so scaffolding
  over a repo that already had `docs/hosted.md` gave that doc a routing row,
  correctly, and the manifest then recorded the post-processed file rather than
  the render. Guessing the hash would have been worse than useless: the offline
  fallback uses the recorded hash on **both** sides of the matrix, so a wrong
  one reads an untouched file as "template moved, user untouched" and
  overwrites it.

  So the whole prune recipe was thrown away in favour of
  `bin/skeletor-upgrade <tree> --repair-manifest`, which re-derives the map
  from the base render — one line changed, idempotent. **Do not pass
  `--from-dir`**: with no base flag it renders at the `skeletor_ref` the
  manifest records (`v0.1.0-8-gabcac22`), which stays correct however far their
  template moves ahead.

  Two things came back to us in the upgrade. `ci.yml` conflicted and was ported
  by hand, taking their side on the install step, the push-branches comment and
  the `fetch-depth` comment — all three are our own reports written back
  better, and keeping our wording would have been keeping a divergence for
  sentiment. And `tests/test_docs_name_live_code.py` came back as a
  **collision** rather than an edit: we wrote it here, and their template now
  ships one at that path *because of our report*, so the first thing it
  collided with was the repo the idea came from. Theirs won — it reads the
  narrative directory list from `scripts/paths.py` instead of listing it, which
  is our own recompute-don't-list rule applied one level further than we
  applied it in the file that argues for it.

  **Pruned 2026-09-01: 228 → 114 entries.** Every foreign path is gone and the
  114 that remain are all genuine scaffold output (`scripts/`, `docs/`,
  `.github/`, `tests/`, `cli/`, `.claude/`). Their recipe needed a loop rather
  than one pass — the drift report prints 20 of 115 and truncates the rest, so
  a single regex sweep over it only ever sees a fifth. Six rounds converged.

  **Still blocked, on one file and a different failure.** `.github/DOCS_INDEX.md`
  reports *"recorded hash does not match the base render"*, which is not the
  "not produced" class and so is not prunable. Cause: at scaffold time that file
  already carried the `AGENTIC_AUTOMATION` and `hosted.md` rows, added by
  skeletor's own post-copy `register_shipped_docs` step — so the old
  `tree_hashes()` recorded the *post-processed* content while `cross_check`
  renders the pristine base, which has neither row. Same root cause as the
  foreign entries (recording what it found rather than what it made), one layer
  in, and not fixable from this side: the correct hash is of a render only
  skeletor can produce. Reported; awaiting their ruling. The upgrade still
  refuses, which is the guard working.

  **The `ci.yml` conflict is confirmed and does not gate us.** skeletor
  reproduced our tree shape at our exact ref and ran the whole sequence: the
  conflict is real and on the line we predicted (base `[main]`, ours
  `[main, develop]`, theirs `[develop, main]` — every three-way merge conflicts
  there, nothing to fix in the mechanism), but the upgraded tree's suite is
  green **with our `ci.yml` left unmerged**, because their new gate parses the
  branch list and asserts the set rather than the text. So: upgrade, leave our
  file alone, resolve when we want their comment and their install step — not
  before we can commit. The hunk lands in `tmp/upgrade/` and the resolution is
  "take theirs wholesale".

  **Both field reports we sent back were accepted and fixed in the template**,
  so `.github/workflows/ci.yml` will be a genuine three-way merge on upgrade —
  our push-trigger and project-install edits sit in the same region the template
  now changes. That makes it the eighth hand-merge and the interesting one. If
  it conflicts, our file is left untouched and the template's diff lands in
  `tmp/upgrade/`.

## Traps — not bugs, but they will get you

- **The upgrade was blocked by one hash, and both of our guesses about why were
  wrong.** Repaired 2026-09-03 in `434790a`; `bin/skeletor-upgrade . --dry-run`
  now produces a plan instead of a refusal. Kept because the *reasoning* failure
  is the reusable part, not the fix.

  `.skeletor.json` recorded a hash for `.github/workflows/ci.yml` that no base
  render could ever match. This note previously blamed two things and neither
  survives reading skeletor's source:

  - **"Written by our own `--repair-manifest`"** — false. It sets
    `manifest["files"]` and nothing else. `skeletor_ref` is written in exactly
    one place, `skeletor-new:425`, so `v0.2.0-dirty` came from the original
    scaffold and the repair merely inherited it.
  - **"We hand-ported `ci.yml`, taking their side on three hunks"** — false, and
    it *cannot* be true: the repair hashes `base_files`, the rendered base, never
    the target.

  What actually happened: the 2026-09-01 repair rendered its base from a skeletor
  checkout with uncommitted changes to that very file (`02897fa`, `e85e6fb`, both
  that day), so the recorded hash described a render that exists in no commit.
  skeletor closed the hole in `5230a7c` — a run that would write now refuses a
  dirty base, while `--dry-run` never is.

  **The lesson, which is the only reason this entry is still here: a remembered
  action is not evidence; a recoverable state is.** The hand-port was the thing
  I could *remember*, so I reached for it. `git log` on one path would have
  answered it and was available the whole time. Prefer the state you can check
  over the event you can recall.

  A second-order note worth keeping: the `--from-dir` warning in the old version
  of this entry described the correct mechanism — hashes rewritten from the wrong
  base while `skeletor_ref` is left alone — as a *hypothetical about a flag
  nobody had pulled*, while that exact mechanism had already fired through a
  different door and was the thing blocking us. **Having the mechanism and
  missing the instance is a cheap failure; the write-up still did the work.**
  It is what let skeletor find the real cause in minutes.

  **The `-dirty` ref never clears *by repair*, and it cleared on the next
  upgrade.** Both halves are true and this entry used to state only the first,
  which read as "forever". Nothing can recover a render that was never
  committed, and `--repair-manifest` does not touch the ref — but an **upgrade**
  writes a new one, and the v0.2.11 upgrade on 2026-09-04 recorded a clean
  `skeletor_ref: v0.2.11` from a clean checkout. The ⚠️ line is gone and the
  next base render is reproducible. `8dd1832` makes the message say so while it
  applies; what it does not say is which operation ends it.

  **It is permanent but bounded, and this entry used to overstate it.** skeletor
  ruled on 2026-09-04 (their `v0.2.6`): the banner is a provenance marker, not a
  live uncertainty about our tree. `cross_check` is a **bijection over the
  manifest** — every recorded hash matches the base render *and* every rendered
  file is recorded — and all three drift shapes are **refusals rather than
  warnings**. Our dry run produced a plan, so the manifest and the base agree
  file for file. The uncommitted edits in that 2026-09-01 checkout therefore
  touched nothing this scaffold ships, and the 8 conflicts the pending upgrade
  reports — the `ci.yml` hand-merge above being the eighth — are all **genuine
  divergence**, not manifest noise.

  The caveat stays live in exactly two shapes: under `--no-base`, and for a
  manifest with no `files` map. Neither is us. Read the banner as "the ref
  cannot be re-derived", not as "the plan may be wrong".

  **Still true and still worth avoiding: `--from-dir`.** It overrides the base,
  so a current checkout gets compared against a v0.2.0 manifest. skeletor fixed
  the advice in `24dc282`, but the flag remains what somebody reaches for with
  the producing checkout sitting next door.

- **The upgrade can see a collision but not a duplicate, and our own reporting
  loop manufactures duplicates.** Found 2026-09-03 in the first working dry run.

  `tests/test_pyright_scope.py` arrives under `✅ 2 new file(s) would be added`.
  We already have that gate, as
  `tests/test_lint_tool_parity.py::test_pyright_has_something_to_analyse` — not
  merely similar but the same gate argued the same way, down to asserting the
  precondition rather than parsing `--outputjson`. Accepting the upgrade as
  reported would leave one gate running twice under two names.

  **This is structural, not bad luck.** The sequence that improves the template
  is: we hit a hole, we write the gate *here* to close it, we report the idea,
  skeletor implements it at the path *they* choose. Both halves are correct and
  the paths differ for no reason. Every gate that reaches the template through a
  report is a candidate.

  No tool can fix it — `cross_check` compares paths and hashes, and seeing this
  would mean diffing *purposes*. The protocol can: skeletor knows which repo
  reported each gate (their docstring names us), so shipping the path back with
  the announcement turns a silent accretion into a decision. Reported to them.

  **Two of five, confirmed — skeletor supplied the list.** They shipped five
  things today from our reports; two land at paths we already occupy under a
  different name:

  | Our report | They shipped at | Ours |
  |---|---|---|
  | pyright scope | `tests/test_pyright_scope.py` | `test_lint_tool_parity.py::test_pyright_has_something_to_analyse` |
  | archive strip | `test_docs_pipeline.py::test_no_filed_plan_still_claims_a_shelf` | `tests/test_archive_drops_tank_fields.py` |

  The other three are clean: `check_doc_tables.py` was widened in the same file,
  `docs/reports/README.md` is ours, and `test_docs_name_real_commands.py` is the
  gate we argued against and were refuted on.

  **The resolution goes opposite ways, on one rule.** Co-location with the
  assertions a reader is already looking through wins. Keep *ours* for pyright:
  theirs sits in the python overlay only because `pyrightconfig.json` does,
  which is forced, while ours sits with the other lint-parity assertions by
  choice. Keep *theirs* for the archive strip: neither placement is forced, so
  only co-location decides, and `test_docs_pipeline.py` is where someone asking
  "what do we assert about the docs pipeline" looks. A rule that answers two
  cases differently is working, not failing.

  `test_archive_drops_tank_fields.py` can be deleted outright. An earlier
  version of this entry said to rescue its archaeology -- that the bug survived
  two layers -- into NOTES.md first. **That was wrong and skeletor caught it.**
  Both halves already ship in the template, beside the code they explain:
  `scripts/docs/add_frontmatter.py` on why sharing the guard made the archive
  branch unreachable in the only case it exists for, and `strip_tank_headers`'s
  docstring on why stripping frontmatter alone does not file a plan. Copying
  them here would have created a second copy of a reason -- the exact thing that
  drifts, and the thing this file keeps warning about.

  Both deletions belong in the same pass as the upgrade, not before it: doing
  them first leaves a gate gone and its replacement not yet arrived.

  **Done 2026-09-04, in the v0.2.11 upgrade.** Both gates deleted, both
  survivors verified present. Two things learned in the doing.

  `git rm` is **atomic across pathspecs**: one of the two files was untracked
  (the upgrade had just written it), so `git rm a b` failed on `a` and removed
  neither — while the surrounding script reported success for both. The verify
  step caught it. Report after checking, not after acting.

  And the deletion only sticks because of a release that landed while we waited.
  Before skeletor's **v0.2.7**, a file they ship and we delete was classified on
  being absent, restored on the next upgrade, and reported as a green
  `✅ new file added` — the one phrasing under which nobody looks, because a new
  file is what an upgrade is *for*. The next dry run now says
  `⏭️ skeletor wrote and you deleted — NOT restored`, naming ours.

  Check for this by hand on every upgrade. Not everything under "new file" is new.

- **A file we wrote will come back as a template *collision*, for the second
  time.** `docs/reports/README.md` was written here 2026-09-03, sent to skeletor
  on request, and shipped in their `905d421`. It is **not** in our
  `.skeletor.json` — 115 entries, and this path is not one — because we created
  it after the last upgrade. So `bin/skeletor-upgrade` will see a new template
  file at a path we already occupy, which is a collision rather than an edit.

  Exactly what happened to `tests/test_docs_name_live_code.py` (below): we wrote
  it, our report caused them to ship one at that path, and the first thing it
  collided with was the repo the idea came from. Theirs won that one on merit.
  **Expect the same shape and judge it the same way** — on which text is better,
  not on which came first.

  What this is *not*, and the correction is skeletor's: it is not that "two
  copies exist and neither generates the other." That is true of all 115
  scaffolded files here and is what a template *is* — noting it for this one
  would imply the other 114 are safe. The only unusual thing is the direction of
  travel, and that is provenance, not a trap.

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

- **[Sketches, not scaffolds](ideas/sketches-not-scaffolds.md)** — the
  direction as of 2026-09-03. proto.pilot emits a *terminal* app you look at and
  throw away, not a web app you could build on, and ships as a tool other
  developers run rather than a service we host. The request was never "make me a
  camping app" — it is "iterate to this idea and show me a prototype", and the
  loop only closes when the tool and the artifact share a surface.

  Decided as a direction, not as a plan: no phases, no acceptance criteria. It
  becomes a `docs/TODO/` plan when someone writes them. The migration is a
  `target` axis beside `archetype`, which turns the one real risk — that models
  write less Textual than FastAPI, so repair costs more — into a measurement
  rather than a bet.

- **[Hosted proto.pilot](ideas/hosted.md)** — **tabled 2026-09-03**,
  superseded by the above. Put `proto new` behind a free public page to build a
  training corpus. Kept because most of its analysis is about the pipeline
  rather than the service and survives the decision; what is tabled is the
  public front door and the corpus-from-strangers thesis.

- **Make Claude optional — a local-model backend.** Captured 2026-08-28. Run Qwen
  (and whatever else is worth trying) on our own breeze.brain node and let `proto`
  drive it, so the pipeline is not bound to one vendor and a generation can cost
  electricity instead of API credit. This is the same internal-GPU-as-cost-play
  argument as the gpu-platform seam (`skyrow-workspace/strategy/seams/gpu-platform.md`,
  a sibling checkout), applied to proto.pilot instead of jam.sense.

  **Its best argument was tabled with the hosted page and the idea got stronger
  anyway.** This used to be justified as what would make a free public tier
  affordable; there is no public tier now. But a tool other developers run on
  their own key does not need us to fund anything, so the remaining reasons are
  the durable ones — not being bound to one vendor, and generating a corpus
  overnight for the price of electricity. That was always the note's own claim:
  worth doing whether or not the page ever existed.

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

- **2026-11-11 — removed with the prototyping layer.** Every item below was open
  against `proto new`, a target, the console, the web front end, Docker or `gc`.
  None was fixed: the code each describes left the tree, and is readable at the
  tag `prototyping-final`. They are kept as written.

  - **The generated smoke suite is not idempotent against a persistent volume.**
    Found 2026-09-02 by running it twice. A `turn-based-game` tree on a fresh
    volume: `12 passed`. The same command again, same container, no changes:
    `1 failed, 11 passed`. `test_playing_a_square_changes_the_board` plays a real
    move and leaves it played, so the second run starts from a board the seed did
    not create, and eventually from a game that has finished.

    Nothing catches this. CI runs the suite once against a fresh tree, `proto new`
    runs it once, and the repair loop only re-runs it after regenerating — so
    every path that exists today gets the fresh-volume answer.

    It is not cosmetic and it lands squarely on the improvement loop: that plan's
    ratchet re-runs the suite against the same tree every iteration, so a suite
    that goes red on its second run would revert every iteration after the first
    and report the app as regressing when nothing changed. **Fix this before
    building the ratchet**, or the ratchet's first honest test will be against a
    broken measurement.

    The fix is a decision, not a patch: either the generated suite resets the
    rows it depends on (a fixture that reseeds), or the tests assert against
    state they create rather than state the seed left. The second is better and
    is a change to the smoke prompt and to every archetype's `smoke_py`.

  - **`proto gc` / `proto prune` / the Docker resource labels have no meaning for
    a terminal tree, and what to do about that is an open question.** Raised by
    Phase 3 of [the terminal target](implementations/spec/terminal-target.md), which says
    outright that this is a question and not a task, so it is recorded here rather
    than half-answered in code.

    They exist because a web tree removed with `rm -rf` orphans a container, a
    named volume, a network and an image, and `containers.py` finds them again
    from a label carrying the tree's absolute path. A `skeleton/tui/` tree is one
    process and one SQLite file: deleting it orphans nothing, there is no daemon
    to ask, and `find_orphans` would have nothing to find.

    **Do not delete any of it** — the web target still needs every part, and it is
    the only mechanism this repo has for resources that outlive their tree. **Do
    not extend it to `tui` either**, which is the tempting half: a label
    vocabulary applied to a target with no resources to label is machinery that
    reads as coverage and is not.

    What is actually undecided is narrower than it looks. `proto prune` is about
    the *registry*, not about Docker, and a terminal tree is registered like any
    other — so it probably applies unchanged and just needs saying. `proto gc` and
    the labels are the half that does not apply, and the question is whether they
    should say so for a `tui` project or stay silent.

    **Phase 5 answered what a terminal verify leaves behind, and the answer is
    "one directory".** `verify_tui` writes a fresh SQLite file per attempt into
    `<tree>/.dbs/`, which is inside the tree and goes when the tree goes. Nothing
    outlives the directory, so `gc` genuinely has nothing to collect — the
    question is now purely one of what to *say*, which makes it cheaper than it
    looked and still not answered.

    Two smaller ones opened alongside it, and both are cosmetic rather than
    broken. `proto ls` prints a port and an up/down state for every prototype,
    and a terminal tree has neither — it is registered with the port `free_port`
    handed out and will always read as `down`. And `registry.record` allocates
    that port at all, which is one number out of a range nothing will bind. The
    honest fix for both is a registry that knows the target; the honest reason
    not to do it today is that neither misleads anybody into a wrong action.

  - **`auth: "password"` is accepted by the spec and implemented by no pass.** A
    spec can ask for it and nothing will build it. Either implement it or reject it
    at intake; silently accepting it is the worst of the three.
  - **`jobs` and `external_apis` are recorded and ignored.** Same shape of problem:
    the spec captures them, no pass consumes them.
  - ~~**The offline baseline ignores `spec.screens`.**~~ **Closed 2026-09-01** by
    Phase 2 of [Archetypes and Theme](implementations/spec/archetypes-and-theme.md).
    `baseline.pages()` treats `spec.screens` as authoritative and generates a
    route, a template and a smoke test for every custom screen. The bug had teeth:
    `checkable_paths()` handed such a path to the browser stage, which fetched a
    404 and reported the screen as broken.

  - **The web front end generates web prototypes only, and that is pinned rather
    than defaulted.** `protopilot/web/app.py::TARGET` is `"web"`. It used to take
    `targets.DEFAULT`, with the reason "no target picker yet" — a workaround, and
    the Phase 6 flip falsified it. The durable reason is that `proto serve` hands
    back a link you click, and a terminal app has no link.

    What is open is the half of the UI that would make a picker honest: a browser
    user choosing `tui` needs to be told a path and a command rather than shown a
    URL, and `job.url` is a single string that assumes otherwise. Small, and not
    worth doing until somebody wants it.

  - **The improvement loop comes after it**, and is not filed yet. The primitives
    arrived with the skeletor `agentic` tier — `scripts/reporting/jobs.py`,
    `run_ledger.py` with its two rails, `agent_runner.py`'s argv contract,
    `fix_policy` defaulting to `none`, `declined` as a first-class outcome. What
    is missing and is proto.pilot's own to design is the **ratchet**: an iteration
    must leave the tree at least as green as it found it or be reverted, which the
    per-tree `git init` already makes nearly free. Note the two loops are
    different: skeletor's tier maintains *this repo*; the ratchet governs
    *generated prototypes*. They share primitives, not a schedule.

- **2026-09-04 — the CI matrix went 3.11–3.14 → 3.11 + 3.14, measured rather
  than argued.** The question was whether four versions were worth maintaining.
  The record answered it: of eight failures on `develop` in the preceding window,
  four were a *single* red version, which is what a matrix is supposed to look
  like when it is earning its keep — but all four were the same timing-sensitive
  `test_console.py` races failing on whichever job lost, on a different version
  each time, and not one was a version incompatibility. Nothing in this repo
  branches on `sys.version_info`, so the interior was interpolation between two
  tested ends. Floor and ceiling kept: the floor is the only evidence for
  `requires-python = ">=3.11"`, and the ceiling is where new breakage arrives.

  The half worth keeping is the second change, not the first. The floor's
  rationale had been a *comment* in `ci.yml` since 2026-08-30 — "the floor of
  this list is the version the metadata is allowed to claim" — and with four
  entries that was slack enough to be hard to get wrong. With two, the floor job
  *is* the evidence, so `tests/test_python_support.py` now holds it to
  `pyproject.toml` and fails in both directions: raise the metadata and CI is
  proving something narrower than the claim; drop the floor from the matrix and
  the claim has lost its evidence. Three planted defects, three reds, plus a
  control (reordering the matrix) that stays green because the versions are
  compared numerically and not as strings — `"3.9" > "3.14"` is exactly the bug
  a floor check written the obvious way would have.

  **Trimming a matrix is a decision about one repo, not a general rule.** This
  one is safe to trim precisely because it has no version-conditional code; the
  note in `ci.yml` says to add a version back the moment that stops being true.

- **2026-09-04 — skeletor `v0.2.11` → `v0.3.6`, and the merged test that could
  not pass here.** Eight files: `scripts/yaml_text.py` and its two new suites,
  the `pp worktree drop` live-hold guard, `tree_lock.holders(root=...)`, and the
  YAML comment masker wired into `check_workflow_drift` and
  `test_ci_draft_gate`. That last pair is the finding worth keeping — both gates
  read a **comment** as code, so `# TODO: add actions/setup-python` satisfied the
  check that requires the step, and `# note: ready_for_review used to be here`
  kept five tests green over a deleted trigger. The false pass is perfectly
  correlated with the defect: the string most likely to appear in a job that has
  *not* done the thing is a comment saying it should.

  **`scripts/check_doc_tables.py` conflicted and we kept ours**, for the second
  upgrade running. Upstream merges file rows and folder rows into one
  `referenced()` set and needs a `_FOLDER_INDEX` suffix-strip to recover a
  folder from its README; ours splits `referenced()` (exact file paths) from
  `routed_dirs()` (folder-shaped rows, lookahead-guarded), so a folder's own
  README routes it **as a file, by exact path** and the lookahead never has to
  carry that case. Same rule, and skeletor agreed ours expresses it where it
  cannot be got wrong. Nothing was ported.

  **The seam defect was in a file we had never edited.**
  `tests/test_docs_pipeline.py` merged clean — no conflict, nothing to review —
  and arrived carrying a new test written against upstream's `referenced()`. It
  failed here immediately, which was the good outcome; a permissive version
  would have passed and asserted nothing. Re-pointed at `unrouted()`, the real
  consumer, which is where the three ways of routing a folder are actually
  combined and the only place that answers the question in either shape. **A
  clean merge is not a compatible one** when the merged file imports something
  you diverged on, and no conflict is raised because the divergence is a door
  away.

  Then two things caught by planting rather than by reading. The first `sed`
  plant silently matched nothing and the suite went green — a plant that did not
  land is indistinguishable from a gate that works, so the Python replacement
  now asserts its target exists before writing. And the fixture named
  `docs/TODO/widget-cache.md`, real upstream and dead here, which
  `pp check doc-refs` caught — then caught again in the comment written to
  explain the first catch. Both fixed with a real path; neither with a
  `.validate-ignore` entry, which is where a real path goes to stop being
  checked.

  Standing, unchanged: `tests/test_pyright_scope.py` stays deleted.

- **2026-11-05 — `tests/test_pyright_scope.py` is the template's again.** It
  adopted both of our pyright tests at skeletor v0.23.0 and adds a third, so our
  copies at the end of `test_lint_tool_parity.py` were duplicates. Restored at the
  v0.73.0 round, and the parity file and `pyrightconfig.json` were taken whole.
  This tree now has no deletions from the manifest.

- **2026-10-15 — `scripts/check_doc_tables.py` is the template's again, byte
  for byte.** The entry above kept ours for two rounds on the ground that the
  split API expressed the rule "where it cannot be got wrong". Checked against
  v0.51.2 rather than remembered: both versions carry the same two regexes with
  the same lookahead, both route a folder by its own README or its own path,
  and both stop the walk at a routed folder. The split protected nothing the
  template's `referenced()` + two-argument `unrouted()` does not, and it cost a
  conflict on every upgrade that touched the file plus a merged test that could
  not pass here. Two things the template does better: `unrouted()` returns the
  routed folders too, so the success line counts what the check reached rather
  than what `rglob` found on disk; and hidden directories are skipped.
  `tests/test_docs_pipeline.py` is the template's too now (hash matches the
  manifest), and `tests/test_doc_routing_predicate.py` — ours, not shipped
  upstream — is rewritten against the template's API and keeps the end-to-end
  row-to-walk case the template's own test does not ask. Nothing for skeletor
  to fix; that test file is adoptable as-is if they want `unrouted()` covered.
  Adopted at skeletor v0.55.0: the template's copy replaced ours and our six
  fixture entries in `scripts/doc_refs_allowlist.yaml` went with it, so both
  files now match the render.

- **2026-09-04 — the terminal target, all six phases, and `proto new` now
  builds one by default.** Filed at
  [docs/implementations/spec/terminal-target.md](implementations/spec/terminal-target.md) with per-phase
  landed notes; the go/no-go that gated it is
  [the 2026-09-04 report](reports/occasional/2026-09-04-terminal-target-go-no-go.md).

  `targets.DEFAULT` is `tui`; `Spec.target`'s field default is still `web` and
  always will be, because that one answers "what did a spec written before the
  axis mean". The web target is not demoted — same passes, same skeleton, same
  verifier, still generated in CI — because it is the only control for telling
  a target regression apart from a change regression.

  Four things worth knowing that are not in the plan. The archetype brief is a
  **fifth** thing a target owns beyond the four Phase 2 listed, because both
  shipped fragments are written in web down to "draw the pieces as inline SVG".
  The CLI needed five more medium facts from a target — `USES_PORT`, `HANDOFF`,
  `RUN_HINT`, `LOGS_LABEL`, `MANUAL` — every one of them a sentence that had
  been hardcoded and was true only of Docker. `textual` and `sqlalchemy` became
  runtime dependencies, because this target verifies in process and there is no
  container between proto.pilot and the tree it is checking. And the matrix is
  now four baselines: two archetypes against two targets, all four green in the
  unit suite with no key, no daemon and no browser.

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
  public — see [Branches in `CLAUDE.md`](../CLAUDE.md). The workspace table in
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
