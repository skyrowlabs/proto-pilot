# The terminal-target measurement

Phase 1 of [`docs/TODO/terminal-target.md`](../../../docs/TODO/terminal-target.md):
a go/no-go on whether the model writes a Textual + SQLite terminal app as
reliably as it writes today's FastAPI web app.

It builds **none** of the `target` axis the rest of that plan describes — no
`Spec.target`, no `protopilot/targets/`, nothing under `protopilot/` at all.
That is the point rather than an omission. A gate that has to build the seam it
is gating cannot say no, because by the time it reports, the expensive half is
already committed.

## Running it

```bash
.venv/bin/python scripts/spikes/terminal_target/run.py --list
.venv/bin/python scripts/spikes/terminal_target/run.py --target tui --spec field_notes --backend claude-code
.venv/bin/python scripts/spikes/terminal_target/run.py --target web --spec field_notes --backend claude-code
```

Six runs is the measurement: three specs × two targets. They are independent —
run them one at a time, in any order, and re-run one without redoing the rest.
Records go to `tmp/spikes/terminal-target/` by default, which is gitignored —
right for a tree of generated apps and prompt dumps, wrong for the numbers.
**Copy `runs.jsonl` next to the report that quotes it**, or pass `--out`. A
figure in `docs/reports/` whose working was in `tmp/` is a figure nobody can
check.

- The **web** half needs Docker. The terminal half needs neither Docker nor a
  browser, which is itself half of what is being measured.
- `--passes schema` runs one terminal pass, for checking the harness is alive
  without spending a run. It is refused for `--target web`, which runs the real
  pipeline unmodified or not at all.
- `--no-verify` generates without booting. Such a run records `green: null`,
  never `green: false`: a generation nobody booted has not failed.

## What comes out

`tmp/spikes/terminal-target/<run-id>/`:

| Path | What it is |
| --- | --- |
| `record.json` | the machine-readable record, rewritten after every pass and every verify attempt |
| `runs.jsonl` (one level up) | one summary line per completed run, appended |
| `tree/` | the generated tree, exactly as it was left |
| `prompts/NN-<pass>.md` | the system and user text of every call, as sent |
| `stages/attempt-N-<stage>.txt` | the full failure text of every red verify |

The record carries repair attempts to green, wall clock per pass and in total,
the model's own `duration_api_ms`, token counts, and every failing stage's error
text. That last one is not decoration: the plan says the headline number hides
the thing that matters — whether failures **cluster** (a recurring mistake,
which is a prompt or a skeleton fix and is cheap) or **scatter** (a competence
ceiling, which is not). Only the text answers that, and only if it was kept.

## Token usage, definitively

**Yes, on the `claude-code` backend.** The `claude --output-format json`
envelope carries `usage` (input, output, cache-creation and cache-read tokens),
`total_cost_usd` and `duration_api_ms`. `ClaudeCodeLLM.structured` reads one key
out of that envelope and drops the rest, which is right for the product and is
why the numbers are not simply available — so the harness injects its own
`Runner` through the constructor parameter that already exists and keeps the
envelope. Nothing under `protopilot/` changes.

Two things to read carefully before quoting a number:

- Every call carries **~32k tokens of Claude Code's own system prompt and tool
  definitions**, as cache-creation and cache-read. That is the backend's
  overhead, not the prompt's, and it is charged on the web target and the
  terminal target alike — so it cancels in the comparison and would dominate any
  absolute figure.
- `total_cost_usd` is an **API-equivalent price for a call billed to a
  subscription**. It is comparable between runs. It is not a bill.

On the `api` and `offline` backends there is no usage to read, and the record
says `usage_available: false` rather than zero. A named absence is worth more
than a fabricated number.

## The backend has tools, and that changes what is being measured

Verified on 2026-09-03, twice, from a one-line prompt: `claude --print` — the
call `ClaudeCodeLLM` makes — arrives with its **full tool set** and the
**caller's working directory**. Asked to read `VERSION` it returned `0.1.0`;
asked to `echo` into a path it wrote the file. `permission_denials` was `[]`
both times.

Two consequences, and only the first is this spike's.

**A pass is not one generation.** The first live terminal run's smoke pass took
**602 seconds across 18 turns and 47k output tokens**, and its `notes` said it
had stood a scratch tree up from `skeleton/` and run the tests it was writing
against two candidate implementations. The schema pass beside it was 24s and 3
turns. So the cost is real, it is uneven, and — this is the part that matters —
**it moves the work out of the repair loop and into the pass, which is exactly
where the plan's headline metric cannot see it.** "Repair attempts to green"
will report the terminal target as cheap while the wall clock says otherwise.
Read the per-pass seconds and tokens beside it, or the number means nothing.

**`files.py`'s guarantee does not hold on this backend.** The README and
`AGENTS.md` both say the model can write five paths and that everything else is
"refused before it reaches disk". That is true of what `structured()`
*returns*. It is not true of the subprocess that returns it, which has `Bash`
and `Write` and is running in your project directory. That is a proto.pilot
bug, it predates this spike, and it is not this spike's to fix — but it is why
a live run should not be started from a tree with uncommitted work in it.

`claude-no-tools` is the wrapper that takes them away, and it is verified to
leave `--json-schema` structured output working:

```bash
PROTOPILOT_CLAUDE_BIN=scripts/spikes/terminal_target/claude-no-tools \
  .venv/bin/python scripts/spikes/terminal_target/run.py --target tui --spec field_notes
```

Which way to run the six is a real choice and it should be made once, for all
six, never mixed:

- **With tools** measures what `proto --backend claude-code` actually does
  today. It is the honest cost of using this tool as it ships.
