# Spikes

Throwaway code that produces a number somebody then commits.

A spike is not a feature and it is not a script anybody runs twice a week. It
exists to answer one question a plan is gated on, cheaply, **outside** the
thing it is asking about — because building the seam first is how a gate stops
being able to say no.

It lives here, in the repository, rather than in `prototypes/`, `scratch/` or a
tmpdir, for exactly one reason: **its numbers get quoted in a report.** A
measurement nobody can re-run is an anecdote, and an anecdote in
`docs/reports/` reads exactly like a measurement. So the code that produced the
number is committed, linted and type-checked like everything else here, and the
report says which commit it was produced by.

What that buys, and what it does not:

- It is **not** product code. Nothing under `protopilot/` may import from here,
  and nothing here is on any support promise. A spike is deleted when its plan
  is decided, and deleting it must break nothing.
- It **is** held to the repo's gates — `pp check lint`, output discipline,
  pyright. Not for tidiness: a spike with a bug produces a number that is wrong
  in a direction nobody can see, and it costs live model calls to find out.

## What is here

| Directory | Question it answers | Plan |
| --- | --- | --- |
| `terminal_target/` | Does the model generate a Textual + SQLite terminal app as reliably as it generates today's FastAPI web app? | `docs/TODO/terminal-target.md`, Phase 1 |

## Deleting one

When the plan the spike gates has been decided, delete the directory and the
row above in the same commit as the report that quotes it. The report keeps the
finding; the code that found it has no second job.
