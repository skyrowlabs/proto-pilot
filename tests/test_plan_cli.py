"""`proto plan` from the command line: backends, the review, failures and reruns."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from fakes import FakeLLM
from plan_script import GOOD, IDEA, PASS_NAMES, PLAN_PASS_NAMES, SLUGS, consider_of, edge, outline_of, script, step

from protopilot import cli
from protopilot import llm as llm_module
from protopilot.jobs import STORE
from protopilot.llm import LLMError
from protopilot.plan.model import Plan

pytestmark = [pytest.mark.unit]


def invoke(*args: str, stdin: str = ""):
    return CliRunner().invoke(cli.main, ["plan", *args], input=stdin)


def said(result) -> str:
    """The output as one line: a long path makes click's error wrap anywhere."""
    return " ".join(result.output.split())


def snapshot(tree: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tree)): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


class Recording(FakeLLM):
    """A fake that also keeps the schema each pass was handed."""

    def __init__(self, responses: list):
        super().__init__(responses)
        self.schemas: dict[str, dict] = {}

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        self.schemas[label] = schema
        return super().structured(system=system, user=user, schema=schema, label=label)

    @property
    def labels(self) -> list[str]:
        return [call["label"] for call in self.calls]


@pytest.fixture
def at_a_terminal(monkeypatch):
    monkeypatch.setattr(cli, "_stdin_is_terminal", lambda: True)


@pytest.fixture
def model(monkeypatch):
    """Install a fake backend behind `build_llm`, and hand it back."""

    def install(**overrides: object) -> Recording:
        llm = Recording(script(**overrides))
        monkeypatch.setattr(cli, "build_llm", lambda **_: llm)
        return llm

    return install


@pytest.fixture
def no_backend(monkeypatch):
    """Fail the test the moment anything builds a backend."""

    def install() -> None:
        monkeypatch.setattr(cli, "build_llm", lambda **_: pytest.fail("a backend was built"))

    return install


# -- --backend ------------------------------------------------------------


@pytest.fixture
def backends(monkeypatch):
    """The real `build_llm`, with the two paid classes replaced at the boundary."""
    monkeypatch.delenv("PROTOPILOT_LLM", raising=False)
    built: list[str] = []

    def stand_in(name: str):
        def construct() -> FakeLLM:
            built.append(name)
            return FakeLLM(script())

        return construct

    monkeypatch.setattr(llm_module, "ClaudeLLM", stand_in("api"))
    monkeypatch.setattr(llm_module, "ClaudeCodeLLM", stand_in("claude-code"))
    return built


@pytest.mark.parametrize(
    ("flags", "env", "chosen"),
    [
        ([], None, "api"),
        (["--backend", "api"], None, "api"),
        (["--backend", "claude-code"], None, "claude-code"),
        ([], "claude-code", "claude-code"),
        ([], "subscription", "claude-code"),
        (["--backend", "api"], "claude-code", "api"),
        (["--backend", "claude-code"], "api", "claude-code"),
    ],
)
def test_the_backend_flag_reaches_the_model_and_beats_the_environment(
    tmp_path, monkeypatch, backends, flags, env, chosen
):
    if env:
        monkeypatch.setenv("PROTOPILOT_LLM", env)
    result = invoke(IDEA, "--yes", "--dir", str(tmp_path / "tree"), *flags)
    assert result.exit_code == 0, result.output
    assert backends == [chosen]
    assert Plan.load(tmp_path / "tree").depth == "standard"


@pytest.mark.parametrize(
    ("flags", "env"),
    [
        (["--backend", "offline"], None),
        (["--offline"], None),
        (["--offline", "--backend", "api"], None),
        (["--offline", "--backend", "claude-code"], None),
        (["--offline"], "api"),
        ([], "offline"),
        (["--backend", "offline"], "api"),
    ],
)
def test_every_offline_spelling_writes_the_same_bytes_and_builds_no_model(tmp_path, monkeypatch, backends, flags, env):
    reference = tmp_path / "reference"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(reference)).exit_code == 0
    if env:
        monkeypatch.setenv("PROTOPILOT_LLM", env)
    result = invoke(IDEA, "--yes", "--dir", str(tmp_path / "tree"), *flags)
    assert result.exit_code == 0, result.output
    assert backends == []
    assert snapshot(tmp_path / "tree") == snapshot(reference)
    assert "Estimated model calls: 0, because this run is offline." in said(result)


