# Do our docs name commands the CLI actually has?

> **Analyzed at:** v0.1.0 +25 commits
> Prompted by skeletor, who scanned their own template for this after we
> redirected them from a README to `docs/rules/docs.md` as the bigger surface.

**One real defect, three false positives, and a gate that should not be built.**

## What was scanned

Every `pp <group> <cmd>` and `proto <cmd>` named in any tracked markdown file,
invoked against `--help`. 44 distinct invocations; 4 did not resolve.

## The one that was real

`docs/DEVELOPMENT.md`, `## First-Time Setup`, first line of the first code
block: `./pp setup`. **There is no `pp setup`** — `pp` offers bug, check,
commit, docs, report, test, worktree.

The repo already knew. [`AGENTS.md`](../../../AGENTS.md) carries the fact *with
its reasoning*: `setup` "could not be implemented, because the CLI cannot run
until the install it would be performing has already put `click` in the venv. A
quick start that fails on line one reads as user error at the exact moment a
reader has no way to tell."

So AGENTS.md was corrected at some point and DEVELOPMENT.md was not, and the
stale copy was the **developer setup guide's opening command** — the first thing
a new contributor types. Two docs in one repo disagreeing, with the correct one
stating the fact only in passing, in a paragraph about a past mistake.

Fixed in the same sitting: the block now names `cp .env.example .env`,
`pre-commit install --install-hooks` and `scripts/git/install_merge_drivers.py`,
each verified to run.

## Why the gate this implies should not be built

**The scan output is byte-identical before and after that fix.** The replacement
prose says "There is no `pp setup`, deliberately" — so the file still names the
command, now to deny it. A matcher cannot tell an instruction from a denial.

Three distinct kinds of legitimate absence turned up, and they look the same:

| Kind | Example | Why it is fine |
| ---- | ------- | -------------- |
| Never implemented, named to say so | `pp setup`, `pp service up` (`AGENTS.md`) | The sentence exists *because* the command does not |
| A wrong command **name**, named as an error | `proto check docs` (`AGENTS.md`) | Two CLIs here; the doc warns about confusing `proto` with `pp` |
| Planned, in an unbuilt plan | `proto improve --log` (`docs/TODO/improvement-loop.md`) | **A plan naming commands that do not exist yet is what a plan is** |

Only the third has a mechanical answer — exclude `docs/TODO/` by construction.
The first two differ from each other in *intent* while being identical to any
pattern, and they live in `AGENTS.md`, the file most likely to explain why a
command is absent. A gate would ship red on arrival there and spend its life
being taught the difference between prose and instruction.

~~**So: run this by hand when touching a docs command block. Do not make it a
gate.**~~

## Errata, same day — that conclusion was wrong, and my own table refutes it

skeletor built the gate after reading this report, and the argument is one I had
in front of me and did not see: **all three classes above are prose.** A fenced
` ```bash ` block is different *in kind* — it is not describing a command, it is
telling you to run one.

Scope the scan to fenced blocks and all three fall out at once. Not by
allowlist, not by teaching a matcher to read intent — by construction. Class 3
is excluded twice over, since a tank plan goes by role as well.

They measured it rather than asserting it: 24 invocations across a generated
tree, **0 false positives**, including their own replacement paragraph that
names `setup` three times to explain its absence. Planted three cases — the
original line restored (fires), the same command in prose (silent), a tank plan
with a ```bash block calling an unbuilt command (silent).

So the finding this report should have reached is the opposite of the one it
published, and skeletor put the reason better than "I read past it":

> **The complete solution was produced here and labelled an obstacle.** The
> three classes were not evidence a gate was impossible — they were the
> specification of what a scope rule had to exclude, and enumerating them *is*
> the work.

What was missing was a single question — *what do these three have in common?* —
and its answer had to be a property of the **class** rather than of any member.
That is not where attention goes while you are busy telling three things apart.
The table above is unchanged because it is correct; only the direction the next
question pointed was wrong, and that is a more useful lesson than carelessness
would have been, because carelessness has no remedy but trying harder.

Shipped in skeletor `v0.2.4` as `tests/test_docs_name_real_commands.py`, in
core. Two properties worth copying if this is ever taken here: it walks click's
command registry rather than shelling out `--help` per command, so it is exact
and needs no built venv; and **it asserts the scan found something**, because a
scan over zero fenced blocks is green and worth nothing — which is this repo's
own pyright finding applied to the check that came out of it.

## The habit — which is a different animal from the gate

skeletor's correction on this is worth keeping too. The tally below is really
two failures, and one process fix does not touch the other. Ours was writing a
command into a document no shell had answered — a habit. **Theirs was a fix
applied to two of three copies, by someone who knew the reason and had written
it down** — which no amount of care prevents and which is exactly what a gate is
for. Filing both under "be careful" would have lost that.

Not a check. The defect existed because a command was written into a document
that no shell had ever answered. The same shape produced two other misses the
same day — commands written into a README sent to skeletor unrun, and a claim
about two workspace files never opened.

> **Do not write a command into a document until a shell has answered it.**

## Ruled out, so nobody pays for this twice

- `pp`'s command surface is otherwise accurate across all tracked markdown: 40
  of 44 invocations resolve, and the 4 that do not are catalogued above.
- The three replacement commands in `docs/reports/README.md` — the file sent to
  skeletor — were verified here and independently by them in a `core/python`
  scaffold. All three are core-tier; no tier gets `docs/reports/` without them.
