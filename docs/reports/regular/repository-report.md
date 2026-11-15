---
commit_range: v0.3.0..HEAD
generated: "2026-11-15T04:01:57Z"
previous_release: v0.3.0
release: unreleased
status: in-flight
---

# Repository Report

> **Window:** unreleased (since v0.3.0) — `v0.3.0..HEAD` (81 commits, at `97c4fb3`)

Nothing in this window is in production. All of it is on `develop` and waits for
the release after v0.3.0. That release will remove fourteen commands (`bb5058b`).

## Metrics

| Figure | Value |
| ------ | ----- |
| Commits | 81 |
| By type | docs 22 · chore 15 · fix 13 · test 5 · feat 5 · build 1 · refactor 1 (the other 19 have no conventional type: merge commits) |
| Captures this job filed and still open (`finding_count`) | 0 |
| Holding tank | 1 plan, `planned`; ready queue empty; nothing awaiting review |

Most-changed files, by number of commits touching them:
`docs/todo_index.json` 16, `.skeletor.json` 13, `docs/ARCHITECTURE.md` 11; then 8
each for `docs/assets/skeletor-version.svg`, `docs/CLI.md` and
`docs/TODO/remove-prototyping.md`; then 7 each for `protopilot/plan/pipeline.py`
and `docs/TODO/plan-prototypes.md`; then 6 each for `AGENTS.md`,
`scripts/reporting/jobs.py`, `protopilot/cli.py` and `README.md`. The collected
data has no line counts, coverage or test results, so this report gives none.

## What changed

The window finished two plans:
[Plan Prototypes and Dreaming](../../implementations/spec/plan-prototypes.md)
(`29631a0`) and
[Remove Prototyping](../../implementations/spec/remove-prototyping.md) (`9c8acba`).

**Prototyping removed (`protopilot/`, `pyproject.toml`)** — merged in `bd35ef6`
- `bb5058b` (`feat(cli)!`) deletes the generator, both targets, both front ends,
  the skeleton and their tests. `proto new`, `add`, `spec`, `up`, `down`, `reset`,
  `logs`, `test`, `export`, `gc`, `console`, `serve`, `archetypes` and `targets`
  are gone. The surviving verbs are listed at `protopilot/cli.py:5`. The tag
  `prototyping-final` holds the last tree that has them.
- Old registry rows are kept, listed as `old`, and dropped only by `proto prune`
  (`protopilot/registry.py:26-32`, `:181`). `proto rm` refuses them
  (`protopilot/cli.py:28-30`).
- `4512671` drops the dependencies that only generated apps used: sqlalchemy,
  textual, and the browser and web extras. `86249a7` moves `PLAN_DIR`, `SLUG_RE`
  and `VerifyResult` into `protopilot/plan`, with no change in behaviour.
- Tests: `a4e58a6` covers what the removal left untested. `334ae77` and `a4e58a6`
  re-record the coverage baseline over the code that remains.
- The two prototype designs went to `docs/implementations/dropped/` (`6f3eded`).
  README and docs now describe planning as the whole product (`ad93437`).

**Research: the call (`protopilot/llm.py`)**
- The research call joined the `LLM` protocol (`protopilot/llm.py:63`). The CLI
  backend allows web tools only (`:253`) — `fa439ef`. The API backend refuses it
  with a message (`:172-174`).
- A stream is refused if its init event is missing or lists anything other than
  the research tools (`6e7e529`), or if the session used a tool that is not a web
  tool (`c66db5e`); see `research_result`, `:293-319`.

**Research: the pass and the ledger (`protopilot/plan/`)**
- `bb62291` makes one call per topic, resumable from `.protopilot/research/`. Its
  ledger of fetches feeds `sources.md` and the verifier. `97f01b8` gives `connect`,
  `consider` and `start` the findings.
- Fixes: the research state of each topic is now rebuilt from its own transcript
  (`71206ba`); the pipeline guards a resume as well as the command (`a464aff`);
  findings past the depth's count are refused (`f07f350`); page-derived text is
  escaped (`a3022f4`, `59507c8`); sources are listed by number (`ff1d644`); dream
  verbs read the reconciled plan (`e930533`). Tests: `450225e`, `feeb62e`.

