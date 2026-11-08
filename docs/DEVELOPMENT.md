# Development Guide

## First-Time Setup

```bash
cp .env.example .env                                   # then fill it in
.venv/bin/pre-commit install --install-hooks           # commit-msg format + lint gates
.venv/bin/python scripts/git/install_merge_drivers.py  # clone-local config
./pp check health                                      # is everything answering?
```

**There is no `pp setup`, deliberately** — see `AGENTS.md`, which explains that
it could not exist: the CLI cannot run until the install it would be performing
has already put `click` in the venv, so a quick start that opens with it fails
on line one and reads as user error. This file named it anyway until 2026-09-03,
in its own first code block, which is the worst place in the repo to name a
command that is not there.

Two of those lines install things that are easy to miss because they live outside
version control:

- **Git hooks** (`pre-commit install --install-hooks`) — the commit-msg format
  check and the lint gates.
- **The clone-local config** (`scripts/git/install_merge_drivers.py`, the third
  line above) — the `regen-docs` merge driver and `commit.template`. Both live in
  `.git/config`, which is not tracked, so a clone that skipped that line has
  `.gitattributes` naming a driver that does not exist and a `check pre-push` that
  is red until it runs. Verify with `pp check merge-drivers`, which checks and
  never installs.
- **The pre-push hook** (`scripts/hooks/pre-push`, installed by that same script) —
  see [Pushing](#pushing). Git runs a copy under `.git/hooks`, so a changed hook needs
  the installer again, and `check pre-push` is red until it has run.

The block above is static text, and so are the install blocks in `README.md` and
`AGENTS.md`. They were generated from one source when this repository was
scaffolded, which is **not** a standing guarantee — a guarantee implemented by
rendering is spent at the moment of rendering, and the generator is not here.

What holds them together now is `tests/test_setup_blocks_agree.py`, which ratchets
on how many leading lines the install blocks agree on and fails when that number
drops. It enrols a block by looking for an install command in it, not by naming
documents, and **this file's block is deliberately not enrolled**: the rewrite
above moved the venv line out of it, so what is left are the steps that come
after the install. Two documents are measured here, not the three that test's
prose assumes. A shared step drifting between them is caught; a step drifting
between them and this file is not, so change all three by hand.

That last claim is present-tense about a mechanism, which is what the paragraph
before it says to distrust. It is honest for the one reason the warning turns on:
the test ships beside this file and runs in the same `pp check pre-push`, with no
rendering step between the claim and its enforcement.

## Pushing

A push to `develop` or `main` needs evidence that the pushed tree was
checked. Commit first, then run the gates, then push:

```bash
./pp check pre-push
git push
```

A full run on a checkout with nothing uncommitted stamps `HEAD^{tree}` under the git
common dir. The hook reads every ref in the push, and a protected one passes if the
pushed commit's tree is stamped or equals the fetched tip of either branch, which CI has
already seen. Otherwise it refuses and names the command. Other branches, tags and
deletes are not judged.

- **The stamp is per tree.** Rewording a commit keeps it. A merge or a pull that
  produces a new tree needs a fresh run, so every direct push pays for a full
  `check pre-push`.
- **`--quick` never stamps,** and a run with uncommitted changes says it did not.
- **`git push --no-verify` skips the hook.** Nothing records that it did.
- **An unattended job pushing to a protected branch is refused** until it runs the gates
  first.
- **The installer leaves a pre-push hook it did not write alone,** and `check pre-push`
  stays red until you remove it. To decline the hook, delete `scripts/hooks/pre-push` and
  `tests/test_green_stamp.py`.

## Configuration

Every value the application reads appears in `.env.example` with a comment. The
real `.env` is untracked, and a pre-commit hook refuses any `.env*` that is not
the example — a committed secret is a rotated secret.

Read config through the validated config object, never `os.getenv()` at the
point of use. Validation happens once at startup, so a misconfigured process
refuses to boot rather than failing on the first request that needs the value.

## The Gates

Every gate CI blocks on is runnable locally with the same invocation, **except
the integration suite**, which needs the stack up and so has no host equivalent.
That one exception is declared in `tests/test_pre_push_covers_ci.py`, which fails
when CI grows a blocking gate `pre-push` neither runs nor declares — the earlier
version of this sentence said "everything" and was wrong about three gates.

```bash
./pp check pre-push        # every host-runnable one, in fail-fastest order
./pp check pre-push --quick # no test suites; the rest still run
./pp check lint            # the blocking lint set
./pp check docs            # indexes, tables, links, refs, report anchors
```

Every gate runs even after one fails. One fix per round trip is the thing this
exists to avoid.

Your own gates go in `scripts/gates.py`, as an append to `DOCS_GATES` (run by
`check docs` and `check pre-push`) or `PRE_PUSH_GATES` (`check pre-push` alone).
Editing a list in `cli/check.py` instead conflicts with every
release that adds a gate there.

## Testing

Suites are selected by **marker**, and a test file joins a suite by declaring
one. There is no registry to update:

```python
pytestmark = [pytest.mark.unit]
```

```bash
./pp test unit             # host-side, no services
./pp test integration      # needs the stack up
./pp test all              # everything except `manual`
./pp test unit --ci        # reproduce CI's skip semantics locally
./pp test coverage -w 20   # the worst-covered modules — where a test buys most
./pp test coverage --suite unit --suite ui   # only these suites, budgeted as unit+ui
```

`--ci` sets `PP_CI=1`, under which an env-gate skip becomes a **failure**.
That is the difference between "the suite passed" and "the suite ran".

Full rules: [`docs/rules/testing.md`](rules/testing.md).

## CI/CD Pipeline

| Event                          | What runs                              | ~min |
| ------------------------------ | -------------------------------------- | ---- |
| Draft PR, docs-only            | `CI Gate` + `pytest`                   | ~4   |
| Draft PR carrying code         | `CI Gate` + `Node` + `pytest`          | ~5   |
| Ready PR → `develop`, docs-only | `CI Gate` + `pytest`          | ~4   |
| Ready PR → `develop`, code      | `CI Gate` + `Node` + `pytest` | ~5   |
| Ready PR → `main`, docs-only | `CI Gate` + `pytest`       | ~4   |
| Ready PR → `main`, code      | **everything**             | full |
| Ready PR opened by Dependabot  | **everything** — deliberately exempt   | full |
| Push to `develop` or `main` | **everything**, and Release Please on `main` | full |

Three things about this table are load-bearing:

1. **A required context that reports `skipped` satisfies branch protection** —
   under its real name. So gating is done with `if:` on the job, never
   `paths-ignore` on the trigger: a required check that never reports at all
   blocks the PR forever.

   **The unit suite is never gated, docs-only included**, because its tests
   read `docs/` — plans, tables, references — so a docs-only change is what
   they judge. It runs once per interpreter, as `pytest <version>`, and a
   skipped matrix reports one check with the expression unexpanded, so a
   protection requiring `pytest <version>` can wait forever.
   **Require `pytest`, never `pytest <version>`.** `pytest` is one job that
   `needs:` the matrix and always reports — pass when every leg passed, fail
   otherwise, including when the gate failed and nothing ran. A protection
   set up before that job existed names the per-version contexts; no file in
   this tree can change that setting, so check it.

   **Change it one branch at a time, and only once that branch carries the
   job.** A pull request runs the `ci.yml` of its merge commit, so a required
   context reaches it only if the base or the head has the job that reports it.
   Require `pytest` on a branch whose `ci.yml` predates it and every pull request
   into that branch from a branch cut from it — a hotfix, typically — waits
   forever on a check nothing will run. The release branch is the one that
   lags: it gets the job only when the base branch is next merged into it.
2. **Requiring a context costs nothing; only running a job does.** Size the
   required list for what must gate. Never trim it to save minutes.
3. **The Dependabot exemption is a mechanism, not a courtesy.** Auto-merge fires
   the moment branch protection is satisfied, so without the exemption every
   eligible bump merges having never run the suite it exists to be checked by.

### Dependency updates

`.github/dependabot.yml` proposes version updates monthly, each held back five
days (`cooldown`) so a hijacked release can be yanked before it is proposed.
`.github/workflows/dependabot-auto-merge.yml` merges a Dependabot pull request
once CI passes on it, using the GitHub App's token (`APP_ID`, `APP_PRIVATE_KEY`)
so the merge itself runs CI on the base branch. Patches and minors merge,
security updates included, and so does a major in a dev manifest
(`scripts/requirements.txt`, `requirements-dev*.txt`, `package.json`
devDependencies), because the suite running under it is the migration test. A
major anywhere else is runtime and is left for a person. The decision, and the
list of dev manifests to extend, is `.github/scripts/dependabot-hold.cjs`. Without the App's secrets it merges
nothing and says so in the run.

The lint tools (black, flake8, isort, pyright) are ignored there. Each is pinned
in two files and `tests/test_lint_tool_parity.py` is red until both agree, so a
bump to one of them could never merge. Bump those by hand, in both files.

## Releases

Versioning is Conventional Commits → Release Please. Commit types decide the
bump; `CHANGELOG.md` and `VERSION` are generated. **Never hand-edit either.**

**Known: a pull request merged with a merge commit lists its change twice.**
GitHub writes the PR title into the merge commit's body by default, and Release
Please reads that line as a second commit (sky.vault, v0.2.0 and v0.3.0). The
template leaves merge settings to you: squash merges, or PR titles with a hidden
type such as `chore:`, avoid it. Measured on one tree only.

The release lands on `main`, so back-merge it. Until you do,
`develop` does not contain the release commit, and `git describe` there
names the release before this one (mind.head):

```bash
git fetch origin && git switch develop && git merge --ff-only origin/main && git push
```

A fast-forward, because a merge commit is a commit no check has run on, and a
`develop` with required checks takes it only by admin bypass (sky.vault).
After a promote `develop` is normally an ancestor of `main`,
so the fast-forward gives the same tree. If git refuses, `develop` has moved
since: open the back-merge as a pull request from `main` and merge it
with a merge commit, so it runs the checks and keeps the release commit an ancestor.

A release closes the report window: in-flight reports under
`docs/reports/regular/` freeze into `docs/reports/releases/<tag>/`. See
[`docs/rules/docs.md`](rules/docs.md).

## Command Output

Every command splits its output the same way: **stdout is what a caller
consumes** (a `--json` payload, a generated block, a listing you may pipe) and
**stderr is what only a human reads** (status lines, progress, and the "what to
do next" under an error).

Both land on your terminal, so an interactive run looks the same either way. The
difference appears the moment you pipe one:

```bash
python scripts/check_doc_tables.py --json | jq        # payload only
./pp check docs 2>/dev/null                        # silent: it is all narration
```

Every `scripts/check_*.py` supports `--json` and answers on **every** path,
including the ones that pass — a ratchet you can only read when it is red says
nothing about which way it has been moving.

Nothing spells a status symbol or picks a stream by hand; it all comes from
`scripts/output.py`, and `pp check output` enforces that by pattern.
Full rules: [`docs/rules/output.md`](rules/output.md).

## Reproducing a CI Failure Locally

```bash
./pp check lint                        # 1. fastest feedback; catches most CI rejections
./pp test unit --ci                    # 2. CI's skip semantics
PP_PYTHON=.venv-ci/bin/python ./pp check pre-push   # 3. CI's exact interpreter
```

Step 3 matters more than it looks. A local venv that has drifted from CI's
pinned interpreter produces failures that exist in one environment and not the
other, and the tool names are identical, so the version never occurs to anyone.

### After an upgrade

An upgrade that writes leaves `tmp/upgrade/REPORT.md` behind: the conflict
count, the base it started from and each pending file are filled in, and every
other section says in a comment what belongs there. Fill those in, whoever ran
it, so every upgrade of this tree is reported the same way. A second run of the
same upgrade, such as `--ported`, keeps what you wrote and marks a conflict you
resolved; an upgrade to a different version starts the file again.

### A scheduled workflow

No pull request runs a job triggered by `schedule:`, so its first real run is
the night after the merge. Run it here first:

```bash
./pp check scheduled --plan   # what would run, and where it would stop
./pp check scheduled          # run it: the working tree, a clean venv
```

It rehearses the working tree as `git add -A` would commit it, so run it straight
after an upgrade, before committing. It exits 3, no subject, when no job could be
rehearsed in full: nothing was checked, and it still names where each job stopped.

A clean venv is the point. A dependency only that job needs is missing there
and present in your `.venv`, so the rehearsal fails and your own suite passes.
What it cannot stand in for (another action, a secret, a condition beyond
`github.event_name`) stops the job, and the job is reported as not rehearsed,
never as passing. `scripts/rehearse_scheduled.py` has the rules.
