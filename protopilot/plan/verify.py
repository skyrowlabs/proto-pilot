"""Is this plan coherent and traceable? One named check per bullet of *What "verified" means*.

Every check is a pure function of a `Plan` and its pages, the dict `render.render`
returns and `render.read` reads back, so the same check judges what was drawn and
what landed. A check ends in one of three states, and `NO_SUBJECT` is not a pass:
it had nothing to look at, proved nothing, and the green line names it apart.

Green proves structure, never truth: see `green_line`, and the spec for why.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import NamedTuple

from protopilot.plan import render
from protopilot.plan.model import DREAM_WORD_CAP, Edge, Plan
from protopilot.verify import VerifyResult

PASSED = "passed"
FAILED = "failed"
NO_SUBJECT = "no subject"

#: Below this a dream's words are too common to call a copy, so only longer text is compared.
MIN_LEAK_CHARS = 16
LEAK_FIELDS = ("title", "what_if", "takes", "reason", "if_adopted")
CAPPED_FIELDS = ("title", "what_if", "takes")

Pages = dict[str, str]

RUNBOOK = """\
# Runbook

proto-pilot could not get this plan to green in {attempts} check(s), so it handed the
tree over as it stands. **Nothing here is verified.** Everything below is what it knows.

## Still wrong

{wrong}

## What was tried

{tried}

## Checks with no subject

These neither failed nor held: they had nothing to look at.

{empty}

## What to do

`.protopilot/plan.json` is the truth and every page is drawn from it, so a fix goes
there. Rerunning the same command verifies it again and redraws it, with no model call.
To have the model try again, remove this directory and rerun from the start.
"""


@dataclass(frozen=True)
class CheckResult:
    name: str
    state: str
    summary: str
    problems: tuple[str, ...] = ()

    def report(self) -> str:
        return "\n".join([f"[{self.name}] {self.summary}", *(f"- {problem}" for problem in self.problems)])


@dataclass(frozen=True)
class PlanVerdict(VerifyResult):
    """`stage` is the first failing check's name, and `checks` holds every check's result."""

    checks: tuple[CheckResult, ...] = ()

    def named(self, state: str) -> list[str]:
        return [check.name for check in self.checks if check.state == state]

    @property
    def failed(self) -> list[CheckResult]:
        return [check for check in self.checks if check.state == FAILED]

    def report(self) -> str:
        return "\n\n".join(check.report() for check in self.failed)


def _judged(name: str, subject: object, problems: list[str], advice: str, nothing: str) -> CheckResult:
    """A check's result: any problem is red, whatever else is true; no subject is never a pass."""
    if problems:
        more = f" ({len(problems) - 1} more below.)" if len(problems) > 1 else ""
        return CheckResult(name, FAILED, f"{problems[0]}. {advice}{more}", tuple(problems))
    if not subject:
        return CheckResult(name, NO_SUBJECT, nothing)
    return CheckResult(name, PASSED, "Held.")


def topic_map(plan: Plan, pages: Pages) -> CheckResult:
    """Every topic is in the map; every edge names two topics that exist."""
    known = {topic.slug for topic in plan.topics}
    entry = pages.get(render.PLAN_FILE, "")
    problems = [f"page {name} is missing" for name in sorted(set(render.render(plan)) - set(pages))]
    problems += [
        f"topic {topic.slug} is not in the map on {render.PLAN_FILE}"
        for topic in plan.topics
        if f"({render.TOPICS_DIR}/{topic.slug}.md)" not in entry
    ]
    for edge in plan.edges:
        ghosts = sorted({edge.from_topic, edge.to_topic} - known)
        if ghosts:
            line = f"{edge.from_topic} {edge.kind} {edge.to_topic}"
            problems.append(f"the edge {line} names what is not a topic: {', '.join(ghosts)}")
    advice = "Point each edge at a real topic, and rerun to draw every page."
    return _judged("topic_map", plan.topics, problems, advice, "The plan has no topics to map.")


