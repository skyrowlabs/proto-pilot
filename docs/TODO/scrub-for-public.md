---
title: "Scrub for Public"
slug: scrub-for-public
shelf_status: blocked
priority: high
updated: 2026-11-24
tags: [publication, docs, release]
summary: "Remove personal traces and private-project context from the tracked tree, then hand the visibility flip to the maintainer; history is kept as it is."
---

# Scrub for Public

> **Status**: 🔴 Planned
> **Shelf-Status**: blocked
> **Blocked-On**: owner-ops
> **Priority**: High — the open-source release was decided on 2026-09-03 and this is the only thing between it and the flip
> **Updated**: 2026-11-24

> **For agentic workers:** execute task by task with superpowers:executing-plans
> or superpowers:subagent-driven-development. `blocked`, not `ready`, only
> because Task 5 holds two `(~operator)` steps; Tasks 1–4 can run now.

**Goal:** the tracked tree on `develop` names no private project and carries no
personal trace, so the repository can be made public as it is.

**Architecture:** documentation and metadata edits only. One untracked local
check finds the hits; each task clears one class of them and commits. No
product code changes behaviour.

## Problem

The repository is private and ships as open source the way skeletor does: public,
issues open, no launch and no support promise. Today's tracked tree is not fit to
show strangers:

- **Personal traces.** Docs attribute decisions to the maintainer by name, and
  may carry paths or machine details the publication gate does not catch.
- **Private context.** About eighty files name sibling projects that are not
  public, and some docs (rulings, run logs, working reports) only make sense with
  that context.
- **A stale description.** "A framework for prototyping ideas with agents" still
  names the layer removed on 2026-11-11, in `scripts/repo_settings.py:21` (which
  `pp settings` pushes to GitHub) and `cli/__init__.py:102` (the `pp --help` line).

## Approach

Scrub the **current tree only**. Commit history and the four tags stay, so every
`proto-pilot@<sha>` reference elsewhere keeps resolving. **Accepted trade-off:**
old commits still hold the earlier wording; anyone reading `git log -p` can find
it. If that ever becomes unacceptable, the fallback is a fresh history, which
breaks those references.

## Global Constraints

- **The private-name list never enters this tree** — a tracked list would be the
  leak (`tests/test_publication.py` states the rule). It lives outside the repo.
- Public repos may be named: **skeletor, sky.boss**, and skyrowlabs.com. Every
  other sibling project is private and may not be.
- The GitHub handle in `.github/CODEOWNERS` stays: it is already public and the
  file does not work without it. The `LICENSE` holder (the company) stays.
- `.skeletor.json` is not edited; it is skeletor's record of the scaffold and its
  upgrades three-way merge against it.
- History is not rewritten. No force-push.
- Commits follow `docs/rules/commits.md`; body 10 lines or fewer.
- `pp settings --apply` and the visibility change are the maintainer's alone.

## Review Focus

1. **A private name in a form the check misses** — a slug (`kebab-case`), a
   module (`snake_case`), a command word, or a relative link (`../<slug>/`).
   The check must search all forms; Task 1 builds it that way.
2. **A reworded passage that no longer makes sense** — "another project" in a
  sentence whose point was which project. Delete such a passage rather than
  leave a riddle.
3. **Private context in non-Markdown files** — `tests/fixtures/*.jsonl`, YAML,
  JSON indexes, Python comments and docstrings. The check runs over
  `git ls-files`, not `docs/`.
4. **A generated file edited by hand** — `docs/TODO/README.md`,
  `docs/todo_index.json`, `docs/implementation_index.json` and report indexes
  are rebuilt. Fix the source and regenerate (`pp check docs` says which).
5. **A broken link after a delete** — `pp check doc-links` and `doc-refs`
  must stay green after Task 4.

---

### Task 1: Inventory

**Files:**
- Create (outside the repo): `~/.config/proto-pilot/private-names.txt`, one
  pattern per line, every form of the maintainer's name and each private
  project's wordmark, slug, module and command
- Create (outside the repo): `~/.config/proto-pilot/scrub-check.sh`
- Produces: `scrub-check.sh` prints `path:line:match` per hit and exits 1 on any
  hit, 0 on none. Later tasks re-run it.

