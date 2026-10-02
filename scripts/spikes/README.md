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
| — | nothing right now | — |

`terminal_target/` lived here from 2026-09-03 to 2026-09-04 and asked whether
the model generates a Textual + SQLite terminal app as reliably as it generates
a FastAPI web one. It does — identical repair attempts over six live runs — and
[the report](../../docs/reports/occasional/2026-09-04-terminal-target-go-no-go.md)
keeps the finding. The directory went when the target it gated shipped, exactly
as the section below says it should; its prompts were **moved** into
`protopilot/passes/tui/_brief.py` rather than deleted, because the numbers in
that report describe those exact strings.

## Deleting one

When the plan the spike gates has been decided, delete the directory and the
row above in the same commit as the report that quotes it. The report keeps the
finding; the code that found it has no second job.