def _reachable(start: str, graph: dict[str, set[str]]) -> set[str]:
    seen, stack = {start}, [start]
    while stack:
        for target in graph.get(stack.pop(), set()) - seen:
            seen.add(target)
            stack.append(target)
    return seen


def cycle_edges(plan: Plan) -> list[Edge]:
    """The `depends-on` edges on a loop, a topic depending on itself included."""
    links = [edge for edge in plan.edges if edge.kind == "depends-on"]
    graph: dict[str, set[str]] = {}
    for edge in links:
        graph.setdefault(edge.from_topic, set()).add(edge.to_topic)
    return [edge for edge in links if edge.from_topic in _reachable(edge.to_topic, graph)]


def no_cycles(plan: Plan, pages: Pages) -> CheckResult:
    """`depends-on` has no cycles."""
    looped = cycle_edges(plan)
    problems = [f"{edge.from_topic} depends on {edge.to_topic}, and that link is on a loop" for edge in looped]
    subject = [edge for edge in plan.edges if edge.kind == "depends-on"]
    advice = "A loop leaves nothing to settle first: remove or retype one of its links."
    return _judged("no_cycles", subject, problems, advice, "The plan has no `depends-on` edges.")


def findings_traced(plan: Plan, pages: Pages) -> CheckResult:
    """Every finding has a source in `sources.md`, or is labelled an assumption."""
    known = {source.id for source in plan.sources}
    problems = []
    for topic in plan.topics:
        for finding in topic.findings:
            ghosts = sorted(set(finding.source_ids) - known)
            if ghosts:
                said = f"{render.SOURCES_FILE} does not hold {', '.join(ghosts)}"
                problems.append(f"topic {topic.slug}: {said}, and a finding cites it: {finding.text!r}")
            elif not (finding.assumption or finding.source_ids):
                problems.append(f"topic {topic.slug}: nothing backs this finding: {finding.text!r}")
    subject = [finding for topic in plan.topics for finding in topic.findings]
    advice = "Cite a source the plan holds, or label the finding an assumption."
    return _judged("findings_traced", subject, problems, advice, "The plan has no findings to trace.")


def sources_fetched(plan: Plan, pages: Pages) -> CheckResult:
    """Every source was fetched with usable content during this run, not typed by the model."""
    problems = [
        f"source {source.id} ({source.url}) was never fetched with usable content"
        for source in plan.sources
        if not source.fetched
    ]
    if plan.researched and not plan.sources:
        problems.append("the plan says it was researched, and it holds no source")
    advice = "Only a research run can record a fetch, so remove the source or research it."
    return _judged("sources_fetched", plan.sources, problems, advice, "The plan has no sources to check.")


class StepFault(NamedTuple):
    topic: str
    problem: str


def step_faults(plan: Plan) -> list[StepFault]:
    """Each step against those before it. A first step is ready because nothing came before it."""
    needs = plan.needs()
    covered: set[str] = set()
    faults = []
    for number, step in enumerate(plan.steps, start=1):
        waiting = sorted(needs.get(step.topic, set()) - covered)
        if step.topic not in needs:
            faults.append(StepFault(step.topic, f"step {number} names a topic that does not exist: {step.topic}"))
        elif step.topic in covered:
            faults.append(StepFault(step.topic, f"step {number} ({step.topic}) repeats a topic"))
        elif waiting:
            needed = f"waits on {', '.join(waiting)}, which no earlier step covers"
            faults.append(StepFault(step.topic, f"step {number} ({step.topic}) {needed}"))
        covered.add(step.topic)
    return faults


def start_order(plan: Plan, pages: Pages) -> CheckResult:
    """The first step has no unmet dependency, and no later one jumps ahead of what it needs."""
    problems = [fault.problem for fault in step_faults(plan)]
    if not plan.steps:
        problems.append("the plan has no steps, so it does not say where to begin")
    advice = "Start from a topic that depends on nothing, and cover each dependency before what needs it."
    return _judged("start_order", plan.steps, problems, advice, "")


