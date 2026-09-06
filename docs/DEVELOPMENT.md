# Development Guide

## First-Time Setup

```bash
cp .env.example .env                            # then fill it in
.venv/bin/pre-commit install --install-hooks    # commit-msg format + lint gates
python scripts/git/install_merge_drivers.py     # the regen-docs driver
./pp check health                               # is everything answering?
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
- **The `regen-docs` merge driver** — its definition lives in `.git/config`,
  which is not tracked, so **every clone after the first installs it by hand**.
  That is the third line above; there is no step that does it for you. Verify
  with `pp check merge-drivers`, which checks and never installs.

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
```

`--ci` sets `PP_CI=1`, under which an env-gate skip becomes a **failure**.
That is the difference between "the suite passed" and "the suite ran".

Full rules: [`docs/rules/testing.md`](rules/testing.md).

## CI/CD Pipeline

| Event                          | What runs                              | ~min |
| ------------------------------ | -------------------------------------- | ---- |
| Draft PR                       | `CI Gate` alone                        | ~1   |
| Ready PR → `develop`, docs-only | `CI Gate` alone               | ~1   |
| Ready PR → `develop`, code      | `CI Gate` + `Unit Tests`      | ~5   |
| Ready PR opened by Dependabot  | **everything** — deliberately exempt   | full |
| Push to `main`   | **everything** + Release Please        | full |

Three things about this table are load-bearing:

1. **A required context that reports `skipped` satisfies branch protection.**
   So gating is done with `if:` on the job, never `paths-ignore` on the trigger
   — a required check that never reports at all blocks the PR forever.
2. **Requiring a context costs nothing; only running a job does.** Size the
   required list for what must gate. Never trim it to save minutes.
3. **The Dependabot exemption is a mechanism, not a courtesy.** Auto-merge fires
   the moment branch protection is satisfied, so without the exemption every
   eligible bump merges having never run the suite it exists to be checked by.

## Releases

Versioning is Conventional Commits → Release Please. Commit types decide the
bump; `CHANGELOG.md` and `VERSION` are generated. **Never hand-edit either.**

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
