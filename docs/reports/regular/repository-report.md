---
commit_range: v0.3.0..HEAD
generated: "2026-11-08T17:39:36Z"
previous_release: v0.3.0
release: unreleased
status: in-flight
---

# Repository Report

> **Window:** unreleased (since v0.3.0) — `v0.3.0..HEAD` (46 commits, at `fffbad1`)





Nothing in this window is in production. All of it is on `develop` and waits for
the release after v0.3.0.

## Metrics

| Figure | Value |
| ------ | ----- |
| Commits | 46 |
| By type | docs 15 · fix 13 · feat 4 · chore 3 · test 3 (the other 8 are merge commits) |
| Captures this job filed and still open (`finding_count`) | 0 |
| Holding tank | 2 plans, both blocked; ready queue empty; nothing awaiting review |

Most-changed files, by number of commits touching them:
`docs/ARCHITECTURE.md` 8, `docs/TODO/plan-prototypes.md` 7,
`protopilot/plan/pipeline.py` 6; then 5 each for `protopilot/cli.py`,
`docs/todo_index.json` and `docs/CLI.md`; then 4 each for `AGENTS.md`, `README.md`
and `protopilot/plan/render.py`; then 3 each for `.skeletor.json`, this report and
`protopilot/llm.py`. The collected data has no line counts, coverage or test
results, so this report gives none.

## What changed

The window finished [Plan Prototypes and Dreaming](../../implementations/spec/plan-prototypes.md).
Phase 6 (research) and Phase 7 (the surfaces that assume an app) landed, and the
plan was filed to `docs/implementations/` (`29631a0`).

**Research: the call (`protopilot/llm.py`)**
- The research call joined the `LLM` protocol (`protopilot/llm.py:63`). The CLI
  backend allows web tools only, on `stream-json` (`:413`) — `fa439ef`. The API
  backend refuses it in a sentence (`:172`).
- A stream is refused if any init event lists no tools (`6e7e529`) or the session
  used any tool that is not a web tool (`c66db5e`); see `research_result`, `:293`.

**Research: the pass and the ledger (`protopilot/plan/`)**
- `bb62291` added one call per topic, resumable from `.protopilot/research/`, with
  a ledger of fetches feeding `sources.md` and the verifier. `97f01b8` gave
  `connect`, `consider` and `start` the findings.
- Fixes: the research state of each topic is now redrawn from its own transcript
  (`71206ba`, `protopilot/plan/ledger.py:11-13`); a resume is guarded in the
  pipeline as well as the command (`a464aff`); findings past the depth's count are
  refused (`f07f350`); page-derived text is escaped (`a3022f4`, `59507c8`); sources
  are listed by number (`ff1d644`); dream verbs read the reconciled plan
  (`e930533`, `protopilot/plan/pipeline.py:628`). Tests: `450225e`, `feeb62e`.

**Plans as registry entries (`protopilot/registry.py`, `cli.py`, `web/`)**
- `2c0dda7`: `proto ls` lists plan trees, and the app verbs refuse a plan.
  `c6e2a97`: `down --all` says that it stops apps and never plans. `21fa97f`: a
  plan whose render is blocked after saving still gets registered.
- `4d53ba8`: the registry guards kinds, slugs and unsafe roots, and serialises
  writers with `flock` (`protopilot/registry.py:112-126`).
- `39f9168`: the console asks the tree what kind it is before it touches Docker or
  delete. Confirm text moved out of inline script, so a quote in a name cannot run.
  Tests: `969342e`, `tests/test_web_asks_the_tree.py`.

**Docs**
- README, `docs/CLI.md` and `docs/ARCHITECTURE.md` now describe plans as the
  product and say how app verbs treat a plan (`c82f3c3`, `a4e7a85`, `2424bda`).
  The operator's reads of the dreams and of a researched run are recorded
  (`db442ec`, `ba3fc68`). `NOTES.md` moved into `docs/` (`e98c4cd`). The previous
  edition of this report is `1903427`.

**Skeletor (`.skeletor.json` v0.81.1 → v0.81.5)** — `a03f0de` (v0.81.2), `78825df`
(v0.81.4), `1640d0e` (v0.81.5).
- Report-writing runs that exit 0 without a commit are now recorded as failed, and
  the reason names any refused tools (`scripts/reporting/agent_runner.py:336`,
  `:351`, `:122`). `AGENT_TOOLS` can grant a job extra tools; it is empty here
  (`scripts/reporting/jobs.py:335`).
- Coverage's data file moved to `tmp/.coverage` (`pyproject.toml`,
  `[tool.coverage.run]`), and the budget check reads that location from coverage's
  own config (`scripts/check_coverage_budget.py:146`).

## Risks

1. **The research pass has been run live once.** The one recorded run is the
   bakery idea at `--depth shallow` on `claude-code`
   (`docs/implementations/spec/plan-prototypes.md:236`). Everything else pins
   behaviour against fakes. `standard` and `deep` depths have no live run on
   record. **Not filed:** judging a run is a person's reading, not a task.
2. **Fetch "usable" is a heuristic built on an undocumented CLI field.** The
   ledger reads `code` and `bytes` from the CLI's `tool_use_result`
   (`protopilot/plan/ledger.py:67`, `:96`), plus text patterns (`:34-43`). The
   metadata is used only when a message holds one tool result (`:98`). The spec
   says the field is not a documented contract. If the Claude CLI changes its
   stream shape, fetches will be misjudged and nothing fails loudly. **Not filed:**
   the only real test is a live call, and this job cannot write acceptance criteria
   for one that pass without network access.
3. **On the API backend, every plan comes out Not researched.** `ClaudeLLM.research`
   raises `ResearchUnavailable` (`protopilot/llm.py:172-174`). The API measurement is
   still deferred for lack of credit (`docs/implementations/spec/plan-prototypes.md:144`,
   `:217`). This is intended behaviour, but it means the two backends now produce
   different products.
4. **The anchor check still does not see a stale window or a stale body.**
   `check()` (`scripts/docs/release_window.py:177-199`) checks that the fields and
   the Window line exist, not that they match `git`. Still true at `fffbad1`. The
   code comes from the template, so the fix belongs in skeletor, and this tree's
   queue would only produce an edit to a template-owned file. **Not filed.** This
   run did not check whether skeletor's current template has the same gap.

## What is unfinished

The ready queue is empty. Both plans in the tank are blocked:

1. ⛔ Blocked (product decision): [Drawing Freedom](../../TODO/drawing-freedom.md),
   low priority, tabled 2026-11-06 with prototyping.
2. ⛔ Blocked (product decision): [The Improvement Loop](../../TODO/improvement-loop.md),
   low priority, tabled 2026-11-06 with prototyping.

The filed plan's deferred items are not in the tank: API research
(`docs/implementations/spec/plan-prototypes.md:144`, `:217`), `proto new --from-plan`
(`:255`), and handing a plan to the Improvement Loop (`:257`).