**Plans in the registry (`protopilot/registry.py`, `cli.py`)**
- `2c0dda7`: `proto ls` lists plan trees. `21fa97f`: a plan whose render is
  blocked after saving is still registered. `4d53ba8`: the registry guards kinds,
  slugs and unsafe roots, and serialises writers with `flock` (now
  `protopilot/registry.py:128`, unsafe-delete guard `:210-211`). The console and
  app-verb changes in `39f9168`, `c6e2a97` and `969342e` were deleted by `bb5058b`.

**Planning docs**
- `247f4ae` adds the [living-plans](../../TODO/living-plans.md) spec. `2c21368`
  and `c95170d` record the owner's rulings on its open questions.

**Skeletor (`.skeletor.json` v0.81.1 → v0.88.0)** — twelve upgrades: `a03f0de`,
`78825df`, `1640d0e`, `73d51ab`, `e3751fa`, `2e17f22`, `9529342`/`8fa9b2b`,
`3f55fbf`, `8ed46ed`, `6291350`, `cc531c0`.
- The v0.88.0 apply conflicted in `tests/cli_smoke_allowlist.yaml` and was ported
  by hand. `bb9e0eb` then recorded v0.88.0 as the base.
- `e3751fa` (v0.81.7) adds the skeletor version badge
  (`docs/assets/skeletor-version.svg`).
- From the v0.81.x upgrades, still true at HEAD: report runs that exit 0 without
  a commit are recorded as failed. Coverage data lives at `tmp/.coverage`.

**Reporting (`scripts/reporting/jobs.py`)**
- `f0761d9` adds this job to `AUTO_PUSH` (`scripts/reporting/jobs.py:379`). Its
  report commit is now published through an auto-merging pull request.

## Risks

1. **The next release breaks every v0.3.0 user of the app verbs.** Fourteen
   commands are removed outright (`bb5058b`). `protopilot/cli.py` has no message
   for a removed verb; the only notice is `OLD_ROWS` (`:29`), which `proto ls`
   prints. Their registry rows survive as `old`
   (`protopilot/registry.py:32`). The 0.3.0 registry test is ticked
   (`docs/implementations/spec/remove-prototyping.md:420`). The spec's last check,
   CI green on `develop` at the merge SHA, is still unticked (`:426`). **Not
   filed:** the release notes are the release skill's job, and that check is an
   observation, not work.
2. **This report now lands on `develop` without a person reading it**
   (`scripts/reporting/jobs.py:379`). A wrong figure or a stale `path:line` would
   be merged by the runner, not caught at review. The gate below does not catch
   this either (risk 5).
3. **The research pass has been run live once:** the bakery idea at
   `--depth shallow` on `claude-code`
   (`docs/implementations/spec/plan-prototypes.md:236`). Every other test pins
   behaviour against fakes. `standard` and `deep` have no live run on record.
   **Not filed:** judging a run is a person's reading, not a task.
4. **Whether a fetch is "usable" is a guess built on an undocumented CLI field.**
   The ledger reads `code` and `bytes` from `tool_use_result`
   (`protopilot/plan/ledger.py:66`, `:95`) only when a message holds one result
   (`:97`), plus text patterns (`:32-43`). If the Claude CLI changes its stream
   shape, fetches will be misjudged and nothing will fail loudly. **Not filed:**
   only a live call tests this, and this job cannot write acceptance criteria that
   pass without network access.
5. **The anchor check still does not see a stale window or a stale body.**
   `check()` (`scripts/docs/release_window.py:177-199`) checks that the fields and
   the Window line exist, not that they match `git`. Still true at `97c4fb3`. The
   code is template-owned, so the fix belongs in skeletor. **Not filed.** This
   run did not check skeletor's current template for the same gap.
6. **On the API backend, every plan comes out Not researched**
   (`protopilot/llm.py:172-174`). API research is still deferred
   (`docs/implementations/spec/plan-prototypes.md:144`, `:217`). This is intended,
   but the two backends make different products.

## What is unfinished

1. [Living Plans](../../TODO/living-plans.md) — `planned`, not ready, 28 open
   tasks. Its Phase 1 is a person's reading, and the findings may reorder the rest
   (`docs/TODO/living-plans.md:19-20`).

Deferred items from the filed plans that are not in the tank: API research
(`docs/implementations/spec/plan-prototypes.md:144`, `:217`) and the CI check
after the removal merged (`docs/implementations/spec/remove-prototyping.md:426`).
The deferred `proto new --from-plan` (`plan-prototypes.md:255`) and the
Improvement Loop handoff (`:257`) both depended on prototyping, so the removal
made them moot. My reading, not a ruling: Living Plans' handoff brief is the
nearest thing to a replacement.
