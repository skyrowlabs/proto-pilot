"""The brief beside an idea: what a person states is the plan's, and the model fills only the blanks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, script

from protopilot import cli
from protopilot.plan import pipeline
from protopilot.plan.model import Brief, Plan, plan_path

pytestmark = [pytest.mark.unit]

BRIEF_FLAGS = (
    "--goal", "decide whether to open a second branch",
    "--for", "renters with no shed",
    "--horizon", "two years, volunteers only",
    "--must", "no paid staff",
    "--must", "one room",
    "--not", "delivery",
    "--not", "power tools",
)  # fmt: skip
STATED = Brief(
    goal="decide whether to open a second branch",
    audience="renters with no shed",
    horizon="two years, volunteers only",
    must=["no paid staff", "one room"],
    out=["delivery", "power tools"],
)


def invoke(*args: str, stdin: str = ""):
    return CliRunner().invoke(cli.main, ["plan", *args], input=stdin)


def said(result) -> str:
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


@pytest.fixture
def at_a_terminal(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_terminal", lambda: True)


@pytest.fixture
def model(monkeypatch):
    def install(**overrides: object) -> FakeLLM:
        llm = FakeLLM(script(**overrides))
        monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
        return llm

    return install


@pytest.fixture
def no_backend(monkeypatch):
    """Fail the test the moment anything builds a backend, from the call on."""

    def install() -> None:
        monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("a backend was built"))

    return install


# -- the stated fields win -------------------------------------------------


def test_every_stated_field_beats_what_the_model_returned(tmp_path, model):
    tree = tmp_path / "tree"
    disagreeing = {**GOOD["scope"], "goal": "Something else.", "audience": "Everyone", "constraints": ["be cheap"]}
    model(scope=disagreeing)
    assert invoke(IDEA, *BRIEF_FLAGS, "--direction", "one town", "--yes", "--dir", str(tree)).exit_code == 0
    plan = Plan.load(tree)
    assert plan.brief == STATED
    assert (plan.goal, plan.audience, plan.horizon) == (STATED.goal, STATED.audience, STATED.horizon)
    # The direction first, then the person's must-haves, then what the model added.
    assert plan.constraints == ["one town", "no paid staff", "one room", "be cheap"]


def test_a_blank_field_is_left_to_the_model(tmp_path, model):
    tree = tmp_path / "tree"
    model()
    assert invoke(IDEA, "--for", "renters", "--yes", "--dir", str(tree)).exit_code == 0
    plan = Plan.load(tree)
    assert plan.audience == "renters"
    assert (plan.goal, plan.horizon) == (GOOD["scope"]["goal"], GOOD["scope"]["horizon"])


def test_the_scope_prompt_names_each_stated_field(tmp_path, model):
    llm = model()
    assert invoke(IDEA, *BRIEF_FLAGS, "--yes", "--dir", str(tmp_path / "tree")).exit_code == 0
    user = next(call["user"] for call in llm.calls if call["label"] == "scope")
    for line in (
        f"Goal the user stated: {STATED.goal}",
        f"Audience the user stated: {STATED.audience}",
        f"Horizon the user stated: {STATED.horizon}",
        "Must-have the user stated: one room",
        "Out of scope, as the user stated: power tools",
    ):
        assert line in user


def test_every_pass_after_scope_is_told_what_is_out_of_scope(tmp_path, model):
    llm = model()
    assert invoke(IDEA, *BRIEF_FLAGS, "--yes", "--dir", str(tmp_path / "tree")).exit_code == 0
    later = [call for call in llm.calls if call["label"] != "scope"]
    assert later, "no pass ran after scope"
    for call in later:
        assert '"out_of_scope": [\n    "delivery",\n    "power tools"\n  ]' in call["user"], call["label"]


def test_out_of_scope_is_its_own_section_of_the_plan_page(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--not", "delivery", "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    page = (tree / "PLAN.md").read_text(encoding="utf-8")
    assert "## Out of scope\n\n- delivery\n" in page
    assert page.index("## Constraints") < page.index("## Out of scope") < page.index("## Open questions")


def test_the_offline_twin_keeps_the_brief_too(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, *BRIEF_FLAGS, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    plan = Plan.load(tree)
    assert (plan.goal, plan.audience, plan.horizon) == (STATED.goal, STATED.audience, STATED.horizon)
    assert plan.constraints[:2] == STATED.must


def test_the_review_summary_marks_what_the_person_stated():
    brief = STATED.model_copy(update={"audience": ""})
    plan = Plan(
        slug="p", title="P", idea="p", brief=brief, goal=STATED.goal, audience="x", constraints=["one room", "cheap"]
    )
    summary = plan.summary()
    assert f"goal: {STATED.goal} (yours)" in summary
    assert "audience: x\n" in summary  # the model's, so unmarked
    assert "constraint: one room (yours)\n  constraint: cheap\n" in summary
    assert "out of scope: delivery" in summary


# -- the brief is half the plan's identity --------------------------------


def test_a_plan_with_no_brief_writes_no_brief_key(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    assert "brief" not in json.loads(plan_path(tree).read_text(encoding="utf-8"))


def test_a_plan_json_from_before_the_brief_still_loads_with_an_empty_one(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    assert not Plan.load(tree).brief
    assert pipeline.existing_plan(tree, IDEA) is not None


def test_the_same_brief_rerenders_with_no_backend_whatever_its_spacing(tmp_path, no_backend):
    tree = tmp_path / "tree"
    assert invoke(IDEA, *BRIEF_FLAGS, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    no_backend()
    respaced = [f"  {arg}  " if not arg.startswith("--") else arg for arg in BRIEF_FLAGS]
    assert invoke(IDEA, *respaced, "--dir", str(tree)).exit_code == 0


@pytest.mark.parametrize(
    "changed",
    [
        ("--goal", "decide something else"),
        ("--not", "delivery"),  # one --not of two
        (),  # no brief at all
    ],
)
def test_another_brief_is_refused_and_touches_nothing(tmp_path, no_backend, changed):
    tree = tmp_path / "tree"
    assert invoke(IDEA, *BRIEF_FLAGS, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    no_backend()
    before = snapshot(tree)
    result = invoke(IDEA, *changed, "--dir", str(tree))
    assert result.exit_code == 1
    assert "same idea, direction and brief" in said(result)
    assert snapshot(tree) == before


def test_a_plan_without_a_brief_refuses_one_added_later(tmp_path, no_backend):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    no_backend()
    result = invoke(IDEA, "--for", "renters", "--dir", str(tree))
    assert result.exit_code == 1
    assert "with no direction." in said(result)  # it names the brief only when the tree has one


def test_a_draft_holding_another_brief_is_not_resumed(tmp_path):
    tree = tmp_path / "tree"
    draft = Plan(slug="p", title="P", idea=IDEA, brief=STATED)
    pipeline.ledger.save_draft(tree, draft)
    assert pipeline.resumable(tree, IDEA, "", STATED) == draft
    with pytest.raises(pipeline.PlanRefused, match="a brief of its own"):
        pipeline.resumable(tree, IDEA, "", Brief(goal="other"))


# -- the guided prompt -----------------------------------------------------


def test_with_no_idea_a_terminal_is_asked_for_the_idea_and_its_brief(tmp_path, monkeypatch, at_a_terminal, model):
    tree = tmp_path / "tree"
    model()
    answers = [
        "",  # the idea is required, so a blank one is asked again
        "  start a community   tool library ",
        STATED.goal,
        STATED.audience,
        "",  # horizon left to the model
        "no paid staff",
        "one room",
        "",  # ends the must-haves
        "delivery",
        "",  # ends the out-of-scope list
        "",  # accepts the outline
    ]
    result = invoke("--dir", str(tree), stdin="\n".join(answers) + "\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert plan.idea == IDEA
    assert plan.brief == Brief(goal=STATED.goal, audience=STATED.audience, must=STATED.must, out=["delivery"])
    assert plan.horizon == GOOD["scope"]["horizon"]


def test_a_field_given_as_a_flag_is_not_asked_again(tmp_path, at_a_terminal, model):
    tree = tmp_path / "tree"
    model()
    flags = ("--goal", "g", "--for", "a", "--horizon", "h", "--must", "m", "--not", "o")
    result = invoke(*flags, "--dir", str(tree), stdin=f"{IDEA}\n\n")
    assert result.exit_code == 0, result.output
    assert cli.ASK_GOAL not in result.output and cli.ASK_MUST not in result.output
    assert Plan.load(tree).brief == Brief(goal="g", audience="a", horizon="h", must=["m"], out=["o"])


@pytest.mark.parametrize("flags", [["--yes"], []])
def test_with_no_idea_and_nobody_to_ask_it_refuses_before_any_backend(tmp_path, no_backend, flags):
    no_backend()
    # CliRunner's stdin is not a terminal, so [] is the piped case and --yes the explicit one.
    result = invoke(*flags, "--offline", "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 1
    assert "needs an idea" in said(result) and "No model was called." in said(result)
    assert not (tmp_path / "tree").exists()