def test_backend_offline_alone_still_holds_a_review(tmp_path, backends, at_a_terminal):
    tree = tmp_path / "tree"
    result = invoke(IDEA, "--backend", "offline", "--dir", str(tree), stdin="drop risks\n\n")
    assert result.exit_code == 0, result.output
    assert "risks" not in [t.slug for t in Plan.load(tree).topics]


@pytest.mark.parametrize("flags", [["--backend", "offline"], ["--offline"]])
def test_depth_is_refused_on_every_offline_spelling_before_any_job(tmp_path, backends, flags):
    before = len(STORE.all())
    result = invoke(IDEA, "--yes", "--depth", "deep", "--dir", str(tmp_path / "tree"), *flags)
    assert result.exit_code == 1
    assert "--depth needs the model" in said(result)
    assert (len(STORE.all()), (tmp_path / "tree").exists()) == (before, False)


def test_an_unknown_backend_is_refused_by_the_flag_and_by_the_environment(tmp_path, monkeypatch, backends):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--yes", "--backend", "bogus", "--dir", str(tree)).exit_code == 2
    monkeypatch.setenv("PROTOPILOT_LLM", "bogus")
    result = invoke(IDEA, "--yes", "--dir", str(tree))
    assert result.exit_code == 1
    assert "unknown backend 'bogus'" in said(result)
    assert not tree.exists()


def test_a_backend_that_cannot_be_built_is_a_sentence_and_no_job(tmp_path, monkeypatch):
    def unbuildable(**_):
        raise LLMError("no credentials")

    monkeypatch.setattr(cli, "build_llm", unbuildable)
    before = len(STORE.all())
    result = invoke(IDEA, "--yes", "--dir", str(tmp_path / "tree"))
    assert (result.exit_code, isinstance(result.exception, SystemExit)) == (1, True)
    assert "no credentials" in result.output
    assert len(STORE.all()) == before


SHIM = """#!{python}
import json, pathlib, sys
log = pathlib.Path({log!r})
responses = json.loads(pathlib.Path({responses!r}).read_text())
done = len(log.read_text().splitlines()) if log.exists() else 0
with log.open("a") as out:
    out.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({{"subtype": "success", "structured_output": responses[done]}}))
"""


def claude_shim(tmp_path: Path, monkeypatch) -> Path:
    """A `claude` binary on the real `ClaudeCodeLLM` path; returns the log of its calls."""
    log, responses, shim = tmp_path / "calls.log", tmp_path / "responses.json", tmp_path / "claude"
    responses.write_text(json.dumps(script()))
    shim.write_text(SHIM.format(python=sys.executable, log=str(log), responses=str(responses)))
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PROTOPILOT_CLAUDE_BIN", str(shim))
    return log


