"""Where plans go after you close the terminal.

A flat JSON file of every plan this machine has made: enough to list them and
to notice when a directory has been deleted out from under one.

A row is a `plan`, or it is not ours. A row of kind `app`, or with no kind, was
written by an older proto.pilot for a prototype this version cannot run; it is
kept, listed as `old`, and forgotten only by `proto prune`.

Deliberately not a database. It is a list of paths.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from protopilot.plan.model import PLAN_DIR, plan_path

#: A prototype an older version generated. Never written by this one, only read back.
APP = "app"
PLAN = "plan"
#: The file an older version's prototype kept beside where a plan keeps `plan.json`.
OLD_SPEC = "spec.json"
#: What `proto ls` calls a row: a plan on disk, a plan whose tree is gone, an older prototype.
HERE, GONE, OLD = "-", "gone", "old"
#: Read in `load` where a hand-edited file holds a kind that is not a string; it is never ours.
UNKNOWN = "unknown"


def _state_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def registry_path() -> Path:
    override = os.environ.get("PROTOPILOT_REGISTRY")
    return Path(override) if override else _state_home() / "proto-pilot" / "projects.json"


@dataclass(kw_only=True)
class Entry:
    slug: str
    name: str
    path: str
    # Nothing here sets or reads it. An older row holds one, and it is written back as read.
    port: int | None = None
    created_at: str
    idea: str = ""
    # A row with no kind was written before kinds existed, when only prototypes were listed.
    kind: str = APP

    @property
    def exists(self) -> bool:
        return self.kind == PLAN and tree_kind(Path(self.path)) == PLAN

    @property
    def state(self) -> str:
        if self.exists:
            return HERE
        return OLD if self.kind == APP else GONE


def tree_kind(path: Path) -> str | None:
    """What a directory holds by our own files: `plan`, or None when it is not ours.

    Asked of the tree, never of the registry, because a command is run inside a tree
    and a guard that trusted an index would delete whatever the index named. A tree
    holding an older version's prototype is not ours even beside a plan: it may have
    a running stack, which nothing here can stop.
    """
    if holds_old_prototype(path):
        return None
    return PLAN if plan_path(Path(path)).exists() else None


def holds_old_prototype(path: Path) -> bool:
    """Whether a directory holds the spec an older version's prototype kept."""
    return (Path(path) / PLAN_DIR / OLD_SPEC).exists()


def load() -> list[Entry]:
    path = registry_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        # A corrupt registry must never stop a plan. Losing the index is
        # recoverable; refusing to plan because the index is unreadable is not.
        return []
    known = {f.name for f in fields(Entry)}
    entries = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            # A key this version does not know is ignored, so the row it sits on is kept.
            entry = Entry(**{key: value for key, value in item.items() if key in known})
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
    """`slug`, or `slug_2`, `slug_3`...: a slug names one entry, so two may not share one."""
    candidate, n = slug, 1
    while candidate in taken:
        n += 1
        candidate = f"{slug}_{n}"
    return candidate


def record(*, slug: str, name: str, path: Path, idea: str = "", kind: str = PLAN) -> Entry:
    """Add or update one tree, keyed by resolved path; a slug another path holds gets a suffix."""
    resolved = str(Path(path).resolve())
    with _locked():
        entries = [e for e in load() if e.path != resolved]
        entry = _entry(slug, name, resolved, idea, kind, {e.slug for e in entries})
        entries.insert(0, entry)
        save(entries)
    return entry


def _entry(slug: str, name: str, resolved: str, idea: str, kind: str, taken: set[str]) -> Entry:
    return Entry(
        slug=_unique(slug, taken),
        name=name,
        path=resolved,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        idea=idea,
        kind=kind,
    )


def forget(path: Path) -> None:
    resolved = str(Path(path).resolve())
    with _locked():
        save([e for e in load() if e.path != resolved])


def prune() -> list[Entry]:
    """Drop every entry that is not a plan on disk. Returns what survived; no folder is touched."""
    with _locked():
        alive = [e for e in load() if e.exists]
        save(alive)
    return alive


def _holds(root: Path, inner: Path) -> bool:
    """Whether `inner` is `root` or anywhere under it."""
    return Path(inner).resolve().is_relative_to(root)


class NotAProject(ValueError):
    """Refused: the path is not a plan, or is not safe to delete."""


def delete(path: Path) -> None:
    """Remove a plan's tree and forget it. Irreversible.

    Guarded rather than trusting the caller: the difference between deleting a
    plan and deleting a home directory is one bad lookup. A directory holding
    no plan of ours is never removed.
    """
    import shutil

    root = Path(path).resolve()
    if tree_kind(root) is None:
        raise NotAProject(f"{root} has no {plan_path(root).relative_to(root)}; refusing to delete")
    if root.parent == root or _holds(root, Path.home()) or _holds(root, registry_path()):
        raise NotAProject(f"{root} is not a safe path to delete: it is, or holds, your home or the registry")

    shutil.rmtree(root, ignore_errors=True)
    forget(root)
