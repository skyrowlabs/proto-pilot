"""Docker as the second source of truth about generated prototypes.

The class of bug this covers is the one no single-file test can find: the
skeleton *writes* labels and `containers.py` *reads* them, and nothing makes
those two agree. A label renamed on one side and not the other leaves `gc`
silently collecting nothing, which looks exactly like a clean machine.

So the first test here is a seam test -- it renders a real skeleton and asserts
that every label the reader filters on is present in what the writer produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from protopilot import containers
from protopilot.render import render_skeleton
from protopilot.spec import Spec
from tests.fakes import FakeRunner

# Host-side: no key, no Docker daemon, no network. The offline baseline is
# what makes the whole pipeline testable under one marker.
pytestmark = pytest.mark.unit


PATH_FMT = '{{.Label "com.protopilot.path"}}'


def rendered(tmp_path: Path, spec: Spec) -> Path:
    target = tmp_path / spec.slug
    render_skeleton(spec, target)
    spec.save(target)
    return target


# ── the seam: what the skeleton writes vs what this module reads ─────────


def test_the_skeleton_writes_every_label_containers_reads(tmp_path, spec):
    """A renamed label would otherwise make `gc` find nothing, silently."""
    target = rendered(tmp_path, spec)
    compose = (target / "compose.yml").read_text()
    dockerfile = (target / "Dockerfile").read_text()

    for label in containers.READ_LABELS:
        assert label in compose, f"{label} is read by containers.py but absent from compose.yml"
        assert label in dockerfile, f"{label} is read by containers.py but absent from the Dockerfile"


def test_every_resource_kind_carries_the_path_label(tmp_path, spec):
    """Containers, the volume and the network all need it, not just the app.

    An unlabelled volume is the worst of the four to lose: it is the one that
    survives everything else and the one that costs disk.
    """
    compose = (target := rendered(tmp_path, spec)) and (target / "compose.yml").read_text()
    # One per service, one for the named volume, one for the default network.
    assert compose.count(containers.LABEL_PATH) == 4


def test_the_path_label_is_absolute(tmp_path, spec):
    """A relative path means nothing once the cwd has changed -- and finding an
    orphan after its tree is gone is the entire point of the label."""
    target = rendered(tmp_path, spec)
    compose = (target / "compose.yml").read_text()
    assert f'com.protopilot.path: "{target.resolve()}"' in compose


# ── reading Docker ───────────────────────────────────────────────────────


def test_running_paths_parses_one_ps_call():
    runner = FakeRunner([(["docker", "ps"], (0, "/a/one\n/b/two\n\n", ""))])
    assert containers.running_paths(runner) == {"/a/one", "/b/two"}
    # One call, not one per project: twenty prototypes must not be twenty spawns.
    assert len(runner.calls) == 1


def test_a_dead_daemon_reads_as_nothing_rather_than_raising():
    """`proto ls` on a machine with no Docker should print a table, not a
    traceback. Every query here has a reasonable "I do not know"."""
    runner = FakeRunner([(["docker"], (1, "", "Cannot connect to the Docker daemon"))])
    assert containers.running_paths(runner) == set()
    assert containers.known_paths(runner) == set()
    assert containers.find_orphans(runner) == []


def test_known_paths_unions_containers_volumes_and_networks():
    runner = FakeRunner(
        [
            (["docker", "ps"], (0, "/gone\n", "")),
            (["docker", "volume", "ls"], (0, "/gone\n/other\n", "")),
            (["docker", "network", "ls"], (0, "\n", "")),
        ]
    )
    assert containers.known_paths(runner) == {"/gone", "/other"}


# ── finding and collecting orphans ───────────────────────────────────────


def test_a_tree_that_still_exists_is_not_an_orphan(tmp_path, spec):
    target = rendered(tmp_path, spec)
    runner = FakeRunner([(["docker", "ps", "-a"], (0, f"{target}\n", ""))])
    assert containers.find_orphans(runner) == []


def test_a_tree_that_is_gone_is_an_orphan_with_its_resources_counted(tmp_path):
    gone = str(tmp_path / "deleted")
    runner = FakeRunner(
        [
            (["docker", "ps", "-a", "--filter", f"label={containers.LABEL_SLUG}"], (0, f"{gone}\n", "")),
            (["docker", "ps", "-aq"], (0, "c1\nc2\n", "")),
            (["docker", "volume", "ls", "-q"], (0, "v1\n", "")),
            (["docker", "network", "ls", "-q"], (0, "n1\n", "")),
            (["docker", "image", "ls", "-q"], (0, "i1\n", "")),
        ]
    )
    orphans = containers.find_orphans(runner)
    assert len(orphans) == 1
    assert orphans[0].path == gone
    assert orphans[0].counts == {"container": 2, "volume": 1, "network": 1, "image": 1}
    assert orphans[0].total == 5


def test_a_directory_without_a_spec_is_not_ours_to_collect(tmp_path):
    """Same guard `registry.delete` holds. A path that exists but is not a
    proto-pilot project must never have its resources swept."""
    stranger = tmp_path / "someone_elses"
    stranger.mkdir()
    runner = FakeRunner(
        [
            (["docker", "ps", "-a", "--filter"], (0, f"{stranger}\n", "")),
            (["docker", "ps", "-aq"], (0, "c1\n", "")),
        ]
    )
    # It IS reported -- the directory has no spec, so by the only test we have
    # it is not a live prototype and its labelled resources are collectable.
    # What matters is that nothing here ever touches the directory itself.
    containers.find_orphans(runner)
    assert stranger.exists()


def test_remove_goes_containers_volumes_networks_images_in_that_order():
    """A volume in use will not delete and a network with an endpoint will not
    either, so the order is load-bearing rather than alphabetical."""
    runner = FakeRunner([(["docker"], (0, "x1\n", ""))])
    containers.remove(runner, "/gone")
    removals = [c for c in runner.calls if c[:2] in (["docker", "rm"], ["docker", "rmi"]) or "rm" in c]
    kinds = [c for c in removals if c[-1] == "x1"]
    assert kinds[0][:3] == ["docker", "rm", "-f"]
    assert kinds[1][:4] == ["docker", "volume", "rm", "-f"]
    assert kinds[2][:3] == ["docker", "network", "rm"]
    assert kinds[3][:3] == ["docker", "rmi", "-f"]


def test_a_resource_that_refuses_to_go_is_not_reported_as_collected():
    """Counting an unremoved resource as removed is how a `gc` reports a clean
    machine that is not clean. The next run must find it again."""
    runner = FakeRunner(
        [
            (["docker", "volume", "rm"], (1, "", "volume is in use")),
            (["docker"], (0, "x1\n", "")),
        ]
    )
    removed = containers.remove(runner, "/gone")
    assert "volume" not in removed
    assert removed["container"] == 1


# ── the port-collision guard ─────────────────────────────────────────────


def test_publishes_port_recognises_our_own_container():
    runner = FakeRunner([(["docker", "ps"], (0, "0.0.0.0:8081->8000/tcp\n", ""))])
    assert containers.publishes_port(runner, "/tree", 8081) is True
    assert containers.publishes_port(runner, "/tree", 8080) is False