def test_backend_claude_code_drives_the_real_client_through_every_pass(tmp_path, monkeypatch):
    log = claude_shim(tmp_path, monkeypatch)
    result = invoke(IDEA, "--yes", "--backend", "claude-code", "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 0, result.output
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == len(PASS_NAMES)
    schemas = [json.loads(call[call.index("--json-schema") + 1]) for call in calls]
    assert schemas[1]["properties"]["topics"]["maxItems"] == 6
    assert schemas[2]["properties"]["edges"]["items"]["properties"]["to_topic"]["enum"] == SLUGS
    assert [t.slug for t in Plan.load(tmp_path / "tree").topics] == SLUGS


# -- off a terminal -------------------------------------------------------


@pytest.mark.parametrize("redirect", ["</dev/null", "<&-"], ids=["dev-null", "closed"])
def test_off_a_terminal_a_real_process_refuses_and_never_reaches_the_model(tmp_path, monkeypatch, redirect):
    log = claude_shim(tmp_path, monkeypatch)
    tree = tmp_path / "tree"
    argv = [sys.executable, "-m", "protopilot.cli", "plan", IDEA, "--backend", "claude-code", "--dir", str(tree)]
    done = subprocess.run(
        ["sh", "-c", f'exec "$@" {redirect}', "sh", *argv], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 1, done.stderr
    assert "stdin is not a terminal" in " ".join(done.stderr.split())
    assert "No model was called" in " ".join(done.stderr.split())
    assert not log.exists() and not tree.exists()


def test_off_a_terminal_the_refusal_comes_before_a_job_exists(tmp_path, no_backend):
    no_backend()
    before = len(STORE.all())
    assert invoke(IDEA, "--dir", str(tmp_path / "tree")).exit_code == 1
    assert len(STORE.all()) == before


def test_a_plan_for_another_idea_is_named_ahead_of_the_terminal_refusal(tmp_path, no_backend):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    no_backend()
    result = invoke("another idea", "--dir", str(tree))
    assert result.exit_code == 1
    assert IDEA in said(result) and "stdin is not a terminal" not in said(result)


# -- the review, end to end -----------------------------------------------


def reviewed(tree: Path, stdin: str) -> tuple:
    return invoke(IDEA, "--offline", "--dir", str(tree), stdin=stdin), tree


def test_dropping_below_the_floor_is_explained_and_the_plan_keeps_four(tmp_path, at_a_terminal):
    result, tree = reviewed(tmp_path / "tree", "drop 1\ndrop 1\ndrop 1\n\n")
    assert result.exit_code == 0, result.output
    assert "an outline holds at least 4 topics; add one first" in result.output
    assert len(Plan.load(tree).topics) == 4


def test_adding_past_the_ceiling_is_explained_and_the_plan_keeps_eight(tmp_path, at_a_terminal):
    result, tree = reviewed(tmp_path / "tree", "add One\na\nadd Two\nb\nadd Three\nc\n\n")
    assert result.exit_code == 0, result.output
    assert "an outline holds at most 8 topics; drop one first" in result.output
    assert [t.slug for t in Plan.load(tree).topics][-2:] == ["one", "two"]


def test_an_add_that_collides_changes_nothing(tmp_path, at_a_terminal):
    result, tree = reviewed(tmp_path / "tree", "add Risks\nmine\n\n")
    assert result.exit_code == 0, result.output
    assert "there is already a topic 'risks'" in result.output
    topics = Plan.load(tree).topics
    assert [t.slug for t in topics].count("risks") == 1 and "mine" not in [t.why for t in topics]


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("add", "add needs a title"),
        ("rename 1", "a topic needs a title"),
        ("rename 1   ", "a topic needs a title"),
        ("rename", "no topic ''"),
        ("drop", "no topic ''"),
        ("rename 9 Title", "no topic '9'"),
        ("ADD Title", "not a review command: 'ADD'"),
    ],
)
def test_a_review_line_it_cannot_use_changes_nothing(tmp_path, at_a_terminal, line, reason):
    clean, tree = reviewed(tmp_path / "clean", "\n")
    result, edited = reviewed(tmp_path / "tree", f"{line}\n\n")
    assert result.exit_code == 0, result.output
    assert reason in result.output
    assert snapshot(edited) == snapshot(tree)


def test_an_add_with_no_reason_is_refused_and_asks_again(tmp_path, at_a_terminal):
    result, tree = reviewed(tmp_path / "tree", "add Insurance\n\n\n")
    assert result.exit_code == 0, result.output
    assert "a topic needs a title and a line on why it matters" in result.output
    assert "insurance" not in [t.slug for t in Plan.load(tree).topics]


@pytest.mark.parametrize("answer", ["y", "YES", "  ", "Y"])
def test_every_acceptance_accepts(tmp_path, at_a_terminal, answer):
    result, tree = reviewed(tmp_path / "tree", f"{answer}\n")
    assert result.exit_code == 0, result.output
    assert (tree / "PLAN.md").is_file()


@pytest.mark.parametrize("answer", ["n", "No", "QUIT"])
def test_every_refusal_refuses_and_stops_the_model(tmp_path, at_a_terminal, model, answer):
    llm = model()
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"), stdin=f"{answer}\n")
    assert result.exit_code == 1
    assert llm.labels == ["scope", "outline"]
    assert not (tmp_path / "tree").exists()


@pytest.mark.parametrize(
    "stdin",
    ["", "drop 1\n", "rename 1 New title\nadd Insurance\n"],
    ids=["at-the-first-prompt", "after-an-edit", "inside-an-add"],
)
def test_eof_in_the_review_stops_with_nothing_written(tmp_path, at_a_terminal, model, stdin):
    llm = model()
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"), stdin=stdin)
    assert result.exit_code == 1
    assert "Aborted!" in result.output
    assert llm.labels == ["scope", "outline"]
    assert list(tmp_path.iterdir()) == []


