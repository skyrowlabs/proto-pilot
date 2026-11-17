# Examples — real plans, committed whole

Each example is one real `proto plan` run, kept as the tree it wrote, beside a
walkthrough that reads it end to end. The README's bakery and tool library were
invented to show the shape of a run; these are runs whose output nobody wrote by
hand.

| Example | Run | One line |
| ------- | --- | -------- |
| [Squirrel survival](squirrel-survival.md) | 2026-11-16, `claude-code`, researched | A small 2D survival game, every field of the brief filled in, and what the plan made of it |

## What an example is for

- **A stranger's first look at real output.** A finding with a source, a dream
  set aside with its reason, a step that depends on the topic it names.
- **The input, spelled out.** Every example states its full command, so it can be
  read as a worked use of the brief flags (`--goal`, `--for`, `--horizon`,
  `--must`, `--not`).
- **Use, written down.** [living-plans](../TODO/living-plans.md) Phase 1 asks for
  real ideas run through the pipeline and what was missing noted. Each
  walkthrough ends with that list.

## Rules for the trees

- **The tree is committed as it was written, minus its research transcripts.**
  The plan's data (for example `squirrel_survival/.protopilot/plan.json`) and
  every page stay byte for byte. The transcripts in
  `.protopilot/research/` are left out because they fingerprint the machine that
  ran them (home paths, installed skills and plugins; see
  [#51](https://github.com/skyrowlabs/proto-pilot/issues/51)). The pages already
  show every citation. The cost is that a re-render of a committed tree goes red
  (*Not researched*, *Not verified*, a `RUNBOOK.md`, exit 1), since the ledger
  believes only transcripts it can hash. That is the right answer for a tree
  whose evidence is not there, and the reason never to rerun one in place.
- **Never hand-edit a rendered page.** A re-render overwrites it. A correction
  goes in the walkthrough, which is prose and is ours.
- **An example is a snapshot, not a fixture.** No test reads these trees; the
  offline baseline is what the suite runs. A rerun of the same command writes a
  different plan, because the model and the web both change, so an example is
  replaced, never patched.
