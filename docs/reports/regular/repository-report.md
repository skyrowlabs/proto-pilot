---
commit_range: v0.2.0..HEAD
generated: "2026-10-18T03:02:46Z"
previous_release: v0.2.0
release: unreleased
status: in-flight
---

# Repository Report

> **Window:** unreleased (since v0.2.0) — `v0.2.0..HEAD` (21 commits, at `fa374f1`)


> is in production; all of it ships with the next release.

## Metrics

| Figure | Value |
| ------ | ----- |
| Commits | 21 |
| By type | chore 17 · docs 2 · fix 1 · refactor 1 |
| Captures this job filed and still open (`finding_count`) | 0 |
| Holding tank | 2 plans: 1 planned, 1 blocked; ready queue empty, nothing awaiting review |

Most-changed files, by number of commits touching them: `.skeletor.json` 16,
`cli/_capture.py` 7, `cli/doctor.py` 5; then four commits each for
`scripts/check_coverage_budget.py`, `scripts/reporting/{agent_runner,jobs,shellout}.py`,
`tests/{conftest,test_doctor,test_env_example_parity,test_reporting_shellout}.py`.
The collected data has no line counts, coverage or test results, so this report
gives none.

## What changed

Sixteen of the 21 commits are skeletor upgrades (`.skeletor.json` v0.42.0 → v0.57.0).
**`protopilot/`, the product package, has no commits in this window** — every
change is to the CLI shell, CI, docs tooling or tests.

**CLI (`cli/`)**
- New `pp doctor` (`cli/doctor.py`) reads the repository's GitHub settings via
  `gh api` (`cli/doctor.py:61`): the default branch, the release-PR permission,
  required checks on both branches, back-merge state and CODEOWNERS.
  Commits: `5633850`, `f6662b1`, `264a809`, `bf1062b`, `324c035`.
- New `pp inbox` (`cli/inbox.py`) lists open captures in each lane — `5633850`, `f6662b1`.
- Capture filing (`cli/_capture.py`): `--source` attribution and a per-job cap on
  open captures (`416b64a`, `8b0cdb1`); a frozen release now leaves a record (`8bab345`);
  plus follow-ups in `5633850`, `f6662b1`, `eca84d0`, `34b4936`.
- `cli/report.py` keeps running when a tool is missing (`63cdc56`), and its
  release-freeze recording changed (`8bab345`). `cli/test_cmds.py` and
  `cli/worktree.py` changed in `b96111e`.

**CI (`.github/workflows/`)**
- The three "Install the project" steps (`ci.yml:525`, `ci.yml:610`,
  `coverage-nightly.yml:75`) now all run one script, `scripts/install_project.py`,
  the same one the setup block runs — `b96111e`. pyright 1.1.411 → 1.1.414 in the same commit.
- The commit-subject step (`ci.yml:177`) no longer skips repositories that have
  no Release Please config — `bf1062b`. Nothing changes for this tree, which has
  `.github/release-please-config.json`.

**Docs tooling**
- `scripts/check_doc_tables.py` now matches the template byte for byte, which drops
  the local `routed_dirs()` API — `ef14963`.
- `.github/scripts/.validate-ignore` is gone; its entries moved to
  `scripts/doc_refs_allowlist.yaml`, each with a reason — `bf1062b`.
- Quick Start / setup block: it now installs every extra (`ff1332f`, the window's
  only `fix`), installs clone-local config (`324c035`) and installs the project (`b96111e`).
  The setup-block budget now counts commands (`fa374f1`).

**Tests**
- Unit tests may reach loopback only — `eca84d0`. `tests/conftest.py` gains a
  frozen adopter rule and a check that covers imports — `34b4936`, `e69888e`.

**Reports**
- The v0.2.0 report window closed (`af32686`); the window that froze no reports is recorded (`8ac5800`).

## Risks

1. **CODEOWNERS requests no reviews, and that is true right now.** Running `./pp doctor`
   at `fa374f1` returns `❌ CODEOWNERS names owners GitHub recognises — 5 line(s)
   GitHub rejects`, starting at `.github/CODEOWNERS:8` (`@skyrowlabs`). The defect
   predates this window. What is new is that `pp doctor` makes it visible, and
   `.github/CODEOWNERS:3` carries the template's note on fixing it. **Not filed:**
   it needs a decision — which team or user owns the repository — that a task
   drainer cannot make. Done when `./pp doctor` shows the CODEOWNERS fact as ✅.
2. **`pp doctor` is checked only against its own fixtures.** Its tests swap out
   `gh_api` entirely (`tests/test_doctor.py:27`, `:33`), so they never see the
   response shapes the code assumes — `.get("secrets")` at `cli/doctor.py:98`,
   `can_approve_pull_request_reviews` at `cli/doctor.py:110`. If GitHub changes
   one of those fields, a fact reads wrong and every test still passes. Today's
   run against the real API returned 5 of 6 facts ✅, so the code matches
   GitHub at HEAD. The code is the template's, so any fix belongs in skeletor;
   none is filed here.
3. **One script now installs the project for three CI jobs and the setup block.**
   A defect in `scripts/install_project.py` would break `ci.yml:525`, `ci.yml:610`
   and the nightly `coverage-nightly.yml:75` together. Before `b96111e` each job
   ran its own inline copy. `tests/test_install_project.py` and
   `tests/test_setup_blocks_agree.py` cover the script; this session could not
   run them.

## What is unfinished

The ready queue is empty. In queue order:

1. 🔴 Planned — [The Improvement Loop](../../TODO/improvement-loop.md), high priority,
   last updated 2026-09-03.
2. ⛔ Blocked (needs a product decision) — [Drawing Freedom](../../TODO/drawing-freedom.md),
   high priority, last updated 2026-09-03. It waits on whether web stays a supported
   target (`docs/TODO/drawing-freedom.md:39`).
