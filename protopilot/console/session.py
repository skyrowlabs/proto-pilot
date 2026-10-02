"""A live preview: the generated app, running, driven from the console.

Owns one `protopilot/tui_stream.py` subprocess and the two threads that talk to
it. The console asks for frames on its own timer and forwards keystrokes; what
comes back is the app's real screen with its real state, not a re-render of a
saved one.

**The environment comes from `TuiVerifier.env()`**, not from a second copy of
it here. `PYTHONPATH`, a fresh `APP_DB`, `PYTHONDONTWRITEBYTECODE` and the two
`TERM`/`NO_COLOR` settings are four separate things that can each be wrong, and
the verifier already got them right — a preview booting the tree differently
from the way it was verified would show a screen nobody has checked.

A fresh database per session is deliberate rather than incidental: the tree has
no migrations, so a preview reusing the last run's file would render this
model against the previous one's schema.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

#: The driver, beside the probe it is the live counterpart of.
STREAM = Path(__file__).resolve().parents[1] / "tui_stream.py"


class PreviewSession:
    """One running prototype, behind a pipe.

    Every public method is safe to call from the console's event loop: nothing
    here blocks on the child, and the reader lives on its own thread. What the
    console reads is `frame`, `error` and `alive`, which are plain attributes
    updated by that thread — a queue would buy ordering this does not need,
    since only the newest frame is ever drawn.
    """

    def __init__(self, project_dir: Path, python: str | None = None, stream: Path | None = None) -> None:
        self.project_dir = Path(project_dir)
        self.python = python or sys.executable
        self.stream = Path(stream) if stream else STREAM
        self.frame = ""
        self.error = ""
        self.frames = 0
        self.ready = False
        #: What the app is currently rendered at. `None` until the first
        #: resize, so the opening frame is the stream's own default and
        #: comparable with the verifier's.
        self.size: tuple[int, int] | None = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Boot the app. Restarting is how "rebuild and show me" is spelled.

        Stopping first, unconditionally: a session left running against the
        previous tree would go on answering with frames from an app that is no
        longer the one on disk, which is the stale-screenshot failure again
        with a heartbeat.
        """
        self.stop()
        from protopilot.verify_tui import TuiVerifier

        env = TuiVerifier(self.project_dir).env()
        self.frame = ""
        self.error = ""
        self.frames = 0
        self.ready = False
        self.size = None
        try:
            self._proc = subprocess.Popen(  # noqa: S603 -- argv is ours, never the model's
                [self.python, str(self.stream)],
                cwd=str(self.project_dir),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self.error = f"could not start the preview: {exc}"
            return
        threading.Thread(target=self._read, daemon=True).start()

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        self.ready = False
        if proc is None:
            return
        try:
            self._write(proc, {"quit": True})
            proc.wait(timeout=2)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            # Asked nicely first; a generated app that ignores it is exactly
            # the kind this exists to survive.
            proc.kill()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # -- talking to it ----------------------------------------------------

    def press(self, key: str) -> None:
        self._request({"key": key})

    def resize(self, width: int, height: int) -> None:
        """Render the app at this size from now on.

        The console calls this when its preview pane changes shape, so the
        prototype lays itself out for the space it is being shown in. Without
        it the app renders at a fixed size and the pane scrolls a picture of a
        terminal that is not the one in front of anybody.
        """
        if (width, height) == self.size:
            return
        self.size = (width, height)
        self._request({"resize": [width, height]})

    def tick(self) -> None:
        """Ask for the current frame.

        This is what makes an animated app animate: the console calls it on a
        timer, and an app driving itself from `set_interval` has moved on
        between calls. Nothing is sent to the app, so a still app costs one
        round trip and returns the same screen.
        """
        self._request({"frame": True})

    def _request(self, payload: dict) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        self._write(proc, payload)

    def _write(self, proc: subprocess.Popen, payload: dict) -> None:
        with self._lock:
            try:
                assert proc.stdin is not None
                proc.stdin.write(json.dumps(payload) + "\n")
                proc.stdin.flush()
            except (OSError, ValueError):
                # The child died between the liveness check and the write.
                # Nothing to say that the next frame will not say better.
                pass

    def _read(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "frame" in message:
                self.frame = str(message["frame"])
                self.frames = int(message.get("n", self.frames + 1))
                self.ready = True
                self.error = ""
            elif message.get("error"):
                self.error = str(message["error"])
                if message.get("fatal"):
                    self.ready = False
