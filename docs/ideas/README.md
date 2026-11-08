# Ideas — captured, not scheduled

An idea that grew past a paragraph in [`NOTES.md`](../../NOTES.md) but is not a
plan lands here. Nothing in this folder is committed to, costed, or queued.

| Idea | Captured | One line |
| ---- | -------- | -------- |
| [Plans first](plans-first.md) | 2026-11-06 | The product is now planning; physical prototyping is tabled until an idea is concrete — **plan: [plan-prototypes](../implementations/spec/plan-prototypes.md)** |
| [Sketches, not scaffolds](sketches-not-scaffolds.md) | 2026-09-03 | Emit a terminal app you learn from and throw away; ship as a tool, not a service — **plan cut: [terminal-target](../implementations/spec/terminal-target.md)** |
| [Hosted proto.pilot](hosted.md) — **tabled** | 2026-08-28 | Put `proto new` behind a free public page to build a training corpus |

A tabled idea keeps its row. The reasoning is what the folder is for, and the
successor doc says which parts of it still hold — a row deleted is a question
somebody asks again in six months.

## What belongs here — and what does not

An idea, and **what came of looking at it**. Both, in one folder:

| Folder | Holds | The decision made |
| ------ | ----- | ----------------- |
| `docs/ideas/` | An idea, a feasibility memo, a write-up of why one was dropped | Nobody has decided to **build** it |
| `docs/TODO/` | A plan with a shelf status and a gate | Somebody decided to build it |

A doc leaves this folder in one direction only: to `docs/TODO/` when someone
decides to build it. An examined-and-rejected idea keeps its memo right here,
because the expensive half of an investigation is what it ruled out.

**A doc moves only when the whole idea becomes the plan.** When a plan is cut
from one *slice* of an idea, the idea stays and links to it — they are not two
copies of one thing, they are the argument and the phases, and the rule that
governs both is that a doc lives where it changes. `sketches-not-scaffolds.md`
is the worked case: three decisions, one of which became
[terminal-target](../implementations/spec/terminal-target.md) while the other two are not build
tasks at all. Moving it would have filed a direction in the work queue.

**This started as a three-way split** — idea, then `research/` once somebody
looked, then `TODO/`. skeletor's user collapsed the first two in their template
and the argument is right: an unexamined idea and the write-up of examining it
are the same *kind* of document, and splitting them asks the author to classify
at the moment they know least, with the answer going stale the instant anybody
does the work.

The two documents in this folder settled it before the argument arrived.
`hosted.md` was examined and tabled and did not move; `sketches-not-scaffolds.md`
is literally what came of looking at it, and it is filed as an idea. The rule
had been contradicted by its own first two cases within a day of being written.
The boundary that survives is the one this folder shares with the tank, and it
is crossed once, in one direction.

## Why this folder exists

Root `docs/` is current, critical reference — the docs an agent loads to do
today's work. An unscheduled idea sitting beside `ARCHITECTURE.md` reads as
though it describes the system, and `pp check docs` made that worse by
*requiring* a routing row for it: the tables that tell an agent what to read
were being made to advertise a thing nobody is working on.

Both scans that enforce that registration — `scripts/check_doc_tables.py` here
and skeletor's `register_shipped_docs` at scaffold time — glob `docs/*.md` and
do not descend. So a doc in this folder is registered by **this file**, which
the index tables point at, exactly as they point at `TODO/README.md` rather than
at each plan. Add a row above when you add an idea; a doc here that this table
does not list is a doc no agent will find.
