# CLI Reference

`./pp` is the single entry point for everything you do in this repo. It is a
thin shell wrapper around the `cli/` package.

**The rule that keeps it useful**: adding or changing a script means updating
`cli/` in the same commit. A script nobody can discover is a script nobody runs,
and the second person to need it writes it again.

## Command Groups

| Group          | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `pp check`  | Every validation gate CI blocks on, runnable locally |
| `pp test`   | Marker-driven suite selection                        |
| `pp docs`   | Index regeneration, plan filing, report windows      |
| `pp bug`    | Capture an out-of-scope defect without widening scope |
| `pp task`   | Capture small work that is not a defect              |
| `pp doctor` | Account facts no file can state (release PRs, required checks) |
| `pp settings` | Set GitHub settings to `scripts/repo_settings.py`; previews unless `--apply` |
| `pp inbox`  | Every open capture per lane, every job at its cap, and every Dependabot PR waiting on a person |

Run `./pp <group> --help` for the current commands — the help is generated
from the code, so it cannot go stale the way this table can.

## Why the Wrapper Is Not Just `python -m cli`

Three environment problems, each documented at the point it is handled in the
wrapper script:

1. **Relative `PATH` entries.** A `PATH=.venv/bin:$PATH` prefix is re-resolved
   against each child process's own cwd, so an interpreter found through it
   breaks every child that chdirs. The wrapper absolutizes `PATH` before
   anything is looked up through it.
2. **`python -m` resolves from `sys.path`, not the script's location.** The
   wrapper exports `PYTHONPATH`, resolving symlinks first, so the CLI works from
   any directory and when symlinked onto `PATH`.
3. **A linked worktree has no venv.** `git worktree add` creates a checkout with
   no `.venv` and nothing creates one; the wrapper borrows the main worktree's.
   Same repository, same requirements — only the installed packages are shared,
   never the code.

## Reproducing CI Exactly

```bash
PP_PYTHON=.venv-ci/bin/python ./pp check pre-push
```

A broken override fails loudly rather than falling back. Silently running the
diverged default interpreter is the exact false negative the override removes.

## `proto plan`

`proto` is the product, not this repository's tooling, so `./pp` does not reach it.
`proto plan --help` lists the same flags.

```bash
proto plan "start a community tool library" --direction "one town, volunteer run"
proto plan "start a community tool library" --offline --yes
```

| Flag | What it does |
| ---- | ------------ |
| `--dir` | Target directory; the default is `./<slug>` |
| `--direction` | Extra steer, kept as a constraint |
| `--depth` | Topics in the outline: `shallow` 4, `standard` 6, `deep` 8. The default is `standard`, and it is refused on an offline backend |
| `--backend` | `api` bills API credit, `claude-code` a Claude subscription, `offline` calls no model. Beats `PROTOPILOT_LLM`; with neither set, `api` is used |
| `--offline` | The deterministic baseline with no model call. Beats `--backend` |
| `--yes`, `-y` | Skip scope's questions, which stay open in `PLAN.md`, and the outline review |

A run calls a model by default: `scope`, `outline`, the review, `connect`, `consider`,
`start`, verification, any repair, then render. **It does no research or dreaming
yet**, so every plan is stamped *Not researched* and holds no findings beyond the
offline baseline's assumptions.

**Verification proves structure, never truth.** A green run ends on a line built from
what held: it names those checks and claims nothing past them. A check with nothing
to read is reported as *no subject*, which is not a pass.

**Red gets up to 3 repair attempts, on links and steps only.** The checkpoint's
estimate counts them as 0 to 3 extra calls. Repair can mend a `depends-on` loop or the
order of the steps, so any other failure goes unrepaired, and offline it changes
nothing.

**When repair runs out, the whole tree is still written, and the run exits 1.** It
holds a `RUNBOOK.md` saying what is wrong and what was tried, `PLAN.md` and every topic
page carry a *Not verified* banner, and there is no green line.

At the review, Enter accepts, `add TITLE`, `drop N` and `rename N TITLE` edit, and
`quit` stops with nothing written. Edits can leave the outline anywhere from four to
eight topics, whatever `--depth` asked for.

**Off a terminal it needs `--yes`, even with `--offline`.** Without it the command
refuses before calling a model.

**A failed model pass leaves no tree.** A rerun starts from scope, and any review
edits are lost. A failed repair pass is not one of these: it ends repair, and the tree
is written as above. A render that fails after saving `plan.json` keeps it, so a rerun
redraws it with no model call. A write that dies partway can leave old topic pages
behind, and the error says any page may be out of date until that rerun.

**Rerunning a finished plan verifies it again and re-renders it.** It calls no model
and needs neither `--yes` nor a terminal. It exits 1 if the plan is red, with the same
runbook and banners, so it is how a hand edit to `plan.json` gets checked. With no
model there is no repair: to have one try again, remove the directory and start over.
The same target with another idea or direction is refused, as is a `--depth` other
than the plan's.

**A page's name belongs to the plan.** A `RUNBOOK.md` of your own is left alone on
green, and blocks a red plan: every other page is drawn and marked, and the command
refuses with exit 1 until it is moved. A link at a page path is refused the same way,
as is a directory there, except that on green nothing is drawn. Nothing is written
outside the tree. A green run removes only a runbook this tool wrote.
