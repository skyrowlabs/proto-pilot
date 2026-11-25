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
says so on its page and costs nothing else. A plan with a topic left out is stamped
*Partly researched*, and `PLAN.md` names every topic not researched.
A call whose answer is refused or fails is asked once more, unless the session held more
than the web or ran out of time. Each stream not used is kept as
`.protopilot/research/<topic>.refused-<n>.jsonl`, and the failure names it. A kept stream
is never read as evidence and never resumed from.

**A run that stops during research, or after it, resumes.** Rerun the same command: the
reviewed outline and each researched topic's transcript are kept in
`.protopilot/research/`, and no topic already done is asked again. The transcripts stay
after the plan lands, as the evidence a rerun checks sources against. A topic researched
again gets a numbered transcript beside its first, `<slug>.2.jsonl`. A resume is refused
with `--no-research`, with a `--depth` other than the outline's, offline, and on a
backend that cannot research, because finishing there would drop the research already
done.

**A plan can be revised after it is made.** [`proto answer`, `proto topic` and
`proto research`](#revising-a-plan) each change one thing and leave the rest as it was.

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
plan held before is settled. The topic is not researched until
[`proto research`](#revising-a-plan) is run on it, and until then, on a researched plan,
its page and `PLAN.md` say it was promoted from a dream.

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

## Revising a plan

What changes a plan after it is made, apart from its dreams. Each command works on a
green plan already on disk, does one job, and either lands the plan green or leaves the
plan as it was and exits 1. `--dir` names the plan's folder and defaults to the
current one. Only `proto answer` prompts, and none takes `--yes`.

```bash
proto answer 2                                   # answer open question 2; it becomes a constraint
proto topic rename scope "The boundary"
proto topic drop operations --why "one volunteer runs it, so there is nothing to plan"
proto topic add "Insurance" --why "a borrowed saw can hurt someone"
proto research insurance --backend claude-code   # research one topic, or research it again
```

| Command | What it does | Model calls |
| ------- | ------------ | ----------- |
| `proto answer [N]` | Asks open question `N`, or each in turn, and makes the answer a constraint | None |
| `proto topic rename SLUG TITLE` | Changes a topic's title and keeps its slug | None |
| `proto topic drop SLUG --why WHY` | Removes a topic and what pointed at it, and keeps the reason | None, or `start` and 0 to 3 repair calls if no step is left |
| `proto topic add TITLE --why WHY` | Adds a topic as the plan's last, connected and verified | 1, plus 0 to 3 repair calls |
| `proto research SLUG [--deeper]` | Researches one topic on the web and replaces what it had found | 1 research call, `connect` and `consider` for that topic, plus 0 to 3 repair calls |

| Flag | On | What it does |
| ---- | -- | ------------ |
| `--dir` | all five | The plan's directory |
| `--why` | `topic drop`, `topic add` | Required. Why the topic is ruled out, or why it matters |
| `--offline`, `--backend` | `topic drop`, `topic add`, `research` | As on `proto plan`, except that `research` refuses `--offline` and `--backend offline`. `answer` and `topic rename` call no model and take neither |
| `--deeper` | `research` | Gives this one call the findings and pages of the next `--depth` up. The plan's depth is not changed. Refused on a `deep` plan, which has no depth above it |

**An answer changes nothing else.** The question leaves *Open questions*, the answer joins
the constraints as `question answer`, and `PLAN.md` is redrawn. No topic is outlined or
researched again: to have an answer move a topic, run `proto research` on that topic,
whose prompt holds the constraints. `N` counts the questions as `PLAN.md` lists them, from
1. The answer is read at a prompt, so it can be piped in, and with no input at all the
command aborts and exits 1. Enter at a prompt leaves that question open, and when no
answer is given nothing is changed and the command exits 0. A plan with no open question
says so and exits 0.

**A slug is a topic's identity.** `rename` changes the title and nothing else, so the
file name, the links, the steps, the dreams and the research stay with the topic. A
title another topic already has is refused, whatever its capitals, and so are an empty
title and the title the topic already has.

**A drop removes what pointed at the topic, and says what it removed:** its links, its
step, and any source no other topic cites. A dream that extended it is set aside with
the reason "Its topic was dropped", never deleted, and a dream the topic was promoted
from is dropped with your `--why`. The research transcript stays in
`.protopilot/research/`, and a later research of the same slug never replays it: the
drop removes the topic's record from `plan.json` and any `<slug>.pending.json`. The stamp
follows the records that are left. If the topic was the only one researched, the plan is
stamped *Not researched* again, and if it was the only one left out, *Partly researched*
becomes *Researched*. A plan keeps at least four topics, so a drop from four is refused.
`start` runs again only when
the drop leaves no step to begin on, which is the one case a model is called; `--offline`
takes the baseline's steps then.

**The dropped topic is remembered.** `PLAN.md` lists it under *Dropped topics* with the
reason, and `dreams.md` marks a dream that extended it as extending a dropped topic.
Adding the same title or slug later says it was dropped and why, then adds it: that is a
person's call to make again. It leaves *Dropped topics* only if it comes back under its
old slug. A title whose slug comes out different is a new topic, and the old entry stays.

**An added topic lands as a promoted dream does.** One call supplies its links and
notes, every link must touch it, and repair may mend only what touches it. Offline it
is linked to nothing and has no risks, unknowns or decisions. Either way it is not
researched until `proto research` is run on it. A plan holds at most eight topics, and a
title another topic already has, whatever its capitals, or whose slug a topic already has, is refused.

**Research replaces one topic's record and never merges.** The new transcript is written
beside the old one under a numbered name, the topic's findings are replaced, and a source
only that topic cited leaves `sources.md`. `connect` then reopens the links of that topic
alone, `consider` rewrites its risks, unknowns and decisions, and no other topic's text is
written. If the call cites no page it fetched, the topic reads as not researched again.
It runs on `--backend claude-code` only. Offline and `--backend api` are each refused in
a sentence before any call, and so is `--deeper` on a `deep` plan.

**A try that stopped after its research call is replayed.** The transcript is on disk
before anything else runs, beside a `<slug>.pending.json` that marks it as not landed, so
if a later step fails the plan is left as it was and a rerun reads that transcript
instead of paying for the call again. The mark holds the transcript's number and sha256,
the depth asked, the transcript the topic's record named when the try began, and a
fingerprint of what was asked. The fingerprint is a hash of the whole research prompt:
the idea and its scope, the constraints, the topic's slug, title and reason, and the slug
and title of every other topic. A rerun replays the transcript only while all of that
holds, at the depth it was asked at. It makes a new call, and the log says why, when:

- the rerun adds `--deeper` to a plain try. A plain rerun of a `--deeper` try replays it;
- the prompt has changed: an answer was given, or any topic was renamed, added or
  dropped, this one or another, because the prompt names them all;
- the transcript is missing or its bytes no longer match the hash;
- the mark was written before marks held a hash and a fingerprint.

A replay that fails drops the mark, so the next run asks again. Landing the research
removes the mark, and a mark that cannot be read replays nothing. No transcript is ever
deleted: one that is not replayed stays as it is, and a new call takes the next free
number.

**After any of these, repair may move only what touches the changed topic.** Links
between other topics, their steps and their text are settled, and a repair that moves
one is thrown away.

**A plan researched in part says so.** Researching one topic of a plan made with
`--no-research` stamps `PLAN.md` and `sources.md` *Partly researched*, with every topic
left out named, and redraws no other topic's page.

**Exit codes.** Each command exits 0 when the plan lands green, and changes nothing and
exits 1 when:

- The folder holds no plan, or the plan is red. All five refuse it with no model call.
- There is no such topic or question. The refusal lists the slugs the plan holds, or
  counts its open questions.
- The change is one the plan cannot hold: a title already taken, a drop that would leave
  three topics, an addition that would make nine, a `--why` that is blank.
- `proto research` is given a backend that cannot research, or `--deeper` on a `deep` plan.
- A pass fails, or the result stays red after repair. The report says what failed and
  what repair tried.
- `plan.json` changed while the command ran.

`proto answer` exits 0 with nothing changed when the plan has no open question or no
answer was given. A missing `--why`, or an `N` below 1, is a usage error and exits 2.
