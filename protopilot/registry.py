"""Where prototypes go after you close the terminal.

A generated tree used to be findable only by remembering the directory you
ran `proto new` in, which is fine for one prototype and useless for twenty.
The registry is a flat JSON file of every project this machine has generated:
enough to list them, relaunch one, and notice when a directory has been
deleted out from under it.

Two kinds share it: an `app` from `proto new`, and a `plan` from `proto plan`,
which has no port and nothing to run. An entry written before kinds existed is
an app, because only apps were registered then.

Deliberately not a database. It is a list of paths.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from protopilot.plan.model import PLAN_DIR, plan_path
from protopilot.spec import SPEC_FILENAME

APP = "app"
PLAN = "plan"
KINDS = (APP, PLAN)
#: Read in `load` where a hand-edited file holds a kind that is not a string; it is never ours.
UNKNOWN = "unknown"


def _state_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def registry_path() -> Path:
    override = os.environ.get("PROTOPILOT_REGISTRY")
    return Path(override) if override else _state_home() / "proto-pilot" / "projects.json"


@dataclass
class Entry:
    slug: str
    name: str
    path: str
    # None for a plan: nothing in it listens.
    port: int | None
    created_at: str
    idea: str = ""
    kind: str = APP

    @property
    def exists(self) -> bool:
        return self.kind in KINDS and tree_kind(Path(self.path)) == self.kind


def tree_kind(path: Path) -> str | None:
    """What a directory holds by our own files: `app`, `plan`, or None when it is not ours.

    Asked of the tree, never of the registry, because a command is run inside a tree
    and a guard that trusted an index would delete whatever the index named.
    """
    root = Path(path)
    if (root / PLAN_DIR / SPEC_FILENAME).exists():
        return APP
    if plan_path(root).exists():
        return PLAN
    return None


def load() -> list[Entry]:
    path = registry_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        # A corrupt registry must never stop a generation. Losing the index is
        # recoverable; refusing to build because the index is unreadable is not.
        return []
    entries = []
    for item in raw if isinstance(raw, list) else []:
        try:
            entry = Entry(**item)
        except TypeError:
            continue
        # Kept, so nothing is lost on the next save, but never one of ours: it reads as gone.
        entry.kind = entry.kind if isinstance(entry.kind, str) else UNKNOWN
        entries.append(entry)
    return entries


def save(entries: list[Entry]) -> None:
    """Land the file whole or not at all: a reader never sees half of it."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps([asdict(e) for e in entries], indent=2) + "\n")
        os.replace(temp, path)
    finally:
        with suppress(OSError):
            temp.unlink(missing_ok=True)


@contextmanager
def _locked() -> Iterator[None]:
    """Hold the registry for one load-modify-save, so two writers never lose each other's entry."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:  # pragma: no cover - no flock on this platform; writes stay atomic
        yield
        return
    with open(path.with_name(path.name + ".lock"), "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _unique(slug: str, taken: set[str]) -> str:
    """`slug`, or `slug_2`, `slug_3`...: the web finds an entry by slug, so two may not share one."""
    candidate, n = slug, 1
    while candidate in taken:
        n += 1
        candidate = f"{slug}_{n}"
    return candidate


def record(*, slug: str, name: str, path: Path, port: int | None, idea: str = "", kind: str = APP) -> Entry:
    """Add or update one project, keyed by resolved path; a slug another path holds gets a suffix."""
    resolved = str(Path(path).resolve())
    with _locked():
        entries = [e for e in load() if e.path != resolved]
        entry = _entry(slug, name, resolved, port, idea, kind, {e.slug for e in entries})
        entries.insert(0, entry)
        save(entries)
    return entry


def _entry(slug: str, name: str, resolved: str, port: int | None, idea: str, kind: str, taken: set[str]) -> Entry:
    return Entry(
        slug=_unique(slug, taken),
        name=name,
        path=resolved,
        port=port,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        idea=idea,
        kind=kind,
    )


def forget(path: Path) -> None:
    resolved = str(Path(path).resolve())
    with _locked():
        save([e for e in load() if e.path != resolved])


def prune() -> list[Entry]:
    """Drop entries whose directory is gone. Returns what survived."""
    with _locked():
        alive = [e for e in load() if e.exists]
        save(alive)
    return alive


def _holds(root: Path, inner: Path) -> bool:
    """Whether `inner` is `root` or anywhere under it."""
    return Path(inner).resolve().is_relative_to(root)


class NotAProject(ValueError):
    """Refused: the path is not a proto-pilot project."""


def delete(path: Path, runner=None) -> None:
    """Stop an app's stack and drop its data, then remove the tree. Irreversible.

    Guarded rather than trusting the caller: this is reached from an HTTP
    handler with a slug in the URL, and the difference between deleting a
    prototype and deleting a home directory is one bad lookup. A directory
    holding neither our spec nor our plan is not ours and is never removed.
    A plan has no stack, so it goes with no Docker call at all.
    """
    import shutil
    import subprocess

    root = Path(path).resolve()
    kind = tree_kind(root)
    if kind is None:
        raise NotAProject(
            f"{root} has no {PLAN_DIR}/{SPEC_FILENAME} and no {plan_path(root).relative_to(root)}; refusing to delete"
        )
    if root.parent == root or _holds(root, Path.home()) or _holds(root, registry_path()):
        raise NotAProject(f"{root} is not a safe path to delete: it is, or holds, your home or the registry")

    if kind == APP:
        call = runner or (lambda argv, cwd: subprocess.call(argv, cwd=cwd))  # noqa: S603
        try:
            call(["docker", "compose", "down", "-v"], str(root))
        except OSError:
            # No daemon, or never started. The tree still goes.
            pass
    shutil.rmtree(root, ignore_errors=True)
    forget(root)
