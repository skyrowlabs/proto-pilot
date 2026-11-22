---
commit_range: v0.3.0..HEAD
generated: "2026-11-22T04:01:42Z"
previous_release: v0.3.0
release: unreleased
status: in-flight
---

# Repository Report

> **Window:** unreleased (since v0.3.0) — `v0.3.0..HEAD` (89 commits, at `8b727f2`)

Nothing in this window is in production. All of it is on `develop` and waits for
the release after v0.3.0. That release removes fourteen commands (`bb5058b`) and
adds the brief flags to `proto plan` (`dbfd81b`).

## Metrics

| Figure | Value |
| ------ | ----- |
| Commits | 89 |
| By type | docs 27 · chore 15 · fix 13 · feat 7 · test 5 · build 1 · refactor 1 (the other 20 have no conventional type; `git log --merges` counts 20 merge commits) |
| Captures this job filed and still open (`finding_count`) | 0 |
| Holding tank | 1 plan, `planned`; ready queue empty; nothing awaiting review |

Most-changed files, by number of commits touching them:
`docs/todo_index.json` 16, `docs/ARCHITECTURE.md` 13, `.skeletor.json` 13,
`docs/CLI.md` 9; then 8 each for `docs/TODO/living-plans.md`,
`protopilot/plan/pipeline.py`, `docs/assets/skeletor-version.svg` and
`docs/TODO/remove-prototyping.md`; then 7 each for `AGENTS.md`, `README.md`,
`protopilot/cli.py` and `docs/TODO/plan-prototypes.md`. The collected data has no
line counts, coverage or test results, so this report gives none.

## What changed

The window finished two plans:
[Plan Prototypes and Dreaming](../../implementations/spec/plan-prototypes.md)
(`29631a0`) and
[Remove Prototyping](../../implementations/spec/remove-prototyping.md) (`9c8acba`).

**The brief (`protopilot/cli.py`, `protopilot/plan/`)** — new since the last edition
- `dbfd81b` adds `--goal`, `--for`, `--horizon`, `--must` and `--not` to
  `proto plan` (`protopilot/cli.py:173`, `:231`). With no idea at a terminal it
  asks for each in turn (`:117`).
- The brief is a model of its own (`protopilot/plan/model.py:109`). Scope fills
  only the blanks and puts each stated field back over what it returned
  (`protopilot/plan/passes/scope.py:88-96`).
- The brief is part of a plan's identity: a rerun with another brief is refused
  (`protopilot/plan/pipeline.py:84-86`, `:133`). An empty brief is left out of
  `plan.json` (`protopilot/plan/model.py:306`), so existing trees and the offline
  golden do not change. Tests: `tests/test_plan_brief.py`.

**Where to start (`protopilot/plan/passes/start.py`, `render.py`)** — new since the last edition
- `9ee1427` caps each step at 30 words of action and 25 of reason
  (`protopilot/plan/model.py:55`). The schema pattern applies only to a plan with
  no steps yet (`protopilot/plan/passes/start.py:55-64`). Repair asks for the cap
  in its prompt and does not enforce it. `PLAN.md` puts the reason on its own
  *Why here* line (`protopilot/plan/render.py:145`), so
  `tests/golden/plan_offline_manifest.json` was re-recorded.

**Worked example and dogfood runs (`docs/examples/`, `docs/TODO/living-plans.md`)** — new since the last edition
- `f3ecf83` commits a researched `--depth standard` run as the first worked
  example: [walkthrough](../../examples/squirrel-survival.md) and tree
  `docs/examples/squirrel_survival/`. Its research transcripts are left out
  because of #51. `d5af86f` and `9b11b1d` record what changed after that run.
- `8b727f2` records the Home Kitchen run as Run 1 (`docs/TODO/living-plans.md:130-148`).
  It filed #52, #53 and #54. Its tree is kept outside this repo.

**Prototyping removed (`protopilot/`, `pyproject.toml`)** — merged in `bd35ef6`
- `bb5058b` (`feat(cli)!`) deletes the generator, both targets, both front ends,
  the skeleton and their tests. `proto new`, `add`, `spec`, `up`, `down`, `reset`,
  `logs`, `test`, `export`, `gc`, `console`, `serve`, `archetypes` and `targets`
  are gone. The surviving verbs are listed at `protopilot/cli.py:3-6`. The tag
  `prototyping-final` holds the last tree that has them.
- Old registry rows are kept and listed as `old` (`protopilot/registry.py:32`).
  Only `proto prune` drops them (`:181`).
- `4512671` drops the dependencies only generated apps used. `86249a7` moves
  `PLAN_DIR`, `SLUG_RE` and `VerifyResult` into `protopilot/plan`. `a4e58a6`
  and `334ae77` add tests for what the removal left uncovered and re-record the
  coverage baseline. `6f3eded` and `ad93437` move the designs and docs over.