def dreams_shaped(plan: Plan, pages: Pages) -> CheckResult:
    """Every dream has an anchor topic, a verdict, and fits its word cap."""
    known = {topic.slug for topic in plan.topics}
    problems = []
    for dream in plan.dreams:
        words = sum(len(getattr(dream, field).split()) for field in CAPPED_FIELDS)
        if dream.anchor not in known:
            problems.append(f"dream {dream.id} is anchored to {dream.anchor!r}, which is not a topic")
        if dream.verdict is None:
            problems.append(f"dream {dream.id} has no verdict")
        if words > DREAM_WORD_CAP:
            problems.append(f"dream {dream.id} runs to {words} words, past the cap of {DREAM_WORD_CAP}")
    advice = "Anchor it to a real topic, give it a verdict, and cut it to the cap; one that needs more is a topic."
    return _judged("dreams_shaped", plan.dreams, problems, advice, "The plan has no dreams.")


def _plain(text: str) -> str:
    """Words alone, so a copy with other case, punctuation or escaping still reads as a copy."""
    return " ".join(re.findall(r"\w+", html.unescape(text).casefold()))


def dreams_apart(plan: Plan, pages: Pages) -> CheckResult:
    """No dream text appears in a topic file."""
    topics = {name: _plain(page) for name, page in pages.items() if name.startswith(f"{render.TOPICS_DIR}/")}
    problems = []
    for dream in plan.dreams:
        for field in LEAK_FIELDS:
            words = _plain(getattr(dream, field))
            if len(words) >= MIN_LEAK_CHARS:
                problems += [
                    f"{name} repeats the {field} of dream {dream.id}" for name, page in topics.items() if words in page
                ]
    advice = "A dream must not read as a finding: take its words out of the topic."
    return _judged("dreams_apart", plan.dreams, problems, advice, "The plan has no dreams to keep apart.")


CHECKS: tuple[Callable[[Plan, Pages], CheckResult], ...] = (
    topic_map,
    no_cycles,
    findings_traced,
    sources_fetched,
    start_order,
    dreams_shaped,
    dreams_apart,
)


def _listed(names: Iterable[str]) -> str:
    return ", ".join(names)


def green_line(results: Iterable[CheckResult]) -> str:
    """The sentence a green run ends on, which claims only what these checks can show."""
    results = list(results)
    held = [result.name for result in results if result.state == PASSED]
    empty = [result.name for result in results if result.state == NO_SUBJECT]
    parts = [
        "Green: this plan is coherent and traceable, which is not the same as true.",
        f"Held: {_listed(held)}.",
    ]
    if empty:
        parts.append(f"No subject, so these proved nothing: {_listed(empty)}.")
    parts.append("A source retrieved this run proves a summary of it was read, not that a claim is in the original.")
    return " ".join(parts)


def verdict(plan: Plan, pages: Pages) -> PlanVerdict:
    """Every check, always, so a repair that mends one cannot hide another it broke."""
    results = tuple(check(plan, pages) for check in CHECKS)
    failed = [result for result in results if result.state == FAILED]
    if failed:
        return PlanVerdict(False, failed[0].name, failed[0].summary, checks=results)
    return PlanVerdict(True, "", green_line(results), checks=results)


def runbook(result: PlanVerdict, attempts: int, tried: list[str]) -> str:
    """The floor: what is still wrong, what was tried, and what to do about it."""
    empty = [check for check in result.checks if check.state == NO_SUBJECT]
    return RUNBOOK.format(
        attempts=attempts,
        wrong=result.report(),
        tried="\n".join(f"{n}. {line}" for n, line in enumerate(tried, start=1)) or "No repair ran.",
        empty="\n".join(f"- {check.name}: {check.summary}" for check in empty) or "None.",
    )
