"""`proto targets` and `proto new --target`, executed rather than read.

`tests/test_cli_smoke.py` walks a command tree and runs every leaf of it — but
the tree it walks is `cli.cli`, this **repository's** `./pp`. Rule 15 keeps the
two CLIs apart, and the consequence is that nothing at all executes `proto`:
the product's commands are covered only where a test happens to call the
function underneath them. `proto targets` and `--target` had neither, and were
verified by hand.

What is asserted here is recomputed from the target registry rather than
written out, so the second target enrols by existing — the same property that
makes the registry a registry and not a list.

It used to hard-code `tui` in one place, pinning "the axis exists but the
target does not yet" while that was true. Phase 4 of
`docs/TODO/terminal-target.md` made it false, and the pin came out rather than
being relaxed: the refusal test now uses a name no build will ever have, and
every generation test runs over `targets.names()`.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from protopilot import targets
from protopilot.cli import main
from protopilot.spec import SPEC_DIR, SPEC_FILENAME

# Host-side: no key, no Docker daemon, no network. `--offline --no-verify`
# is what makes a real `proto new` runnable under this marker.
pytestmark = [pytest.mark.unit]

IDEA = "track camping gear across trips"


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """`proto new` records every tree it makes. Never in the real registry."""
    monkeypatch.setenv("PROTOPILOT_REGISTRY", str(tmp_path / "projects.json"))


@pytest.fixture()
def run():
    runner = CliRunner()
    return lambda *args: runner.invoke(main, list(args))


def generated(run, tmp_path, *extra: str):
    """One real offline generation into `tmp_path`, and the spec it wrote.

    No key, no daemon, no git: `--offline` uses the deterministic baseline,
    `--no-verify` skips the boot, and `--no-git` keeps a repository out of a
    temporary directory.
    """
    result = run("new", IDEA, "--dir", str(tmp_path / "tree"), "--offline", "--no-verify", "--no-git", "-y", *extra)
    assert result.exit_code == 0, result.output + repr(result.exception)
    return json.loads((tmp_path / "tree" / SPEC_DIR / SPEC_FILENAME).read_text())


# ── proto targets ────────────────────────────────────────────────────────


def test_targets_lists_every_installed_target_with_what_it_builds(run):
    """Enrolled by existing: the expectation is the registry, so a target added
    later is covered without touching this file."""
    result = run("targets")
    assert result.exit_code == 0

    for name in targets.names():
        module = targets.get(name)
        assert name in result.output
        assert module.LABEL in result.output, f"{name} is listed with no idea what it is"
        for archetype in module.ARCHETYPES:
            assert archetype in result.output, f"{name} does not say it builds {archetype}"


def test_targets_marks_the_default_and_marks_only_it(run):
    """`proto new` with no `--target` picks one, and the list is the only place
    a user can find out which."""
    result = run("targets")
    marked = [line.split()[0] for line in result.output.splitlines() if "(default)" in line]
    assert marked == [targets.DEFAULT]


def test_every_target_it_advertises_is_a_name_new_accepts(run, tmp_path):
    """The list and the selector have to agree. A name printed here that
    `--target` rejects is the tool describing coverage it does not have."""
    for name in targets.names():
        result = run("new", IDEA, "--dir", str(tmp_path / name), "--target", name, "--offline", "--no-verify", "-y")
        assert "unknown target" not in result.output, f"`proto targets` lists {name!r} and `proto new` refuses it"


# ── proto new --target ───────────────────────────────────────────────────


def test_new_refuses_an_unknown_target_by_name(run, tmp_path):
    """Refused naming both the miss and what exists — neither half is guessable
    from the other.

    `hologram` rather than a name that might be implemented one day: a refusal
    test pinned to a real plan's next step is a test that goes red the week the
    plan lands, and reads as a regression rather than as progress.
    """
    result = run("new", IDEA, "--dir", str(tmp_path / "tree"), "--target", "hologram", "--offline", "--no-verify", "-y")

    assert result.exit_code != 0
    assert "unknown target 'hologram'" in result.output
    assert targets.DEFAULT in result.output, "a refusal that does not say what exists leaves nowhere to go"
    assert not (tmp_path / "tree").exists(), "a refused target must not leave a part-built tree"


@pytest.mark.parametrize("name", targets.names())
def test_every_target_generates_a_tree_offline(run, tmp_path, name):
    """Every installed target, generated end to end through the real CLI.

    Parametrised over the registry, so a third target is covered by existing.
    This is the test that turns "the axis has two entries" into "both of them
    build something", and it needs no key, no daemon and no browser.
    """
    tree = tmp_path / name
    result = run("new", IDEA, "--dir", str(tree), "--target", name, "--offline", "--no-verify", "--no-git", "-y")
    assert result.exit_code == 0, result.output + repr(result.exception)

    spec = json.loads((tree / SPEC_DIR / SPEC_FILENAME).read_text())
    assert spec["target"] == name
    for path in targets.get(name).WRITABLE:
        if "*" in path:
            continue
        assert (tree / path).exists(), f"{name}: the {path} pass wrote nothing"


def test_the_target_is_checked_before_anything_is_spent(run, tmp_path, monkeypatch):
    """Ordering, and it is load-bearing twice over: the docker probe and the
    classifier both sit behind this check, so a typo costs neither a running
    daemon nor a token.

    Docker is forced *unavailable* rather than left to the machine. Without
    that the assertion is vacuous anywhere a daemon happens to be running,
    which is every developer laptop and no CI runner — the exact split where a
    reordering would pass here and fail there.
    """
    from protopilot import cli

    monkeypatch.setattr(cli, "docker_available", lambda runner: (False, "the docker daemon is not running"))

    # No `--no-verify`, so the docker probe is live and would answer first if
    # it were reached first.
    result = run("new", IDEA, "--dir", str(tmp_path / "tree"), "--target", "hologram", "-y")

    assert result.exit_code != 0
    assert "unknown target 'hologram'" in result.output
    assert "docker daemon" not in result.output.lower()


def test_new_writes_the_chosen_target_into_the_spec(run, tmp_path):
    """`--target` has to reach `spec.json`, because that file is what every
    later command — `proto add`, `proto spec`, the verifier lookup — reads the
    target off."""
    assert generated(run, tmp_path, "--target", targets.DEFAULT)["target"] == targets.DEFAULT


def test_new_with_no_target_uses_the_registrys_default(run, tmp_path):
    """`targets.DEFAULT`, never a literal in `cli.py`. Phase 6 moves the
    constant and this must move with it rather than pinning `web`."""
    assert generated(run, tmp_path)["target"] == targets.DEFAULT


def test_the_target_reaches_the_review_checkpoint(run, tmp_path):
    """The summary is the only gate in the tool. A person is being asked to
    approve a generation, and which *kind* of thing it is has to be on screen
    before they say yes."""
    result = run("new", IDEA, "--dir", str(tmp_path / "tree"), "--offline", "--no-verify", "--no-git", "-y")
    assert f"target: {targets.DEFAULT}" in result.output


@pytest.mark.parametrize("name", targets.names())
def test_the_generated_tree_is_the_targets_skeleton(run, tmp_path, name):
    """`--target` picks the tree, not just a string in a file. Compared against
    the target module's own skeleton, so this stays true for a second one."""
    generated(run, tmp_path, "--target", name)

    skeleton = targets.get(name).SKELETON_DIR
    for source in skeleton.rglob("*"):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        assert (tmp_path / "tree" / source.relative_to(skeleton)).exists(), f"{source.name} never made it into the tree"
