"""`proto console` — the tool's own terminal front end.

**Not the `tui` target.** That is what `proto` emits; this is what `proto` is.
The two are adjacent in every way that matters, which is why nothing in this
package is called `tui` anything: `targets/tui.py`, `passes/tui/`,
`baseline_tui.py`, `verify_tui.py` and `tui_probe.py` all already mean the
other one.

A second view over `protopilot/jobs.py`, not a second pipeline. The generation
it runs is `protopilot.generation.run_generation`, the same function the web
front end wraps — so a change to the pipeline reaches both front ends or
neither, and neither front end can drift into being the reference.

The two panes are the point: an idea goes in on the left, and the right fills
while it runs. It fills *as it goes* — measured, not assumed. `job.lines` grows
during a generation and the `redirect_stdout` buffer stays empty, so the log
pane is never dark waiting on a flush; the longest it sits still is one pass,
with that pass named on screen throughout.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static

from protopilot import archetypes, generation, targets
from protopilot.console.progress import fold, lines
from protopilot.jobs import STORE, JobStore

#: How often the panes re-read the job. A generation is a minutes-long
#: operation whose fastest interesting event is a pass boundary, so this is
#: about redraw smoothness rather than about not missing anything -- the job's
#: lists are append-only and nothing is lost between ticks.
TICK = 0.2


class ConsoleApp(App):
    """Two panes over one job store."""

    CSS_PATH = "console.tcss"
    TITLE = "proto.pilot"
    BINDINGS = [("ctrl+r", "start", "Generate"), ("ctrl+q", "quit", "Quit")]

    def __init__(
        self,
        workspace: Path,
        backend: str | None = None,
        demo: bool = True,
        store: JobStore | None = None,
        runner=None,
    ) -> None:
        super().__init__()
        self.workspace = Path(workspace)
        self.backend = backend
        self.demo = demo
        # Injected so the suite can drive the console without generating, and
        # so a second console in one process does not share a store by
        # accident. Defaults to the process-wide one the web front end uses.
        self.store = store if store is not None else STORE
        self._run = runner or generation.run_generation
        self.job = None
        self._shown = 0
        self._last_status = ""

    # -- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="panes"):
            with Vertical(id="input-pane"):
                yield Label("What do you want to build?")
                yield Input(placeholder="a tiny notes app for one person", id="idea")
                yield Label("Direction (optional)")
                yield Input(placeholder="calm, keyboard-first", id="direction")
                yield Label("Target")
                yield Select(
                    [(name, name) for name in targets.names()],
                    value=targets.DEFAULT,
                    allow_blank=False,
                    id="target",
                )
                yield Label("Archetype")
                yield Select(
                    [(name, name) for name in archetypes.names()],
                    value=archetypes.DEFAULT,
                    allow_blank=False,
                    id="archetype",
                )
                yield Button("Generate", variant="primary", id="start")
                yield Static("", id="status")
                yield Label("Recent")
                yield Static("nothing yet", id="jobs")
            with Vertical(id="output-pane"):
                with VerticalScroll(id="progress-scroll"):
                    yield Static("Nothing running.", id="progress")
                yield RichLog(id="log", wrap=True, markup=False, max_lines=5000)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(TICK, self.refresh_panes)
        self.query_one("#idea", Input).focus()

    # -- running ----------------------------------------------------------

    def action_start(self) -> None:
        """Start a generation, or say why not.

        **One at a time, and refused by name.** `JobStore.run` wraps its work in
        `redirect_stdout`, and `sys.stdout` is process-global -- two jobs on two
        threads clobber each other's capture. Until that is per-job (Phase 5 of
        the plan) a second generation would interleave two transcripts into one
        pane with nothing marking the seam. A queue is honest; a silent
        interleave is not, and this is the cheap half of that fix.
        """
        if self.busy:
            self.set_status(f"still generating {self.job.idea!r} — one at a time for now")
            return
        idea = self.query_one("#idea", Input).value.strip()
        if not idea:
            self.set_status("an idea first")
            return

        target = str(self.query_one("#target", Select).value)
        archetype = str(self.query_one("#archetype", Select).value)
        try:
            targets.check_pair(target, archetype)
        except targets.UnsupportedPair as exc:
            # Before anything is spent, which is where the CLI checks it too.
            self.set_status(str(exc))
            return

        job = self.store.create(idea, self.query_one("#direction", Input).value.strip())
        job.archetype = archetype
        self.job = job
        self._shown = 0
        self._last_status = job.status
        self.query_one("#log", RichLog).clear()
        self.set_status(f"generating in {self.workspace}")
        self.store.run(
            job,
            lambda j: self._run(j, self.workspace, target=target, backend=self.backend, demo=self.demo),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("idea", "direction"):
            self.action_start()

    @property
    def busy(self) -> bool:
        return self.job is not None and self.job.status in ("pending", "running")

    # -- drawing ----------------------------------------------------------

    #: How many past runs the list shows. Being able to compare the last few
    #: ideas is most of what a job list is for; a scrolling history of every
    #: run this process ever started is a different feature.
    RECENT = 6

    def recent(self) -> str:
        """The last few runs, newest first, from the store rather than from a
        list this app keeps for itself — so a job started elsewhere in the same
        process (the web front end shares `STORE`) shows up here too."""
        marks = {"done": "✓", "failed": "✗", "running": "▸", "pending": "·"}
        rows = []
        for job in self.store.all()[: self.RECENT]:
            idea = job.idea if len(job.idea) <= 26 else job.idea[:25] + "…"
            here = " ←" if self.job is not None and job.id == self.job.id else ""
            rows.append(f"{marks.get(job.status, '·')} {idea}{here}")
        return "\n".join(rows)

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def refresh_panes(self) -> None:
        """One tick: append what is new, redraw what is derived.

        The log is appended to rather than rewritten because `job.lines` is
        append-only and a RichLog that is cleared and refilled every 200ms
        loses the reader's scroll position -- which, on a twenty-minute run, is
        the only thing they have.
        """
        job = self.job
        if job is None:
            return
        # A timer callback can outlive the screen it draws to: `set_interval`
        # keeps firing while the app tears down, and the widgets are gone by
        # then. `query_one` raises `NoMatches` there, from a background tick,
        # where the traceback is attributed to nothing the reader did. Asking
        # whether the pane exists is cheaper than explaining that.
        panes = self.query("#log")
        if not panes:
            return
        log = self.query_one("#log", RichLog)
        for line in job.lines[self._shown :]:
            log.write(line)
        self._shown = len(job.lines)

        text = "\n".join(lines(fold(job.events)))
        self.query_one("#progress", Static).update(text or "starting...")
        self.query_one("#jobs", Static).update(self.recent() or "nothing yet")

        # **On transitions only.** This used to write the status line every
        # tick, which silently ate anything else that line had to say: the
        # "one at a time" refusal was set by the button and overwritten 200ms
        # later by "generating ...", so declining a second run looked exactly
        # like a button that does nothing. Found by the test for the refusal,
        # not by the test for the status.
        if job.status == self._last_status:
            return
        self._last_status = job.status
        if job.status == "failed":
            # The floor, in the pane and not only on disk.
            self.set_status(f"failed: {job.error}")
        elif job.status == "done":
            self.set_status(f"finished — {job.project_dir}" if job.project_dir else "finished")


def run(workspace: Path, backend: str | None = None, demo: bool = True) -> None:
    """Launch the console. Called by `proto console` and nothing else."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    ConsoleApp(workspace, backend=backend, demo=demo).run()
