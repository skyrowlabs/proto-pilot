---
commit_range: v0.3.0..HEAD
generated: "2026-11-07T22:00:37Z"
previous_release: v0.3.0
release: unreleased
status: in-flight
---

# Repository Report

> **Window:** unreleased (since v0.3.0) — `v0.3.0..HEAD` (1 commits, at `e5a33c1`)



> This edition closes the window for the next release, expected to be **v0.3.0**
> (Release Please picks the version; nothing in the tree fixes it). It records what
> that build contained: `v0.2.1..62ad9b8`. Nothing in it was in production before
> that release.

## Metrics

| Figure | Value |
| ------ | ----- |
| Commits | 75 |
| By type | docs 14 · chore 14 · fix 12 · feat 10 · test 8 (the other 17 subjects were untyped merge commits) |
| Captures this job filed and still open (`finding_count`) | 0 |
| Holding tank | 3 plans: 1 ready, 2 blocked; ready queue `plan-prototypes`; nothing awaiting review |

Most-changed files, by number of commits touching them:
`protopilot/plan/pipeline.py` 12, `protopilot/cli.py` 11; then 8 each for
`README.md`, `protopilot/plan/render.py`, `docs/TODO/plan-prototypes.md` and
`.skeletor.json`; then 7 each for `protopilot/plan/model.py`, `docs/todo_index.json`
and `tests/test_plan_pipeline.py`. The collected data had no line counts, coverage
or test results, so this report gives none.

## What changed

The window was the product pivot. `proto plan` was built through Phases 2–5 of
[Plan Prototypes and Dreaming](../../implementations/spec/plan-prototypes.md), the README was
rewritten to lead with planning, and skeletor was upgraded from v0.72.2 to v0.81.1.
Unlike the v0.2.1 window, most of the churn was in `protopilot/`, the product package.

**The pivot (docs)**
- Planning became the product and generating prototypes was tabled, in
  [plans-first](../../ideas/plans-first.md) — `d3c116a`. The plan for the work was
  drafted, its six decisions ruled and Phase 1 (a measured research call on the CLI
  backend) recorded — `1c2d365`, `c715a28`, `89cf722`.

**Phase 2: model, offline baseline, renderer (`protopilot/plan/`)**
- `model.py`, `baseline.py` and `render.py` arrived with `proto plan --offline`,
  which wrote a byte-stable plan tree with no model calls — `3712c5c`.
- Hardening: a plan for a different idea in an existing directory was refused
  (`0ba56d5`); render order, stale-page sweep, slugs and citations were fixed
  (`1d171d2`); `PLAN.md` was written last, so its presence meant every page was
  written (`7bc303f`). Tests: `ac8e3de`.

**Phase 3: the passes and the outline checkpoint (`protopilot/plan/passes/`)**
- `scope`, `outline`, `connect`, `consider` and `start` passes — `beeb926`. They ran
  behind an outline review (add, drop, rename, or `--yes`) and `--depth
  shallow|standard|deep` — `5b152c7`, `02d6b4e`.
- Saves became atomic, and a plan appearing mid-run was refused (`63c51a1`); `start`
  was offered every topic (`4e5d274`); a blocked page was named instead of
  surfacing a raw `OSError` (`3b6a886`). Tests: `2015123`.

**Phase 4: verifier and repair (`protopilot/plan/verify.py`, `passes/repair.py`)**
- One named check per bullet of *What "verified" means* — `b66bc9e`. A red plan was
  repaired a bounded number of times, editing `plan.json` only, and what stayed red
  was handed back — `512bc9d`.
- A repair was judged against the plan it started from (`33cb511`); the floor stayed
  honest and writes stayed inside the tree (`809ddab`); a repair reported what it did
  to step text and how to retry offline (`897f37e`). Tests: `4cbed2c`.

**Phase 5: dreaming (`protopilot/plan/dreaming.py`, `lenses.py`, `passes/{collect,evaluate,propose,promote}.py`)**
- Dream scores and a word cap (`e9563e5`); dreaming ran as a plan was made, and a
  failed round did not cost the plan (`0c67a10`); `proto dream`, `proto dream promote`
  and `proto dream drop --why` were added (`3edee0c`).
- `2f14a0b` kept a dream round from costing a plan in repair too, made a dream verb
  check for blocked pages first and roll the tree back if a write died, and held each
  field to its word budget on the API backend. Tests: `3da80a8`, `b03cc00`,
  `d2265af`, `cd3e3c1`.

**Model backends (`protopilot/llm.py`)**
- The API backend moved each schema `pattern` into a description, because the
  Messages API does not take the keyword (`protopilot/llm.py:61`, used at `:150`) —
  `7726beb`.