**Research (`protopilot/llm.py`, `protopilot/plan/`)**
- The research call joined the `LLM` protocol (`protopilot/llm.py:63`). The CLI
  backend allows only the web tools (`:254`), and the API backend refuses
  (`:172-174`), per `fa439ef`. `6e7e529` and `c66db5e` reject streams that used
  other tools (`research_result`, `:293`).
- `bb62291` makes one resumable call per topic. Its ledger feeds `sources.md`
  and the verifier. `97f01b8` passes the findings to `connect`, `consider` and
  `start`. The fixes are `71206ba`, `a464aff`, `f07f350`, `a3022f4`,
  `59507c8`, `ff1d644` and `e930533`, with tests in `450225e` and `feeb62e`.

**Plans in the registry (`protopilot/registry.py`, `cli.py`)**
- `2c0dda7` makes `proto ls` list plan trees, and `21fa97f` registers a plan whose
  render was blocked. `4d53ba8` adds the guards and `flock` writers
  (`protopilot/registry.py:128-141`, unsafe-delete guard `:210-211`).

**Skeletor (`.skeletor.json` v0.81.1 → v0.88.0)**: twelve upgrades, listed in the
previous edition. Nothing has changed since `97c4fb3`.

**Reporting (`scripts/reporting/jobs.py`)**: `f0761d9` puts this job in
`AUTO_PUSH` (`scripts/reporting/jobs.py:379`).

## Risks

1. **The next release breaks every v0.3.0 user of the app verbs.** Fourteen
   commands are removed outright (`bb5058b`). The only notice is `OLD_ROWS`
   (`protopilot/cli.py:37`), and only `proto ls` prints it (`:447`). The spec's
   CI-at-merge-SHA check is still unticked
   (`docs/implementations/spec/remove-prototyping.md:426`). **Not filed:** release
   notes belong to the release skill.
2. **`--not` is held by a prompt alone.** `scope.apply` merges the model's
   constraints without dropping any that restate an out-of-scope item
   (`protopilot/plan/passes/scope.py:96`). Five clean live samples are the only
   evidence (`docs/examples/squirrel-survival.md:119-126`). In Run 1 a dream
   contradicted a `--must` and was still proposed
   (`docs/TODO/living-plans.md:146-147`). **Not filed:** the walkthrough chose to
   leave it as a prompt fix, so adding a guard is a decision, not a task.
3. **The step cap holds only where the backend honours schema patterns.** It
   applies only to a plan with no steps, and repair only asks for it
   (`protopilot/plan/passes/start.py:55-64`, `protopilot/plan/passes/repair.py:44-46`).
   An over-long step still lands, which the commit says is intended (`9ee1427`).
4. **The committed example tree breaks if someone re-renders it in place.** It goes
   red at `sources_fetched` and exits 1, because its transcripts are absent
   (`docs/examples/squirrel-survival.md:154-158`). Only that prose warns against
   it.
5. **This report lands on `develop` without a person reading it**
   (`scripts/reporting/jobs.py:379`), and the anchor check
   (`scripts/docs/release_window.py:177-199`) still verifies only that the fields
   exist. It does not check that they match `git`. The check is template-owned.
   **Not filed:** the fix belongs in skeletor.
6. **Live research coverage is still thin.** There are three runs on record:
   bakery at `shallow` (`docs/implementations/spec/plan-prototypes.md:236`), and
   the squirrel and Home Kitchen runs at `standard`
   (`docs/TODO/living-plans.md:116-148`). All three used `claude-code`. `deep`
   has never been run live. The ledger still judges a fetch from undocumented CLI
   fields (`protopilot/plan/ledger.py:66`, `:95-97`). Run 1 had 8 unusable fetches
   (`docs/TODO/living-plans.md:140`). On the API backend every plan comes out
   *Not researched* (`protopilot/llm.py:172-174`). **Not filed:** these need live
   calls or a person's reading.

## What is unfinished

1. [Living Plans](../../TODO/living-plans.md) is `planned`, not ready, with 35
   unchecked boxes. Phase 1 has two agent-run records (Run 0 and Run 1), and
   neither counts toward the three operator runs. Both still have the
   operator's five lines open (`docs/TODO/living-plans.md:128`, `:148`).

Open outside the tank: GitHub issues #48, #49, #51, #52, #53 and #54. Two deferred
items from filed plans are also open: API research
(`docs/implementations/spec/plan-prototypes.md:144`, `:217`) and the CI check
after the removal (`docs/implementations/spec/remove-prototyping.md:426`).
