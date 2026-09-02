"""What Docker knows about prototypes this machine has generated.

The registry (`registry.py`) is a JSON file we write. This module is the second,
independent answer to the same question -- read back out of Docker itself, from
labels stamped into every generated `compose.yml`.

Two sources of truth is normally a smell. Here it is the design, because the two
disagree in exactly the way that matters: a tree deleted with `rm -rf` leaves the
registry entry *and* a running container, a named volume, a network and an image,
and nothing on either side ever notices. `registry.delete` cleans up when it is
the one doing the deleting; it cannot help when it is not.

So the labels make Docker self-describing. Every resource carries the absolute
path of the tree that created it, which means an orphan is findable by asking
Docker alone -- no registry, no memory of what was generated last month, and it
still works after the JSON file has been wiped.

Nothing here raises when Docker is missing. A machine with no daemon should
still be able to run `proto ls`; it just cannot say what is running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from protopilot.runner import Runner
from protopilot.spec import SPEC_DIR, SPEC_FILENAME

# The label vocabulary, defined once. `skeleton/compose.yml` and
# `skeleton/Dockerfile` write these; everything below reads them. Adding a
# label means adding it in all three places, and `tests/test_containers.py`
# fails if the skeleton stops writing one that is read here.
LABEL_NS = "com.protopilot"
LABEL_SLUG = f"{LABEL_NS}.slug"
LABEL_PATH = f"{LABEL_NS}.path"
LABEL_PROJECT = f"{LABEL_NS}.project"

#: Read labels are the ones a query filters or parses on. Kept as a set so the
#: skeleton test can assert the skeleton writes every one of them.
READ_LABELS = (LABEL_SLUG, LABEL_PATH, LABEL_PROJECT)

#: How a resource kind is listed and removed. One row per kind, so adding a
#: kind is a row rather than four more functions.
KINDS = (
    # (name, list argv, remove argv, plural for reporting)
    ("container", ["docker", "ps", "-aq"], ["docker", "rm", "-f"], "containers"),
    ("volume", ["docker", "volume", "ls", "-q"], ["docker", "volume", "rm", "-f"], "volumes"),
    ("network", ["docker", "network", "ls", "-q"], ["docker", "network", "rm"], "networks"),
    ("image", ["docker", "image", "ls", "-q"], ["docker", "rmi", "-f"], "images"),
)


@dataclass
class Orphan:
    """Docker resources whose tree is gone."""

    path: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def describe(self) -> str:
        parts = [f"{n} {kind}" for kind, n in sorted(self.counts.items()) if n]
        return f"{self.path}  ({', '.join(parts)})" if parts else self.path


def _lines(runner: Runner, argv: list[str], timeout: float = 30) -> list[str]:
    """Run a docker query and return its non-empty output lines.

    A failure is an empty list, never an exception: every caller is answering a
    question that has a reasonable "I do not know" -- and a `proto ls` that
    raises because the daemon is down is worse than one that omits a column.
    """
    result = runner.run(argv, timeout=timeout)
    if not result.ok:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _tree_exists(path: str) -> bool:
    """Whether a path is still a proto-pilot project.

    Deliberately the same test `registry.delete` guards on. A directory that
    exists but has no spec in it is not ours, and its resources are not ours to
    collect either.
    """
    return (Path(path) / SPEC_DIR / SPEC_FILENAME).exists()


def running_paths(runner: Runner) -> set[str]:
    """Tree paths that currently have a container up.

    One `docker ps` for the whole listing rather than a `compose ps` per
    project: twenty prototypes is twenty subprocess spawns, and `proto ls`
    should not take four seconds to print a table.
    """
    return set(
        _lines(
            runner,
            ["docker", "ps", "--filter", f"label={LABEL_SLUG}", "--format", f'{{{{.Label "{LABEL_PATH}"}}}}'],
        )
    )


def known_paths(runner: Runner) -> set[str]:
    """Every tree path Docker still holds a resource for, running or not.

    Containers, volumes and networks are asked separately because each has its
    own listing command; images are not, because `docker image ls` has no
    `.Label` formatter -- they are found by exact-value filter at removal time,
    which is all `gc` needs.
    """
    fmt = f'{{{{.Label "{LABEL_PATH}"}}}}'
    queries = (
        ["docker", "ps", "-a", "--filter", f"label={LABEL_SLUG}", "--format", fmt],
        ["docker", "volume", "ls", "--filter", f"label={LABEL_SLUG}", "--format", fmt],
        ["docker", "network", "ls", "--filter", f"label={LABEL_SLUG}", "--format", fmt],
    )
    found: set[str] = set()
    for argv in queries:
        found.update(_lines(runner, argv))
    return {path for path in found if path}


def find_orphans(runner: Runner) -> list[Orphan]:
    """Labelled resources whose tree no longer exists.

    This is the whole reason the labels are there. `registry.delete` drops the
    volume when it is the one removing a tree; a `rm -rf`, a wiped scratch
    directory or a `git clean` leaves every resource behind with nothing left
    on disk pointing at it.
    """
    orphans = []
    for path in sorted(known_paths(runner)):
        if _tree_exists(path):
            continue
        counts = {}
        for kind, list_argv, _remove, _plural in KINDS:
            ids = _lines(runner, [*list_argv, "--filter", f"label={LABEL_PATH}={path}"])
            if ids:
                counts[kind] = len(ids)
        if counts:
            orphans.append(Orphan(path=path, counts=counts))
    return orphans


def remove(runner: Runner, path: str) -> dict[str, int]:
    """Delete every labelled resource for one tree path. Irreversible.

    Ordered containers -> volumes -> networks -> images, which is the only
    order that works: a volume in use by a container will not delete, and a
    network with an endpoint attached will not either. `KINDS` is in that order
    and the ordering is load-bearing, not alphabetical.
    """
    removed: dict[str, int] = {}
    for kind, list_argv, remove_argv, _plural in KINDS:
        ids = _lines(runner, [*list_argv, "--filter", f"label={LABEL_PATH}={path}"])
        if not ids:
            continue
        result = runner.run([*remove_argv, *ids], timeout=120)
        # Counted as removed only if docker agreed. A resource that refused to
        # go is not silently reported as collected -- the next `gc` finds it
        # again, which is the correct behaviour for something still in use.
        if result.ok:
            removed[kind] = len(ids)
    return removed


def publishes_port(runner: Runner, path: str, port: int) -> bool:
    """Whether this tree's own container is the thing holding `port`.

    `up` on an already-running prototype is idempotent and must stay that way,
    so "the port is taken" is only a problem when something *else* took it.
    Without this check the collision guard would refuse to re-run `up` on a
    prototype that is working perfectly.
    """
    lines = _lines(
        runner,
        ["docker", "ps", "--filter", f"label={LABEL_PATH}={path}", "--format", "{{.Ports}}"],
    )
    return any(f":{port}->" in line for line in lines)
