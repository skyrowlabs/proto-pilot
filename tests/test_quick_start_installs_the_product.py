"""Every setup block installs proto.pilot itself, with every extra CI installs.

`ci.yml` installs `-e ".[<every extra pyproject.toml declares>]"` before the unit
suite, so a block that names fewer extras promises a `check pre-push` that dies
at collection on a fresh clone. The extras are read from `pyproject.toml` rather
than listed here, so a new extra turns this red instead of the Quick Start false.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_setup_blocks_agree import setup_blocks  # noqa: E402

from scripts.paths import PROJECT_ROOT  # noqa: E402

_EDITABLE = re.compile(r"pip install\s+-e\s+\"?\.\[(?P<extras>[\w,-]+)\]\"?")


def declared_extras() -> set:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as handle:
        return set(tomllib.load(handle)["project"]["optional-dependencies"])


def test_every_setup_block_installs_the_product_with_every_extra() -> None:
    declared = declared_extras()
    blocks = setup_blocks()
    assert blocks, "no setup block enrolled; nothing was checked"
    for doc, lines in sorted(blocks.items()):
        installed = {extra for line in lines for m in _EDITABLE.finditer(line) for extra in m["extras"].split(",")}
        assert installed == declared, (
            f"{doc}'s setup block installs extras {sorted(installed) or 'none'}; pyproject.toml declares "
            f"{sorted(declared)} and CI installs all of them, so a fresh clone's unit suite cannot collect."
        )


def test_the_pattern_reads_an_editable_install() -> None:
    match = _EDITABLE.search('.venv/bin/pip install -e ".[browser,dev,web]"')
    assert match is not None and match["extras"] == "browser,dev,web"
    assert _EDITABLE.search("pip install -e .") is None
