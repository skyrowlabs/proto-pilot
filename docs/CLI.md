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
| `pp pr`     | Land a branch: `check pre-push`, push, pull request, its checks, then the pinned merge command |

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
proto plan "start a community tool library" --for "renters in one town" --must "volunteer run" --not "delivery"
proto plan "start a community tool library" --offline --yes
proto plan            # at a terminal: asks for the idea, then each field of the brief
```

**The idea is one sentence; the brief beside it is optional, and what you state is the
plan's.** The scope pass is shown each field you fill and asked only for the blanks, and
whatever it returns, your field is put back over it, offline or not. The outline review
marks each of them `(yours)`, so you can tell what you said from what the model
inferred. Leave out `IDEA` at a terminal to be asked for the idea and each field in
turn; a field given as a flag is not asked again. Off a terminal, or with `--yes`, a
missing idea is refused before any model is called.

| Flag | What it does |
| ---- | ------------ |
| `--goal` | What the finished plan should let you decide or do. Kept as written |
| `--for` | Who the idea is for. Kept as written, as the plan's audience |
| `--horizon` | The span the plan covers: time, budget, people. Kept as written |
| `--must` | A constraint the plan has to respect. Repeatable; listed first in *Constraints*, after any direction |
| `--not` | Something deliberately out of scope. Repeatable; given to every pass after scope, and listed in its own *Out of scope* section |
| `--direction` | Free-text steer for anything the fields do not hold, kept as a constraint |
| `--dir` | Target directory; the default is `./<slug>` |
| `--depth` | Topics in the outline: `shallow` 4, `standard` 6, `deep` 8, and research effort: 3–4, 4–6 or 6–8 findings a topic, reading at most 3, 5 or 8 pages. A topic answering with more findings than that fails. The default is `standard`, and it is refused on an offline backend |
| `--backend` | `api` bills API credit, `claude-code` a Claude subscription, `offline` calls no model. Beats `PROTOPILOT_LLM`; with neither set, `api` is used |
| `--offline` | The deterministic baseline with no model call. Beats `--backend` |
| `--yes`, `-y` | Skip scope's questions, which stay open in `PLAN.md`, and the outline review |
| `--no-dream` | Skip dreaming. `dreams.md` says it has not run, and `proto dream` can start the pool later |
| `--no-research` | Skip research, for a plan made in a minute or two. It is stamped *Not researched* |

A run calls a model by default: `scope`, `outline`, the review, `research`, `connect`,
`consider`, `start`, `collect`, `evaluate`, `propose`, verification, any repair, then
render. The checkpoint estimates 8 calls plus one research call per topic, or 5 with
`--no-dream`, and a dream pass with nothing to read makes none. It also prints the
research time and reported cost, from one measured topic: about two minutes and $0.40
each, the price the run would carry, not a subscription charge.

**Research runs on `--backend claude-code` only.** Each topic gets one call holding web
search and web fetch and nothing else. A finding is cited only if this run fetched its
page with usable content, which is judged by a heuristic, and anything else is labelled
an assumption; `sources.md` lists what was cited and not fetched, and every fetch that
failed, as plain text and never as a link. A fetched page is read
through a model's summary of it, so a citation shows the summary was read, not that the
claim is in the page. With `--backend api` the command refuses before any call unless
`--no-research` is given. Offline, nothing is researched. A topic whose research fails
says so on its page and costs nothing else; `PLAN.md` names every topic not researched.
A call whose answer is refused or fails is asked once more, unless the session held more
than the web or ran out of time. Each stream not used is kept as
`.protopilot/research/<topic>.refused-<n>.jsonl`, and the failure names it. A kept stream
is never read as evidence and never resumed from.

**A run that stops during research, or after it, resumes.** Rerun the same command: the
reviewed outline and each researched topic's transcript are kept in
`.protopilot/research/`, and no topic already done is asked again. The transcripts stay
after the plan lands, as the evidence a rerun checks sources against. A resume is refused
with `--no-research`, with a `--depth` other than the outline's, offline, and on a
backend that cannot research, because finishing there would drop the research already
done.

**Dreaming runs by default, at a small count:** one dream through each of the six
lenses, of which at most three are proposed. Dreams are guesses, not findings, and they
go in `dreams.md`, never in a topic file. [`proto dream`](#proto-dream) has the rest.

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

**A failed model pass leaves no tree**, unless research had begun, which resumes as above. Otherwise a rerun starts from scope, and any review
edits are lost. A failed repair pass is not one of these: it ends repair, and the tree
is written as above. **Nor is a failed dream pass:** the plan is written without
dreams, `dreams.md` and a closing line say what stopped, and the run exits as the plan's
checks decide, so 0 on a green plan. `proto dream` tries again. A render that fails after saving `plan.json` keeps it, so a rerun
redraws it with no model call. A write that dies partway can leave old topic pages
behind, and the error says any page may be out of date until that rerun.

**Rerunning a finished plan verifies it again and re-renders it.** It calls no model
and needs neither `--yes` nor a terminal. It exits 1 if the plan is red, with the same
runbook and banners, so it is how a hand edit to `plan.json` gets checked. A source
marked fetched by hand stays red: the check reads the run's transcripts, not the flag. A
topic whose transcript is missing, renamed or edited is shown as failed research. With no
model there is no repair: to have one try again, remove the directory and start over.
The same target with another idea, direction or brief is refused, as is a `--depth`
other than the plan's. The brief is compared as typed, after spacing is collapsed, so
the command that made a plan is the command that re-renders it.

**A page's name belongs to the plan.** A `RUNBOOK.md` of your own is left alone on
green, and blocks a red plan: every other page is drawn and marked, and the command
refuses with exit 1 until it is moved. A link at a page path is refused the same way,
as is a directory there, except that on green nothing is drawn. Nothing is written
outside the tree. A green run removes only a runbook this tool wrote.

## A plan on the other verbs

`proto plan` lists its folder on this machine as kind `plan`, once `plan.json` lands,
whether the plan is green or red, and even when a page could not be drawn. A plan made before plans were listed joins the list
the next time `proto plan` redraws it.

| Command | On a plan |
| ------- | --------- |
| `proto ls` | Listed with its kind, and `gone` once its `plan.json` is |
| `proto rm` | Deletes the folder and forgets it. `--dir` names the folder, which defaults to the current one, and `--yes` skips the confirmation |
| `proto prune` | Forgets it once its `plan.json` is gone. `--yes` skips the confirmation |

`proto ls` prints one row per entry: its state, kind, slug and path. The state is `-`
for a plan on disk, `gone` or `old`. It ends on `N plan(s)`, then a line counting the
`gone` rows and a line counting the `old` ones, each only when there are any. It reads
the list and never changes it. `proto prune` lists what it will forget, asks, and then
reports `forgot N: G gone, O old`. It changes the list only, never a folder.

What a folder is comes from its own files, never from the list: a `plan.json` there
makes it a plan. A folder without one, including one whose research stopped before
`plan.json` was written, is refused by `proto rm`, and so are `/` and any folder that
is or holds your home or the list itself.

**A prototype made by an older proto.pilot is not a plan.** Its row, of kind `app` or
with no kind, is listed as `old`, and `proto prune` forgets the row and leaves the
folder alone. `proto rm` refuses a folder holding the `spec.json` such a prototype
kept, even when a `plan.json` sits beside it, and says what to run
there instead: `docker compose down -v` for a web prototype, then delete the folder by
hand. Two folders
never share a slug in the list: one whose slug is taken is listed as `_2`, `_3`.

`proto doctor` takes no flag. It reports whether the `anthropic` SDK is installed and
whether each backend, API credit and a Claude subscription, is reachable. It exits 0
when the SDK is there and at least one backend answers, and 1 otherwise; `--offline`
works either way.

## `proto dream`

Everything that happens to a plan's pool of dreams after the plan exists. Each command
works on a green plan already on disk, and none of them prompts, so none needs `--yes`.

```bash
proto dream                                     # another round, on the plan in this folder
proto dream ./mytree --lens who-else --lens the-opposite
proto dream promote d4 --dir ./mytree
proto dream drop d7 --why "needs a second town" --dir ./mytree
```

| Command | What it does | Model calls |
| ------- | ------------ | ----------- |
| `proto dream [DIR]` | Adds a round to the pool. `DIR` defaults to the current folder | 3 at most |
| `proto dream promote ID` | Turns a dream into the plan's last topic, connected and verified | 1, plus 0 to 3 repair calls |
| `proto dream drop ID --why WHY` | Rules a dream out. `--why` is required, and the reason stays beside it | None |

**The verbs and the directory share one position.** A first word that is a verb is the
verb, and anything else is a directory for a round. So a directory named like a verb is
written `./promote`, `./drop` or `./round`. `proto dream round [DIR]` is the same round
spelt out, and `proto dream --help` lists the verbs. `promote` and `drop` never take a
position for the directory: they take `--dir`, which defaults to the current folder.

| Flag | On | What it does |
| ---- | -- | ------------ |
| `--lens` | a round | Dream through this lens only; repeat for more. One of `who-else`, `the-opposite`, `ten-times-bigger`, `the-smallest-version`, `remove-the-main-constraint`, `borrow-from-another-field`. The default is all six |
| `--offline`, `--backend` | a round, `promote` | As on `proto plan`. `drop` calls no model and takes neither |
| `--dir` | `promote`, `drop` | The plan's directory |
| `--why` | `drop` | What ruled the dream out |

**A round goes wider than a plan's own:** two dreams through each lens, not one. It adds
and never rewrites, so a dream keeps its id, words and verdict through every later round.
`collect` writes the dreams. `evaluate`, a separate call, rates each on `pull`, `reach`,
`cost` and `fit`, never summed, then gives a verdict of `proposed` or `set-aside` with a
sentence of reasoning, and merges near-duplicates, including of a dream already set aside
or dropped. `propose` keeps at most three a round, each saying what would change if
adopted, and whatever it passes over is set aside.

**A dream is at most 44 words** across its title (6), what-if (26) and what it would take
(12). One over the cap, or otherwise unfit for the pool, is left out with a line saying
why, and costs only itself. Offline, a dream is a template that says so, its ratings read
`not judged`, and the first few in lens order are proposed.

**Only a person promotes.** Any dream not yet promoted can be, a set-aside or dropped one
included, and no pass can do it. The links and notes come from one call, and every link
must touch the new topic. Offline it depends on the dream's anchor and has no risks,
unknowns or decisions. Repair may mend only what touches the new topic, because what the
plan held before is settled. The topic is not researched, and on a researched plan its
page and `PLAN.md` say it was promoted from a dream.

**Exit codes.** Each command changes nothing and exits 1 when:

- The plan is red. All three refuse it with no model call, and name the check to mend.
- A pass fails. `proto plan` writes on past a failed dream pass, and a round does not.
- A promotion stays red after repair. The report says what failed and what repair tried.
- The id is not in the pool, or `plan.json` changed while the command ran.

A round in which no dream survives is not a failure: it reports `0 new dream(s)`, keeps
the pool and exits 0. If the pool is still empty, `dreams.md` says dreaming failed.

**Two limits.** `dreams_apart`, the check that keeps dreams out of topic files, catches a
copy with a word or two changed and misses a paraphrase. The API backend has never been
run for these passes, and it asks for the word limits in a schema description where the
`claude-code` backend enforces them. `verify.py` holds the cap on both.
