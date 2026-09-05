"""A job that `needs:` a job that does not exist kills the whole workflow.

Not the job — the **run**. GitHub validates the graph before it schedules
anything, so an unresolved dependency is a `startup_failure`: zero jobs, no
logs, `gh run view --log-failed` answering "log not found", and nothing on the
commit to say which line was wrong. Every other CI failure hands you a stack
trace; this one hands you an empty run and the diff you just pushed.

It happened here on `8ea7b6b`. `release-please` carried
`needs: [lint, unit-tests, integration, ui]`, and the same commit removed the
`ui` job — deliberately, because `cli/test_cmds.py` declares that suite
`scheduled=False` (see the note beside it). Nothing local objected: the file is
valid YAML, `pp check pre-push` passed all four gates, and
`tests/test_ci_runs_every_suite.py` was satisfied, because it asks whether the
markers and the workflows agree and has no opinion about the job graph.

That is the gap this closes, and it generalises past the `ui` case: removing a
job is a normal thing to do — an obsolete lint pass, a suite that moved, a
platform dropped — and the reference that outlives it is never in the block you
edited.

## Why the comments are stripped first

Via `scripts/yaml_text.py`, for the reason skeletor found in the mirror-image
check: a workflow that lost a job is the likeliest place on earth to find a
comment *naming* that job, so a scanner reading raw text has its false pass
perfectly correlated with the defect. The note now sitting where the `ui` job
used to be says the word `ui` five times.

Here it is `yaml.safe_load` doing the reading rather than a regex, so comments
are dropped anyway — but the parse is over the masked text regardless, so the
two checks cannot disagree about what a workflow says.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scanning import scanned  # noqa: E402
from scripts.yaml_text import read_uncommented  # noqa: E402

WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"


def _jobs(path: Path) -> dict:
    return (yaml.safe_load(read_uncommented(path)) or {}).get("jobs") or {}


def _needs(job: dict) -> list[str]:
    """`needs:` is a string for one dependency and a list for several.

    Both spellings are valid and the repo uses both. Iterating the string form
    yields *characters*, which turns a correct workflow into four bogus
    findings — measured, on the first version of this scan.
    """
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _workflows() -> list[Path]:
    return scanned(sorted(WORKFLOWS.glob("*.yml")), "workflow files under .github/workflows/", 2)


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_every_needs_names_a_job_in_the_same_workflow(path: Path):
    jobs = scanned(_jobs(path), f"jobs in {path.name}")
    dangling = {name: [n for n in _needs(job) if n not in jobs] for name, job in jobs.items() if _needs(job)}
    dangling = {name: missing for name, missing in dangling.items() if missing}

    assert not dangling, (
        f"{path.relative_to(PROJECT_ROOT)} has job(s) depending on jobs it does not define: "
        f"{dangling}.\nGitHub rejects the whole workflow before scheduling anything — the run "
        f"is a startup_failure with zero jobs and no log, so this is not a red check, it is an "
        f"absent one. Jobs defined here: {sorted(jobs)}"
    )
