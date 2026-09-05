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
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static, TabbedContent, TabPane

from protopilot import archetypes, generation, targets
from protopilot.console.progress import fold, lines
from protopilot.console.review import ReviewScreen
from protopilot.jobs import STORE, JobStore

#: How often the panes re-read the job. A generation is a minutes-long
#: operation whose fastest interesting event is a pass boundary, so this is
#: about redraw smoothness rather than about not missing anything -- the job's
#: lists are append-only and nothing is lost between ticks.
TICK = 0.2

#: Shown before a run has produced a screen, and again at the start of the
#: next one. Says what this pane is for and what it cannot do, because the
#: obvious expectation of a pane called Preview is a running app.
NO_PREVIEW = (
    "No preview yet.\n\n"
    "Once a terminal prototype verifies, the screen it painted is shown here -- "
    "a picture of the generated app, not the app itself.\n\n"
    "To use it, run the command shown when the generation finishes."
)


class ConsoleApp(App):
    """Two panes over one job store."""

    CSS_PATH = "console.tcss"
    TITLE = "proto.pilot"
    BINDINGS = [
        ("ctrl+r", "start", "Generate"),
        ("ctrl+p", "preview", "Preview"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        workspace: Path,
        backend: str | None = None,
        demo: bool = True,
        store: JobStore | None = None,
        runner=None,
        review: bool = True,
    ) -> None:
        super().__init__()
        self.workspace = Path(workspace)
        self.backend = backend
        self.demo = demo
        # Injected so the suite can drive the console without generating, and
        # so a second console in one process does not share a store by
        # accident. Defaults to the process-wide one the web front end uses.
        self.store = store if store is not None else STORE
        # The two halves separately, so the review screen can sit between them.
        # `runner` overrides the whole-run path and is what the suite injects;
        # when it is given the checkpoint is skipped, because a fake runner has
        # no spec to review.
        self._run = runner
        self._assemble = generation.assemble
        self._build = generation.build
        self.review = review and runner is None
        self.job = None
        self.spec = None
        #: idle | assembling | reviewing | building
        self.phase = "idle"
        self._shown = 0
        self._last_status = ""
        self._preview = ""

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
                # Two tabs rather than a third region. Everything above
                # describes the *build*; the preview is the only thing that
                # shows what was built, and the two want the same space at
                # different moments -- the log while it runs, the screen once
                # it is green.
                with TabbedContent(id="views"):
                    with TabPane("Output", id="tab-log"):
                        yield RichLog(id="log", wrap=True, markup=False, max_lines=5000)
                    with TabPane("Preview", id="tab-preview"):
                        yield Static(NO_PREVIEW, id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(TICK, self.refresh_panes)
        self.query_one("#idea", Input).focus()

    # -- running ----------------------------------------------------------

    def action_start(self) -> None:
        """Start a generation, or say why not.

        **One at a time, and refused by name.** The reason changed and the
        behaviour did not, which is worth saying plainly: this began as a guard
        around `JobStore.run`'s process-global `redirect_stdout`, where two
        jobs genuinely braided each other's output. That is fixed -- capture is
        per-thread now -- so what remains is a *view* constraint rather than a
        correctness one. These panes show one run: one log, one progress
        region, one answer to "what is happening". A second concurrent
        generation would need somewhere to put it, and that is a different
        feature from being allowed to have one.

        Refused **by name**, either way. A button that silently does nothing is
        indistinguishable from one that is broken.
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
        self.spec = None
        self.target = target
        self._shown = 0
        self._last_status = job.status
        self._preview = ""
        self.query_one("#log", RichLog).clear()
        self.query_one("#views", TabbedContent).active = "tab-log"
        # The widget too, not only the guard. Resetting `_preview` alone
        # switched the tab back and left the previous idea's screenshot sitting
        # in it -- a picture of something that is not what is being generated,
        # which is worse than no picture.
        self.query_one("#preview", Static).update(NO_PREVIEW)

        if self._run is not None:
            # An injected whole-run path: no spec to review, so no checkpoint.
            self.phase = "building"
            self.set_status(f"generating in {self.workspace}")
            self.store.run(
                job,
                lambda j: self._run(j, self.workspace, target=target, backend=self.backend, demo=self.demo),
            )
            return

        if not self.review:
            self.phase = "building"
            self.set_status(f"generating in {self.workspace}")
            self.store.run(job, lambda j: self._whole_run(j, target))
            return

        self.phase = "assembling"
        self.set_status("reading the idea...")
        self.store.run(job, lambda j: self._assemble_into(j, target))

    def _assemble_into(self, job, target: str) -> None:
        """Intake, on the job's thread. The spec is kept for the review screen."""
        self.spec = self._assemble(job, backend=self.backend, target=target)

    def _whole_run(self, job, target: str) -> None:
        """Both halves with nobody asked, for `--no-review`."""
        spec = self._assemble(job, backend=self.backend, target=target)
        self._build(job, self.workspace, spec, backend=self.backend, demo=self.demo)

    # -- the checkpoint ---------------------------------------------------

    def open_review(self) -> None:
        """Show the spec and wait for an answer.

        Pushed from the timer rather than from the worker thread: a Textual
        screen must be mounted on the app's own event loop, and a thread that
        pushed one directly would be mutating the widget tree from outside it.
        The timer already runs there and already watches for the phase change.
        """
        spec = self.spec
        if spec is None:  # intake produced nothing to review
            self.phase = "idle"
            self.set_status("nothing to review")
            return
        self.phase = "reviewing"
        destination = str(Path(self.workspace) / spec.slug)
        self.push_screen(ReviewScreen(spec.summary(), destination), self.answer_review)

    def answer_review(self, approved: bool | None) -> None:
        """What the checkpoint is for, in both directions."""
        job = self.job
        if job is None or self.spec is None:
            self.phase = "idle"
            return
        if not approved:
            # Nothing has been written, so there is nothing to undo. The
            # transcript stays: what intake produced is worth reading even when
            # the answer is no, and it is what a person changes their idea from.
            self.phase = "idle"
            self.set_status("declined — nothing was generated")
            return
        self.phase = "building"
        self._last_status = "pending"
        self.set_status(f"generating in {self.workspace}")
        spec = self.spec
        self.store.run(job, lambda j: self._build(j, self.workspace, spec, backend=self.backend, demo=self.demo))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("idea", "direction"):
            self.action_start()

    @property
    def busy(self) -> bool:
        """Anything in flight, **including a review waiting to be answered.**

        Asked of the phase rather than of `job.status`, because the job is
        `done` while the review screen is open — intake finished, and nothing
        after it has started. A `job.status` reading would call that idle and
        let a second generation start underneath the modal.
        """
        return self.phase != "idle"

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

    def action_preview(self) -> None:
        """Toggle between the log and the generated app's screen."""
        views = self.query_one("#views", TabbedContent)
        views.active = "tab-log" if views.active == "tab-preview" else "tab-preview"

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

        progress = fold(job.events)
        text = "\n".join(lines(progress))
        self.query_one("#progress", Static).update(text or "starting...")
        self.query_one("#jobs", Static).update(self.recent() or "nothing yet")

        if progress.screen and progress.screen != self._preview:
            self._preview = progress.screen
            self.query_one("#preview", Static).update(progress.screen)
            # Switched to once, on arrival. Not on every tick: a reader who
            # tabbed back to the log to read a repair would be yanked away
            # again 200ms later, which is the same class of bug as the status
            # line that rewrote itself over its own message.
            self.query_one("#views", TabbedContent).active = "tab-preview"

        # **On transitions only.** This used to write the status line every
        # tick, which silently ate anything else that line had to say: the
        # "one at a time" refusal was set by the button and overwritten 200ms
        # later by "generating ...", so declining a second run looked exactly
        # like a button that does nothing. Found by the test for the refusal,
        # not by the test for the status.
        if job.status == self._last_status:
            return
        self._last_status = job.status
        if job.status not in ("done", "failed"):
            return

        if job.status == "failed":
            # The floor, in the pane and not only on disk. Whichever half
            # raised -- a failed intake is as final as a failed pass, and the
            # phase has to leave "assembling" either way or the console is
            # busy forever.
            self.phase = "idle"
            self.set_status(f"failed: {job.error}")
        elif self.phase == "assembling":
            # Intake finished. This is the checkpoint, and it is opened from
            # here because a screen must be mounted on the app's event loop.
            self.open_review()
        else:
            self.set_status(f"finished — {job.project_dir}" if job.project_dir else "finished")
            self.phase = "idle"


def run(workspace: Path, backend: str | None = None, demo: bool = True) -> None:
    """Launch the console. Called by `proto console` and nothing else."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    ConsoleApp(workspace, backend=backend, demo=demo).run()
