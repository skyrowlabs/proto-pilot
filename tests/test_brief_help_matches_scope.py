"""`proto plan --help` and the scope prompt agree on which blank brief fields the model fills (#52)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from protopilot import cli
from protopilot.plan import render
from protopilot.plan.passes import scope

pytestmark = [pytest.mark.unit]

LEFT_EMPTY = "An empty string if the idea does not say."


def helped() -> str:
    return " ".join(CliRunner().invoke(cli.main, ["plan", "--help"]).output.split())


@pytest.mark.parametrize(("field", "flag"), [("audience", "--for"), ("horizon", "--horizon")])
def test_a_field_the_prompt_leaves_empty_is_one_the_help_says_may_stay_unset(field: str, flag: str):
    assert f"- `{field}`:" in scope.SYSTEM and LEFT_EMPTY in scope.SYSTEM.split(f"- `{field}`:")[1].splitlines()[0]
    assert "A blank --for or --horizon is filled only from what IDEA says" in helped() and flag in helped()
    assert f"otherwise reads {render.UNSET.rstrip('.')}" in helped()


def test_the_goal_the_prompt_always_returns_is_the_one_the_help_says_the_model_proposes():
    assert LEFT_EMPTY not in scope.SYSTEM.split("- `goal`:")[1].splitlines()[0]
    assert "A blank --goal, the model proposes." in helped()
