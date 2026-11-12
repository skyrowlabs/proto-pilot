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
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static, TabbedContent, TabPane

from protopilot import archetypes, generation, targets
from protopilot.console.review import ReviewScreen
from protopilot.console.session import PreviewSession
from protopilot.console.splitter import Splitter
from protopilot.console.theme import SKYROW
from protopilot.jobs import STORE, JobStore
from protopilot.progress import fold, lines

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
    "Once a terminal prototype verifies, the screen it painted is shown here.\n\n"
    "ctrl+l runs the prototype live in this pane: keys go to it, and it is "
    "rebuilt from whatever is on disk each time you press it."
)

#: How often a live session is asked for its current frame. An app driving
#: itself from `set_interval` has moved on between calls, so this is the
#: preview's frame rate; a still app costs one round trip and returns the same
#: screen. Faster than `TICK` because this is the only thing here that animates.
LIVE_TICK = 0.1


class PreviewPane(Static):
    """The preview, made focusable so it can be typed into.

    A `Static` cannot take focus by default, which is right for a label and
    wrong for something you are meant to drive. Focus is what separates "the
    idea box has my keystrokes" from "the prototype does", and it is a
    distinction the reader can see rather than one they have to remember.
    """

    can_focus = True


class ConsoleApp(App):
    """Two panes over one job store."""

    CSS_PATH = "console.tcss"
    TITLE = "proto.pilot"
    BINDINGS = [
        ("ctrl+r", "start", "Generate"),
        # Priority for the same reason the resize chords are: `Input` binds
        # `ctrl+e` for end-of-line and a focused widget beats an app binding,
        # so this did nothing whenever any text box had focus -- which is
        # always, since the change box is one. `end` still goes to the end of
        # a line; nothing else here reaches the iterate loop.
        Binding("ctrl+e", "apply_change", "Apply change", priority=True),
        ("ctrl+p", "preview", "Preview"),
        ("ctrl+l", "live", "Run live"),
        ("ctrl+y", "copy_path", "Copy path"),
        # Both roads to the same place: a terminal with mouse reporting off,
        # or a multiplexer that eats drags, still resizes.
        #
        # **`priority=True`, and it is a trade rather than a detail.** `Input`
        # binds `ctrl+left`/`ctrl+right` for word movement and a focused widget
        # beats an app binding, so without this these did nothing at all
        # whenever the idea box had focus -- which is on startup and after
        # every run. A layout control that only works when nothing is focused
        # is not a layout control. What it costs is word-jumping inside a
        # single-line input, which the arrow keys still do one character at a
        # time; what it buys is a resize that works wherever you are.
        Binding("ctrl+left", "narrow", "Narrower", priority=True),
        Binding("ctrl+right", "widen", "Wider", priority=True),
        Binding("ctrl+up", "shorter", "Shorter", priority=True),
        Binding("ctrl+down", "taller", "Taller", priority=True),
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
        self._amend = generation.amend
        self.review = review and runner is None
        self.job = None
        self.spec = None
        #: idle | assembling | reviewing | building
        self.phase = "idle"
        self._shown = 0
        self._last_status = ""
        self._preview = ""
        self.session: PreviewSession | None = None

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

                # The iterate loop. Under its own heading naming the prototype
                # being changed, because "apply this change" is meaningless
                # without "to what" -- and the failure it prevents is the one
                # that made this exist: refining an idea by generating a fourth
                # tree beside three abandoned ones.
                yield Label("Change", id="change-label")
                yield Static("nothing loaded", id="loaded")
                yield Input(placeholder="add a score counter", id="change")
                yield Button("Apply change", id="apply")

                yield Label("Recent")
                yield Static("nothing yet", id="jobs")
            yield Splitter("#input-pane", axis="width", minimum=24, maximum=90, id="split-panes")
            with Vertical(id="output-pane"):
                with VerticalScroll(id="progress-scroll"):
                    yield Static("Nothing running.", id="progress")
                yield Splitter("#progress-scroll", axis="height", minimum=3, maximum=60, id="split-rows")
                # Two tabs rather than a third region. Everything above
                # describes the *build*; the preview is the only thing that
                # shows what was built, and the two want the same space at
                # different moments -- the log while it runs, the screen once
                # it is green.
                with TabbedContent(id="views"):
                    with TabPane("Output", id="tab-log"):
                        yield RichLog(id="log", wrap=True, markup=False, max_lines=5000)
                    with TabPane("Preview", id="tab-preview"):
                        # Scrollable in **both** directions. A live session is
                        # resized to this pane so it usually fits exactly, but
                        # two cases do not: the still screenshot, which the
                        # verifier renders at a fixed 100x30 and which is not
                        # ours to re-render; and a pane smaller than an app can
                        # lay out in, where the stream floors the size and
                        # sends a frame bigger than the space. Scrolling a
                        # frame that does not fit is honest; silently cropping
                        # one is not.
                        with ScrollableContainer(id="preview-scroll"):
                            yield PreviewPane(NO_PREVIEW, id="preview")
        yield Footer()

    def on_mount(self) -> None:
        # Registered and selected here rather than via a class attribute,
        # because a theme has to exist before it can be named.
        self.register_theme(SKYROW)
        self.theme = SKYROW.name
        self.set_interval(TICK, self.refresh_panes)
        # Its own timer, and faster: this one is the preview's frame rate and
        # has nothing to do with how often a job's log is drained.
        self.set_interval(LIVE_TICK, self.refresh_live)
        self.query_one("#idea", Input).focus()

    def refresh_live(self) -> None:
        """One frame from the running prototype, if there is one."""
        session = self.session
        if session is None:
            return
        if not self.query("#preview"):
            return
        pane = self.query_one("#preview", PreviewPane)
        # Ask for the app to be laid out at the size it is being shown at.
        # Cheap and idempotent: the session drops a resize to the size it is
        # already at, so this is a comparison per tick and nothing more.
        region = self.query_one("#preview-scroll").content_size
        if region.width and region.height:
            session.resize(region.width, region.height)
        if not session.alive:
            if session.error:
                pane.update(f"{session.error}\n\nctrl+l to rebuild and try again.")
                self.session = None
            return
        session.tick()
        if session.frame:
            body = session.frame
            if session.error:
                # A key that raised is a finding about the generated app, not a
                # reason to blank the screen it was raised from.
                body = f"{session.frame}\n\n! {session.error}"
            pane.update(body)

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

    # -- iterating on what is already there -------------------------------

    def action_apply_change(self) -> None:
        """Change the loaded prototype rather than generating another one.

        The whole point: a person refining an idea wants the thing they have to
        become the thing they meant. Generating afresh from a longer sentence
        throws away everything the last run got right and costs the full
        twenty-one minutes to find out whether the new sentence was better.

        The change runs on the **same job**, so the transcript is continuous —
        one prototype, its history in one log — and there is no review
        checkpoint, because the spec being amended is one that was already
        approved and the change itself is the approval.
        """
        if self.busy:
            self.set_status("still working\none at a time for now")
            return
        directory = self.loaded
        if not directory:
            self.set_status("nothing loaded\ngenerate something first")
            return
        change = self.query_one("#change", Input).value.strip()
        if not change:
            self.set_status("say what to change")
            return

        job = self.job
        if job is None:
            return
        self.phase = "building"
        self._last_status = "pending"
        self._preview = ""
        self.set_status(f"changing {Path(directory).name}")
        self.query_one("#change", Input).value = ""
        self.store.run(
            job,
            lambda j: self._amend(j, Path(directory), change, backend=self.backend, demo=self.demo),
        )

    @property
    def loaded(self) -> str:
        """The prototype a change would be applied to, or "".

        Read from the job rather than kept as a second field: `project_dir` is
        set by the runner when a tree is actually written, so this cannot claim
        a prototype that a declined review or a failed intake never made.
        """
        job = self.job
        return job.project_dir if job and job.project_dir else ""

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
        elif event.button.id == "apply":
            self.action_apply_change()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("idea", "direction"):
            self.action_start()
        elif event.input.id == "change":
            self.action_apply_change()

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

    # -- the live preview -------------------------------------------------

    def action_live(self) -> None:
        """Run the generated prototype in the pane, or rebuild it if it is
        already running.

        **Restart is the refresh.** There is no "reload" that is cheaper or
        more truthful: the app is a process holding its own state, and what a
        reader means by "show me the current one" is the tree as it is on disk
        now. Pressing this again after editing generated code, or after
        `proto add`, shows the change.
        """
        job = self.job
        directory = job.project_dir if job else ""
        if not directory or not Path(directory).is_dir():
            self.set_status("nothing generated yet to run")
            return

        self.query_one("#views", TabbedContent).active = "tab-preview"
        self.set_status(f"starting {Path(directory).name}...")
        session = self.session or PreviewSession(Path(directory))
        session.project_dir = Path(directory)
        self.session = session
        session.start()
        # Focused, because a preview you have to click before it takes a key
        # reads as one that ignores keys.
        self.query_one("#preview", PreviewPane).focus()

    def on_key(self, event) -> None:
        """Forward keystrokes to a live prototype, when one has focus.

        **`ctrl+`-anything is never forwarded**, and that is the whole of the
        rule. The console's own bindings all live there, so the reader keeps a
        way out — to quit, to switch tabs, to rebuild — that no generated app
        can capture by binding it first. Everything else belongs to the app
        being previewed, because a preview that swallows `q` is not showing you
        the thing you asked to see.
        """
        session = self.session
        if session is None or not session.alive:
            return
        if not isinstance(self.focused, PreviewPane):
            return
        if event.key.startswith("ctrl+"):
            return
        event.stop()
        event.prevent_default()
        session.press(event.key)

    def on_unmount(self) -> None:
        """A subprocess outliving the console is a prototype nobody can see and
        nobody can stop."""
        if self.session is not None:
            self.session.stop()

    # -- resizing ---------------------------------------------------------

    def action_narrow(self) -> None:
        self.query_one("#split-panes", Splitter).nudge(-4)

    def action_widen(self) -> None:
        self.query_one("#split-panes", Splitter).nudge(4)

    def action_shorter(self) -> None:
        self.query_one("#split-rows", Splitter).nudge(-2)

    def action_taller(self) -> None:
        self.query_one("#split-rows", Splitter).nudge(2)

    def action_copy_path(self) -> None:
        """Put the generated tree's path on the clipboard.

        A terminal UI captures the mouse, so the usual answer -- select it and
        drag -- does not work, and the path is the one string from a run that a
        person needs *outside* the console. Textual copies over OSC 52, which
        the terminal forwards, so this works over ssh as well.
        """
        job = self.job
        directory = job.project_dir if job else ""
        if not directory:
            self.set_status("nothing generated yet")
            return
        self.copy_to_clipboard(directory)
        # Named, and not just "copied": a clipboard write that silently went to
        # the wrong tree is indistinguishable from one that worked.
        self.set_status(f"copied {Path(directory).name}")

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
        # **Every widget this method touches, checked before any of it runs.**
        # A timer callback sees the tree in two states it must survive: partly
        # mounted, because `TabbedContent` brings its panes up asynchronously
        # and the first ticks land in the middle of that; and partly gone,
        # because `set_interval` keeps firing while the app tears down. Either
        # way `query_one` raises `NoMatches` from a background tick, where the
        # traceback is attributed to nothing the reader did.
        #
        # Checking one id was enough until the log moved inside a tab, and then
        # it was not: `#log` mounted first and `#progress` was reached a line
        # later, in the same frame, before it existed. A guard that names fewer
        # widgets than the body uses is a guard with a window in it.
        needed = ("#log", "#progress", "#jobs", "#preview", "#views")
        if any(not self.query(name) for name in needed):
            return
        log = self.query_one("#log", RichLog)
        for line in job.lines[self._shown :]:
            log.write(line)
        self._shown = len(job.lines)

        progress = fold(job.events)
        text = "\n".join(lines(progress))
        self.query_one("#progress", Static).update(text or "starting...")
        self.query_one("#jobs", Static).update(self.recent() or "nothing yet")
        loaded = self.loaded
        self.query_one("#loaded", Static).update(
            f"{progress.name or Path(loaded).name}\n{Path(loaded).name}" if loaded else "nothing loaded"
        )

        # A live session outranks the screenshot: it is the same app, now, with
        # its own state, and drawing the still one over it would replace what
        # the reader is driving with a picture of how it started.
        if self.session is not None and self.session.alive:
            pass
        elif progress.screen and progress.screen != self._preview:
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
            self.query_one("#progress-scroll", VerticalScroll).scroll_end(animate=False)
        elif self.phase == "assembling":
            # Intake finished. This is the checkpoint, and it is opened from
            # here because a screen must be mounted on the app's event loop.
            self.open_review()
        else:
            # **Short on purpose, and measured.** This pane is 34 columns wide
            # and 29 after its padding; an absolute path is comfortably longer,
            # so putting one here clipped it into something that could be
            # neither read nor retyped. The path belongs in the wide pane on
            # the right, where it is; what belongs here is how to get hold of
            # it -- on two lines, because the one-line version was 33.
            self.set_status("finished\nctrl+y copies the path" if job.project_dir else "finished")
            # The path and the run command are the last lines of a region that
            # scrolls, so on a short terminal they finish below the fold --
            # written, correct, and invisible.
            self.query_one("#progress-scroll", VerticalScroll).scroll_end(animate=False)
            self.phase = "idle"


def run(workspace: Path, backend: str | None = None, demo: bool = True) -> None:
    """Launch the console. Called by `proto console` and nothing else."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    ConsoleApp(workspace, backend=backend, demo=demo).run()