def test_eof_at_a_question_stops_before_the_outline(tmp_path, at_a_terminal, model):
    llm = model(scope={**GOOD["scope"], "questions": ["Who runs it?"]})
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"))
    assert result.exit_code == 1
    assert llm.labels == ["scope"]
    assert list(tmp_path.iterdir()) == []


KEPT = [s for s in SLUGS if s != "safety"] + ["insurance"]


def edited_run(**overrides: object) -> dict:
    """A run whose later passes answer for the outline as the review below leaves it."""
    return {
        "connect": {"edges": [edge("insurance", "members"), edge("money", "space", "informs")]},
        "consider": consider_of(KEPT),
        "start": {"steps": [step("members")]},
        **overrides,
    }


REVIEW = "drop safety\nadd Insurance\nIt decides liability\nrename 1 The people\n\n"


def test_review_edits_are_what_every_later_pass_is_given(tmp_path, at_a_terminal, model):
    llm = model(**edited_run())
    tree = tmp_path / "tree"
    result = invoke(IDEA, "--dir", str(tree), stdin=REVIEW)
    assert result.exit_code == 0, result.output
    assert llm.labels == PASS_NAMES
    for call in llm.calls[2:4]:
        assert '"slug": "safety"' not in call["user"]
        assert '"slug": "insurance"' in call["user"] and "The people" in call["user"]
    assert llm.schemas["connect"]["properties"]["edges"]["items"]["properties"]["to_topic"]["enum"] == [
        *SLUGS[:5],
        "insurance",
    ]
    assert [t.slug for t in Plan.load(tree).topics] == KEPT
    assert "# The people" in (tree / "topics" / "members.md").read_text(encoding="utf-8")
    assert not (tree / "topics" / "safety.md").exists()


@pytest.mark.parametrize(
    ("overrides", "where"),
    [
        ({"connect": {"edges": [edge("safety", "members")]}}, "connect"),
        ({"connect": {"edges": [edge("members", "safety", "informs")]}}, "connect"),
        ({"consider": consider_of(SLUGS)}, "consider"),
        ({"consider": consider_of([*KEPT, "safety"])}, "consider"),
        ({"start": {"steps": [step("safety")]}}, "start"),
    ],
    ids=["edge-from", "edge-to", "row-instead-of-added", "extra-row", "step"],
)
def test_a_topic_dropped_in_review_cannot_come_back(tmp_path, at_a_terminal, model, overrides, where):
    model(**edited_run(**overrides))
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"), stdin=REVIEW)
    assert result.exit_code == 1
    assert f"pass '{where}' returned output that cannot be used" in said(result)
    assert not (tmp_path / "tree").exists()


def test_a_review_may_leave_depth_and_topic_count_apart_and_records_the_depth_asked(tmp_path, at_a_terminal, model):
    slugs = [f"t{n}" for n in range(4)]
    extra = [*slugs, "extra"]
    model(
        outline=outline_of(slugs),
        connect={"edges": []},
        consider=consider_of(extra),
        start={"steps": [step("extra")]},
    )
    tree = tmp_path / "tree"
    result = invoke(IDEA, "--depth", "shallow", "--dir", str(tree), stdin="add Extra\nwhy\n\n")
    assert result.exit_code == 0, result.output
    plan = Plan.load(tree)
    assert (plan.depth, len(plan.topics)) == ("shallow", 5)


def test_the_estimate_is_on_screen_before_the_review_asks(tmp_path, at_a_terminal, model):
    model()
    result = invoke(IDEA, "--dir", str(tmp_path / "tree"), stdin="\n")
    assert result.output.index("6 still to come") < result.output.index(cli.PLAN_REVIEW_PROMPT)


def test_each_line_of_a_run_is_printed_once(tmp_path, model):
    model()
    result = invoke(IDEA, "--yes", "--dir", str(tmp_path / "tree"))
    for name in PASS_NAMES:
        assert result.output.count(f"  pass {name}...") == 1
    assert result.output.count("  pass render...") == 1


# -- failure, through the CLI ---------------------------------------------