- [ ] Write `scrub-check.sh`: `git ls-files -z | xargs -0 grep -n -i -I -E -f ~/.config/proto-pilot/private-names.txt`, inverted exit status
- [ ] Run it; save the output to `~/.config/proto-pilot/hits-before.txt`. Expected: roughly 80 files
- [ ] Run `./pp test unit -k publication`. Expected: PASS; record any failure as a Task 2 item
- [ ] Sort the hit files into Task 2 (personal), Task 3 (reword) and Task 4 (delete). Nothing is committed in this task

### Task 2: Personal traces and the stale description

**Files:**
- Modify: every file Task 1 sorted here
- Modify: `scripts/repo_settings.py:21`, `cli/__init__.py:102`

- [ ] Replace each attributed ruling with an unattributed decision, keeping the date: "<name> ruled on 2026-11-11 that…" becomes "Decided 2026-11-11: …"
- [ ] Set `DESCRIPTION` and the `pp` docstring to one line describing the planning tool, matching the README's opening sentence
- [ ] Run `scrub-check.sh`. Expected: no hit for the maintainer's name
- [ ] Run `./pp check pre-push`. Expected: green
- [ ] Commit: `docs: drop personal attribution and the prototyping tagline`

### Task 3: Reword private-project mentions

**Files:**
- Modify: every file Task 1 sorted here, across `docs/`, `tests/`, `protopilot/`, `scripts/`

- [ ] Replace each mention with a generic term ("another project", "a sibling repository", "an example idea") where the sentence still teaches something
- [ ] Where a worked example or fixture is built around a private project's idea, change the idea to a neutral one only if the test asserts nothing about its wording; otherwise move the file to Task 4
- [ ] Regenerate any index the edits touch, using the command `pp check docs` names
- [ ] Run `scrub-check.sh`. Expected: hits only in files sorted to Task 4
- [ ] Run `./pp check pre-push`. Expected: green
- [ ] Commit: `docs: generalise mentions of private sibling projects`

### Task 4: Delete what only makes sense privately

**Files:**
- Delete: files Task 1 sorted here. Candidates to read first: `docs/reports/`, run logs inside `docs/TODO/living-plans.md`, `docs/ideas/hosted.md`, `tests/fixtures/`

- [ ] Delete whole files with `git rm`; cut passages in place. A filed plan in `docs/implementations/` is edited, never removed, so the archive keeps its shape
- [ ] Fix every link the deletes broke
- [ ] Confirm `git check-ignore tmp prototypes` prints both
- [ ] Run `scrub-check.sh`. Expected: exit 0, no output
- [ ] Run `./pp check pre-push` and `./pp test unit`. Expected: green
- [ ] Commit: `docs: remove private working material before publication`

### Task 5: Verify and hand over the flip

- [ ] Run `pre-commit run gitleaks --all-files` and a full-history scan (`gitleaks git --log-opts=--all`). Expected: no findings. A finding in history stops this plan and goes to the maintainer: it is the one case for a fresh history
- [ ] Push `develop` (standing rule: commit under the gates, then push)
- [ ] Raise one DECISIONS row in the sky.boss deck for the two operator steps below
- [ ] Apply the new description with `./pp settings --apply` (~operator)
- [ ] Make the repository public (~operator)
- [ ] After the flip, update the company workspace's project brief and repos table to read public; one commit in that repo (~deferred)

## Acceptance

- [ ] `scrub-check.sh` exits 0 over `git ls-files`
- [ ] `./pp test unit` passes, including `tests/test_publication.py`
- [ ] `./pp check pre-push` is green
- [ ] The full-history gitleaks scan reports no findings
- [ ] `gh repo view skyrowlabs/proto-pilot --json visibility,description` reads `PUBLIC` and the new description (~operator)

## Dropped, and why

- **A fresh history.** It hides the old wording, but it breaks every cross-repo SHA reference and all four tags. Held in reserve, only if the history scan turns up something that cannot stay.
- **Flip with no scrub.** Rejected by the maintainer: personal traces and private context go first.
- **A tracked deny-list of private names as a test.** It would publish exactly what it guards.
- **Editing `.skeletor.json`'s stale description.** It is the scaffold's merge base; a wrong value there costs nothing in public and a broken upgrade costs a round.