**CLI and README**
- `proto --help` led with planning — `bbcedc4`.
- The README led with planning and moved prototyping to a later section (`35fb458`),
  and described the model-backed run, verification and dreaming as built (`88d09b7`,
  `5bbc527`, `4df781c`, `5a15095`). It stated at `README.md:201` that nothing was
  researched and every plan was stamped **Not researched**; that held for this build.

**Skeletor (`.skeletor.json` v0.72.2 → v0.81.1)**
- Seven upgrade commits and two merge rounds: actionlint joined `check lint`
  (`a8212ef`); modules declared smoke execution (`77ec281`); product gates got
  `scripts/gates.py` (`6b61f13`); every check got an exit contract and a bare exit 3
  stopped passing (`14d1697`, `9fd5dab`); the divergence record arrived (`29ddee5`);
  the `check.py` conflict was ported (`291bb89`); v0.81.1 landed (`cde97be`,
  `a42c73b`, `63ebc6b`). `557ba68` restored the template's `test_pyright_scope.py`.

**Skeleton dependencies (`skeleton/web/`)**
- pytest 8.3.4 → 9.0.3, jinja2 3.1.5 → 3.1.6 and a python-multipart bump
  (`391cc73`, `34c83eb`, `8476f95`), with the web golden manifests updated to match
  (`2cc6946`).

**Not in this window**
- Research (Phase 6) was not in the build: its commits were on a feature branch,
  not on `develop` at `62ad9b8`.

## Risks

1. **The dream lenses have never been judged on a real idea.** Phase 5 shipped with
   its one hand check open (`docs/TODO/plan-prototypes.md:204`): whether the lenses
   produce different dreams and whether `evaluate` separates them. The tests pin
   shape, caps and failure handling against `tests/fakes.py`, not the quality of
   what a model returns. **Not filed:** it is marked `~operator`, a person's
   reading, so no task drainer can close it.
2. **On the API backend, `pattern` constraints were requests, not rules.**
   `_without_patterns` (`protopilot/llm.py:61`) turned every `pattern` into a
   sentence, so the server no longer rejected a field that broke one; the code's
   own comment says the caller's check is what holds. The CLI backend still
   enforced them. The API side of `proto plan` was covered by `tests/test_llm.py`
   with a stubbed client; Phase 1's API measurement was deferred for lack of API
   credit (`docs/TODO/plan-prototypes.md:144`), and nothing in the tree records a
   live API run of `proto plan`.
3. **The report-anchor check did not notice a stale window.** At v0.2.1 this
   report still said `v0.2.0..HEAD` and `pp check reports` passed, because
   `check()` (`scripts/docs/release_window.py:177`) checks that the anchor fields
   are present and that `status` is `in-flight` (`:193`, `:196`), and never compares
   `previous_release` with the newest tag. The same gap let v0.2.1 ship without
   freezing an edition (see Errata). The code is the template's, so a fix belongs
   in skeletor; nothing is filed here.

## What is unfinished

In queue order:

1. 🟢 Ready — [Plan Prototypes and Dreaming](../../implementations/spec/plan-prototypes.md), high
   priority, last updated 2026-11-06. Open at `62ad9b8`: Phase 6, research
   (`docs/TODO/plan-prototypes.md:207`); Phase 7, the surfaces that assume an app
   (`:217`), including `proto ls` showing plans and `proto rm` removing a plan
   tree; the API research measurement (`:144`); the Phase 5 hand check (`:204`);
   and every acceptance item (`:250`).
2. ⛔ Blocked (product decision) — [The Improvement Loop](../../TODO/improvement-loop.md),
   low priority, tabled 2026-11-06 with prototyping.
3. ⛔ Blocked (product decision) — [Drawing Freedom](../../TODO/drawing-freedom.md),
   low priority, tabled 2026-11-06 with prototyping.

## Errata

**v0.2.1 has no frozen edition.** `docs/reports/releases/` holds only `v0.2.0/`.
When v0.2.1 was tagged (`1d2ea3e`, 2026-11-04), the in-flight edition (last
refreshed in `1c1a6db`) was still anchored at `v0.2.0..HEAD`. No freeze ran, and
the report was not re-anchored until this edition. The v0.2.1 window was
`v0.2.0..v0.2.1`, 59 commits (`python scripts/docs/release_window.py --release v0.2.1`).
No report described that range. The nearest, committed in `1c1a6db`, covered 23
commits up to `b4545f3`; the 35 commits from `1c1a6db` to the tag were never
reported.