BROKEN = {
    "scope": {"goal": "only this"},
    "outline": {"topics": []},
    "connect": {"edges": "nonsense"},
    "consider": {"topics": []},
    "start": {"steps": []},
}


@pytest.mark.parametrize("name", PLAN_PASS_NAMES)
def test_a_pass_that_fails_leaves_no_tree_and_a_rerun_starts_over(tmp_path, model, name):
    tree = tmp_path / "tree"
    model(**{name: BROKEN[name]})
    result = invoke(IDEA, "--yes", "--dir", str(tree))
    assert result.exit_code == 1
    assert f"pass {name!r} returned output that cannot be used" in said(result)
    assert f"Nothing was written to {tree}. Rerunning starts over from scope" in said(result)
    assert list(tmp_path.iterdir()) == []

    again = model()
    assert invoke(IDEA, "--yes", "--dir", str(tree)).exit_code == 0
    assert again.labels == PASS_NAMES


@pytest.fixture
def render_dies(monkeypatch):
    """Fail the write of `sources.md` until the returned function is called."""
    real = Path.write_text

    def blocked(self, text, *args, **kwargs):
        if self.name == "sources.md":
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", blocked)
    return lambda: monkeypatch.setattr(Path, "write_text", real)


def test_a_rerun_after_a_render_failure_finishes_it_with_no_model(tmp_path, model, no_backend, render_dies):
    clean, tree = tmp_path / "clean", tmp_path / "tree"
    llm = model()
    failed = invoke(IDEA, "--yes", "--dir", str(tree))
    assert failed.exit_code == 1
    assert "disk full" in said(failed)
    assert f"{tree} holds the whole plan but maybe not every page." in said(failed)
    assert "with no model call" in said(failed)
    assert llm.labels == PASS_NAMES
    assert not (tree / "PLAN.md").exists()

    render_dies()
    model()
    assert invoke(IDEA, "--yes", "--dir", str(clean)).exit_code == 0
    no_backend()
    rerun = invoke(IDEA, "--dir", str(tree))  # no --yes, no terminal: a redraw needs neither
    assert rerun.exit_code == 0, rerun.output
    assert "drawing it again, with no model call" in said(rerun)
    assert snapshot(tree) == snapshot(clean)


def test_a_render_failure_keeps_what_the_review_decided(tmp_path, at_a_terminal, model, no_backend, render_dies):
    tree = tmp_path / "tree"
    model(**edited_run())
    assert invoke(IDEA, "--dir", str(tree), stdin=REVIEW).exit_code == 1
    render_dies()
    no_backend()
    assert invoke(IDEA, "--dir", str(tree)).exit_code == 0
    assert (tree / "topics" / "insurance.md").is_file()
    assert not (tree / "topics" / "safety.md").exists()


def test_a_rerun_that_fails_to_render_again_says_so_again(tmp_path, model, no_backend, render_dies):
    tree = tmp_path / "tree"
    model()
    assert invoke(IDEA, "--yes", "--dir", str(tree)).exit_code == 1
    no_backend()
    again = invoke(IDEA, "--dir", str(tree))
    assert again.exit_code == 1
    assert "holds the whole plan" in said(again)


# -- depth on a re-render -------------------------------------------------


def deep_slugs() -> list[str]:
    return [f"t{n}" for n in range(8)]


@pytest.fixture
def deep_plan(tmp_path, model):
    tree = tmp_path / "deep"
    slugs = deep_slugs()
    model(
        outline=outline_of(slugs),
        connect={"edges": []},
        consider=consider_of(slugs),
        start={"steps": [step("t0")]},
    )
    assert invoke(IDEA, "--yes", "--depth", "deep", "--dir", str(tree)).exit_code == 0
    return tree


@pytest.mark.parametrize("flags", [[], ["--depth", "deep"]], ids=["no-flag", "same-depth"])
def test_a_rerender_at_the_recorded_depth_redraws_with_no_backend(deep_plan, no_backend, flags):
    no_backend()
    before = snapshot(deep_plan)
    (deep_plan / "PLAN.md").write_text("hand edit")
    assert invoke(IDEA, "--dir", str(deep_plan), *flags).exit_code == 0
    assert snapshot(deep_plan) == before


