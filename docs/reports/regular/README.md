# In-Flight Reports

Each file here describes the **current window**: `<latest release tag>..HEAD`.
A release closes the window and freezes the edition under
[`../releases/`](../releases/README.md).

The window is resolved from one place — `scripts/docs/release_window.py` — and
stamped onto every report as frontmatter plus a prose line under the H1.
`pp check reports` validates every anchor and blocks CI.

| Report | Cadence | Produced by |
| ------ | ------- | ----------- |
| `repository-report.md` | Sat 22:00 America/Chicago | `pp report repo-report` |

<!-- One row per scheduled report. A report with no owner here is one that is
     refreshed by hand or never — the exact condition anchoring exists to make
     visible. -->

**Nothing is installed in a crontab yet.** The `agentic` tier was taken on
2026-09-01 for its primitives — the job registry, the run ledger and its two
rails, `fix_policy` — which the prototype improvement loop was to be built on.
That plan was [dropped](../../implementations/dropped/improvement-loop.md) on
2026-11-11, never built, when prototyping was removed.
The schedule above is *registered*, not *running*: `pp report cron --print`
emits the block, and `pp report cron --check` will disagree with the live
crontab until somebody installs it. That gap is deliberate and should stay
visible rather than being papered over by deleting the row.

**Cadence did not change when anchoring landed.** A weekly job still runs
weekly; only the window it describes moved from "since this last ran" to "since
the last release". Never defer a scheduled report until a release is cut.