- **Without tools** measures what Phase 1's hypothesis is actually about —
  whether the model *knows* Textual as well as it knows FastAPI — and it is
  what the `api` backend, which the product prefers, would do.

## Structured output holds

Confirmed live on 2026-09-03 against a Textual prompt with the `FILES_SCHEMA`
shape: `structured()` returned a well-formed `{files: [{path, content}], notes}`.
The plan asks for this to be confirmed rather than assumed, and the reason it
was expected to hold is the reason it does — schema-constrained decoding is a
property of the serving runtime, not of what the app is about.

## What is here

| File | What it owns |
| --- | --- |
| `brief.py` | `TUI_BRIEF`, the five pass prompts, the repair prompt, the terminal archetype fragments, the writable-path list |
| `writer.py` | the write guard, over the terminal target's paths |
| `skeleton/` | the fixed terminal tree: `db.py`, `base.py`, `main.py`, `tests/conftest.py`, `pytest.ini` |
| `specs/` | the three specs, and [why each is there](specs/README.md) |
| `metering.py` | the runner and LLM wrappers that keep the usage envelope |
| `boot_probe.py` | boots the generated app under `App.run_test` in a subprocess and reports what it painted |
| `tui_verify.py` | the four stages, returning `protopilot.verify.VerifyResult` |
| `run.py` | one run, incrementally recorded |
| `claude-no-tools` | `claude` with `--tools ""`, for measuring generation rather than agency |

`tests/test_terminal_spike.py` checks the instrument before it is pointed at a
live model: that the specs are ones the tool would have produced, that the brief
is byte-identical across passes, that the write guard refuses the skeleton, and
— the one that matters most — that the blank-screen check can actually tell a
painted screen from an empty one, demonstrated on a hand-written app rather
than asserted.

## What a run costs, measured

One complete terminal run, `field_notes`, `claude-opus-5` at `effort=high`,
tools on, 2026-09-03. **Green in 2 verify attempts** — one repair — in 25
minutes, 6 model calls, 118k output tokens, $7.44 API-equivalent.

| pass | wall clock | turns | output tokens | of which thinking |
| --- | --- | --- | --- | --- |
| `schema` | 24s | 3 | 1.9k | 0.5k |
| `smoke` | 602s | 18 | 47k | 22k |
| `seed` | 55s | 3 | 4.5k | 1.6k |
| `screens` | 708s | 33 | 56k | 22k |
| `ui` | 81s | 2 | 6.9k | 3.6k |
| `repair` | 20s | 3 | 1.7k | 0.2k |

The shape of that column is the finding. Two passes account for **88% of the
wall clock and 87% of the tokens**, and they are the two where the model went
away and checked itself — 18 and 33 turns against 2 or 3 everywhere else. The
plan's chosen metric would have recorded this run as "one repair attempt",
which is true and which hides a factor of thirty.

Beside it, the same spec through the **real web pipeline with `--backend
offline`**: five passes, `docker compose up --build`, the health wait, the
smoke suite and the browser stage, **green first time in 20 seconds** with no
model calls. That is not a comparison — it is the harness's own end-to-end
proof that the web half works. It does settle one thing worth knowing before
starting: **Docker is not the slow part.** Whatever the terminal target saves,
it does not save that.

Extrapolating: budget **10–25 minutes per run and two to three hours for all
six**, dominated entirely by how often a pass decides to go and check its own
work. Runs are independent, so stop after any of them and re-run only that one.

## The one failure so far was not about Textual

Worth reading before the six, because it is the whole argument for keeping the
failure text rather than the failure count. The single red stage in that run
was `import`, and the cause was this, in `app/models.py`:

```
from sqlalchemy.orm import Mapped, мapped_column, relationship
ImportError: cannot import name 'мapped_column' from 'sqlalchemy.orm'
```

A Cyrillic `м` (U+043C) in one identifier. The repair pass found it in 20
seconds and fixed exactly that character. It is a decoding glitch, it is
orthogonal to the target, and the *same prompt* had produced a clean
`models.py` in an earlier run — so counted as a number it reads as "the
terminal target needed a repair", which is false. Classify against the text.

## Three things the plan under-reads, found while building this

Recorded here because they change Phase 2's cost estimate whichever way Phase 1
falls, and they were found by building rather than by reading.

1. **Phase 1 cannot be run without a terminal skeleton.** The plan describes the
   spike as five prompts and a boot, but every pass prompt is written *against*
   a fixed tree — it names the modules the generated code imports — and
   `App.run_test` needs something to run. So `skeleton/` here is a fifth of
   Phase 3, built early and thrown away. It is small (five files, ~150 lines)
   and that smallness is itself a finding in the target's favour: the web
   skeleton is 24 files.

2. **The archetype brief is target-coupled, and Phase 2's table says it is
   not.** That table lists four things a target owns — skeleton, pass tuple,
   allowed paths, verifier — and the archetype axis is described as untouched.
   Both shipped archetype fragments are written in web: "in the same browser",
   "a grid of plain submit buttons inside one form", "draw the pieces as inline
   SVG". Handing either to a Textual pass measures the model resolving a
   contradiction. So a target owns a **fifth** thing, and it is the one that
   multiplies: it is a fragment per archetype × target, not one per target.

3. **`limits` is target-coupled too**, for the same underlying reason and one
   layer earlier. It is intake's record of what *the fixed stack* cannot do, and
   the fixed stack is exactly what the target axis changes — so the real
   kitten-chess spec says the players "take turns at the same browser". That is
   in a `spec.json` written before any of this, which means Phase 2's promise
   that an old spec "loads and generates the app it always did" is true for the
   web target and quietly false for any other one.