@pytest.mark.parametrize("depth", ["shallow", "standard"])
def test_a_rerender_at_another_depth_is_refused_and_touches_nothing(deep_plan, no_backend, depth):
    no_backend()
    before = snapshot(deep_plan)
    result = invoke(IDEA, "--depth", depth, "--dir", str(deep_plan))
    assert result.exit_code == 1
    assert "already holds this plan at depth deep" in said(result)
    assert snapshot(deep_plan) == before


def test_depth_on_an_offline_plan_names_the_rerender_not_the_model(tmp_path):
    tree = tmp_path / "tree"
    assert invoke(IDEA, "--offline", "--yes", "--dir", str(tree)).exit_code == 0
    result = invoke(IDEA, "--offline", "--depth", "shallow", "--dir", str(tree))
    assert result.exit_code == 1
    assert "at depth none (offline baseline)" in said(result)


def test_a_model_plan_with_a_direction_and_an_answer_rerenders_from_its_own_command(
    tmp_path, at_a_terminal, model, no_backend
):
    tree = tmp_path / "tree"
    model(scope={**GOOD["scope"], "questions": ["Who runs it?"]})
    args = (IDEA, "--direction", "one town", "--dir", str(tree))
    assert invoke(*args, stdin="volunteers\n\n").exit_code == 0
    assert Plan.load(tree).constraints == ["one town", "Who runs it? volunteers"]
    no_backend()
    assert invoke(*args).exit_code == 0


# -- what the tester found ------------------------------------------------


def test_a_plan_json_that_cannot_be_written_means_what_the_message_says(tmp_path, model, monkeypatch):
    tree, real = tmp_path / "tree", Path.write_text

    def dies(self, text, *args, **kwargs):
        if "plan.json" in self.name:
            raise OSError("disk full")
        return real(self, text, *args, **kwargs)

    model()
    monkeypatch.setattr(Path, "write_text", dies)
    failed = invoke(IDEA, "--yes", "--dir", str(tree))
    assert failed.exit_code == 1
    assert f"Nothing was written to {tree}." in said(failed)
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setattr(Path, "write_text", real)
    model()
    assert invoke(IDEA, "--yes", "--dir", str(tree)).exit_code == 0


class Overtaken(Recording):
    """Another run takes the tree while `start` is thinking."""

    def __init__(self, tree: Path):
        super().__init__(script())
        self.tree = tree

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        if label == "start":
            self.tree.mkdir()
        return super().structured(system=system, user=user, schema=schema, label=label)


def test_a_refusal_from_the_last_half_says_only_the_refusal(tmp_path, monkeypatch):
    tree = tmp_path / "tree"
    monkeypatch.setattr(cli, "build_llm", lambda **_: Overtaken(tree))
    result = invoke(IDEA, "--yes", "--dir", str(tree))
    assert result.exit_code == 1
    assert "holds no plan; refusing to overwrite it" in said(result)
    assert "Rerun" not in said(result) and "whole plan" not in said(result) and "PlanRefused" not in said(result)


@pytest.mark.parametrize("flags", [["--backend", "offline"], ["--offline"]])
def test_the_depth_refusal_names_no_flag_the_person_did_not_type(tmp_path, backends, flags):
    result = invoke(IDEA, "--yes", "--depth", "deep", "--dir", str(tmp_path / "tree"), *flags)
    assert result.exit_code == 1
    assert "the backend for this run is offline" in said(result)
    assert "--offline" not in said(result)


@pytest.mark.parametrize(
    ("stdin", "why_asked", "reason"),
    [
        ("add One\na\nadd Two\nb\nadd Three\n\n", 2, "at most 8"),
        ("add Scope\n\n", 0, "already a topic 'scope'"),
    ],
    ids=["limit", "collision"],
)
def test_an_add_that_cannot_land_is_refused_before_asking_why(tmp_path, at_a_terminal, stdin, why_asked, reason):
    result = invoke(IDEA, "--offline", "--dir", str(tmp_path / "tree"), stdin=stdin)
    assert result.exit_code == 0, result.output
    assert reason in said(result)
    assert result.output.count("Why does it matter?") == why_asked


def test_first_contact_leads_with_planning_and_new_stays_about_prototypes():
    assert "into a plan you can work from" in CliRunner().invoke(cli.main, ["--help"]).output
    assert "prototype" in CliRunner().invoke(cli.main, ["new", "--help"]).output.lower()
