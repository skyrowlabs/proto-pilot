"""Is this plan coherent and traceable? One named check per bullet of *What "verified" means*.

Every check is a pure function of a `Plan` and its pages, the dict `render.render`
returns and `render.read` reads back, so the same check judges what was drawn and
what landed. A check ends in one of three states, and `NO_SUBJECT` is not a pass:
it had nothing to look at, proved nothing, and the green line names it apart.

Green proves structure, never truth, and `green_line` claims only what held.

`dreams_apart` reads what a topic says, not what every topic page draws. A promoted
dream's words are the topic's now, and a dropped dream's `--why` is a person's, so
neither is compared. It catches a copy, a changed word or two included. A paraphrase
passes, and so does a script written without spaces outside Han and kana, whose text
it cannot split into words, and a `takes` under `MIN_TAKES_WORDS`.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import NamedTuple

from protopilot.plan import ledger, render
from protopilot.plan.model import DREAM_WORD_CAP, UNSPACED, Dream, Edge, Plan, dream_words

PASSED = "passed"
FAILED = "failed"
NO_SUBJECT = "no subject"

#: Below this a dream's words are too common to call a copy, so only longer text is compared.
MIN_LEAK_CHARS = 16
#: From this length one word in this many may differ and still be a copy; shorter text must match.
WORDS_PER_CHANGE = 6
LEAK_FIELDS = ("title", "what_if", "takes", "reason", "if_adopted")
CAPPED_FIELDS = ("title", "what_if", "takes")
#: `takes` is the field of ordinary phrases, so a short one in a topic is a coincidence.
MIN_TAKES_WORDS = 6

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
class VerifyResult:
    """One verdict: whether it held, the stage that decided it, and what to show a person."""

    ok: bool
    stage: str
    summary: str
    output: str = ""
    logs: str = ""

    def report(self) -> str:
        parts = [f"[{self.stage}] {self.summary}"]
        if self.output.strip():
            parts.append("--- command output ---\n" + self.output.strip())
        if self.logs.strip():
            parts.append("--- container logs ---\n" + self.logs.strip())
        return "\n\n".join(parts)


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

    @property
    def problems(self) -> int:
        """How much is wrong, counted so two verdicts can be compared."""
        return sum(len(check.problems) for check in self.failed)

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


def loops(plan: Plan) -> list[list[Edge]]:
    """Every simple `depends-on` loop, once each, as its links, so two sharing a topic stay two."""
    links = {(edge.from_topic, edge.to_topic): edge for edge in plan.edges if edge.kind == "depends-on"}
    found: list[list[Edge]] = []

    def walk(start: str, path: list[str]) -> None:
        for source, target in sorted(links):
            if source != path[-1]:
                continue
            if target == start:
                found.append([links[pair] for pair in zip(path, [*path[1:], start])])
            elif target > start and target not in path:
                walk(start, [*path, target])

    for topic in sorted({source for source, _ in links}):
        walk(topic, [topic])
    return found


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


def _borrowed(plan: Plan) -> list[str]:
    """Each cited finding whose source its own topic's research never fetched. No ledger, no subject."""
    if not plan.research:
        return []
    urls = {source.id: ledger.normal(source.url) for source in plan.sources}
    problems = []
    for topic in plan.topics:
        record = plan.research_of(topic.slug)
        own = {ledger.normal(f.url) for f in record.fetches if f.usable} if record else set()
        for finding in topic.findings:
            stray = sorted(i for i in finding.source_ids if not finding.assumption and i in urls and urls[i] not in own)
            if stray:
                problems.append(f"topic {topic.slug} cites {', '.join(stray)}, which its own research never fetched")
    return problems


def sources_fetched(plan: Plan, pages: Pages) -> CheckResult:
    """Every source was fetched with usable content during this run, not typed by the model.

    The evidence is the research ledger, never `Source.fetched`, so typing `true` there earns
    nothing. The pipeline redraws the ledger from the run's transcripts before a loaded plan
    is checked, so typing a fetch into the ledger earns nothing either.
    """
    usable = ledger.usable_urls(plan)
    problems = []
    for source in plan.sources:
        if ledger.normal(source.url) not in usable:
            typed = ", though plan.json marks it fetched" if source.fetched else ""
            problems.append(f"source {source.id} ({source.url}) has no usable fetch in this run's ledger{typed}")
    if plan.researched and not plan.sources:
        problems.append("the plan says it was researched, and it holds no source")
    problems += _borrowed(plan)
    advice = "Only a research run can record a fetch, so remove the source or research it."
    return _judged("sources_fetched", plan.sources, problems, advice, "The plan has no sources to check.")


class StepFault(NamedTuple):
    index: int
    topic: str
    problem: str


def step_faults(plan: Plan) -> list[StepFault]:
    """Each step against those before it. A first step is ready because nothing came before it."""
    needs = plan.needs()
    covered: set[str] = set()
    faults = []
    for index, step in enumerate(plan.steps):
        number, waiting = index + 1, sorted(needs.get(step.topic, set()) - covered)
        if step.topic not in needs:
            faults.append(
                StepFault(index, step.topic, f"step {number} names a topic that does not exist: {step.topic}")
            )
        elif step.topic in covered:
            faults.append(StepFault(index, step.topic, f"step {number} ({step.topic}) repeats a topic"))
        elif waiting:
            needed = f"waits on {', '.join(waiting)}, which no earlier step covers"
            faults.append(StepFault(index, step.topic, f"step {number} ({step.topic}) {needed}"))
        covered.add(step.topic)
    return faults


def start_order(plan: Plan, pages: Pages) -> CheckResult:
    """The first step has no unmet dependency, and no later one jumps ahead of what it needs."""
    problems = [fault.problem for fault in step_faults(plan)]
    if not plan.steps:
        problems.append("the plan has no steps, so it does not say where to begin")
    advice = "Start from a topic that depends on nothing, and cover each dependency before what needs it."
    return _judged("start_order", plan.steps, problems, advice, "")


def dream_length(dream: Dream) -> int:
    return sum(dream_words(getattr(dream, field)) for field in CAPPED_FIELDS)


def dreams_shaped(plan: Plan, pages: Pages) -> CheckResult:
    """Every dream has an anchor topic, a verdict, and fits its word cap, and one id means one dream."""
    known = {topic.slug for topic in plan.topics}
    ids = [dream.id for dream in plan.dreams]
    problems = [
        f"more than one dream has the id {repeated}" for repeated in sorted({i for i in ids if ids.count(i) > 1})
    ]
    for dream in plan.dreams:
        words = dream_length(dream)
        if dream.anchor not in known:
            problems.append(f"dream {dream.id} is anchored to {dream.anchor!r}, which is not a topic")
        if dream.verdict is None:
            problems.append(f"dream {dream.id} has no verdict")
        if (dream.verdict == "promoted") != (dream.promoted_to in known):
            problems.append(f"dream {dream.id} is {dream.verdict}, and names the topic {dream.promoted_to!r}")
        if words > DREAM_WORD_CAP:
            problems.append(f"dream {dream.id} runs to {words} words, past the cap of {DREAM_WORD_CAP}")
    advice = "Anchor it to a real topic, give it a verdict, and cut it to the cap; one that needs more is a topic."
    return _judged("dreams_shaped", plan.dreams, problems, advice, "The plan has no dreams.")


def plain(text: str) -> str:
    """Words alone, so a copy in other case, accents, punctuation or escaping still reads as one."""
    folded = unicodedata.normalize("NFKD", html.unescape(text)).casefold()
    bare = "".join(char for char in folded if not unicodedata.combining(char))
    spaced = UNSPACED.sub(lambda char: f" {char.group()} ", bare)
    return " ".join(re.findall(r"[^\W_]+", spaced))


def copied(words: str, line: str) -> bool:
    """Is `words` in `line` as whole words, allowing a changed word per `WORDS_PER_CHANGE`?"""
    if f" {words} " in f" {line} ":
        return True
    ours, theirs = words.split(), line.split()
    slack = len(ours) // WORDS_PER_CHANGE
    if not slack or len(set(ours) & set(theirs)) < len(set(ours)) - slack:
        return False
    blocks = [block for block in SequenceMatcher(None, ours, theirs, False).get_matching_blocks() if block.size]
    if not blocks:
        return False
    matched = sum(block.size for block in blocks)
    spread = blocks[-1].b + blocks[-1].size - blocks[0].b
    return len(ours) - matched <= slack and spread - matched <= slack


def _compared(dream: Dream, field: str, words: str) -> bool:
    if dream.verdict == "promoted" or (dream.verdict == "dropped" and field == "reason"):
        return False
    return len(words) >= MIN_LEAK_CHARS and (field != "takes" or len(words.split()) >= MIN_TAKES_WORDS)


class Leak(NamedTuple):
    dream: str
    field: str
    page: str


def leaks(plan: Plan, pages: Pages) -> tuple[list[Leak], bool]:
    """Every copy of an offered dream's text in what a topic says, and whether anything was long enough to compare."""
    own = render.furniture(plan)
    topics = {
        name: [plain(line) for line in page.splitlines() if line not in own.get(name, ())]
        for name, page in pages.items()
        if name.startswith(f"{render.TOPICS_DIR}/")
    }
    # A dream may repeat the plan's own name: a topic quoting it is not quoting the dream.
    names = {plain(plan.title), plain(plan.idea), plain(plan.direction)}
    found, compared = [], False
    for dream in plan.dreams:
        for field in LEAK_FIELDS:
            words = plain(getattr(dream, field))
            if _compared(dream, field, words) and words not in names:
                compared = True
                found += [
                    Leak(dream.id, field, name)
                    for name, lines in topics.items()
                    if any(copied(words, line) for line in lines)
                ]
    return found, compared


def dreams_apart(plan: Plan, pages: Pages) -> CheckResult:
    """No dream text appears in what a topic says. Text too short to compare is no subject."""
    found, compared = leaks(plan, pages)
    problems = [f"{leak.page} repeats the {leak.field} of dream {leak.dream}" for leak in found]
    advice = "A dream must not read as a finding: take its words out of the topic."
    return _judged("dreams_apart", compared, problems, advice, "The plan has no dream text long enough to compare.")


CHECKS: tuple[Callable[[Plan, Pages], CheckResult], ...] = (
    topic_map,
    no_cycles,
    findings_traced,
    sources_fetched,
    start_order,
    dreams_shaped,
    dreams_apart,
)


#: What each dream check read, for the green line to say only of the ones that held.
DREAM_CLAIMS = (("dreams_shaped", "their shape"), ("dreams_apart", "that they stay apart"))


def _listed(names: Iterable[str]) -> str:
    return ", ".join(names)


def _claim(held: list[str]) -> str:
    """What green may say: only what checks with a subject held, then the limit."""
    limit = "which is not the same as true."
    if "findings_traced" in held and "sources_fetched" in held:
        return f"this plan is coherent and traceable, {limit}"
    labelled = " and every finding is cited or labelled an assumption" if "findings_traced" in held else ""
    return f"this plan's structure holds{labelled}, {limit}"


def green_line(results: Iterable[CheckResult]) -> str:
    """The sentence a green run ends on, built from what held so it claims nothing else."""
    results = list(results)
    held = [result.name for result in results if result.state == PASSED]
    empty = [result.name for result in results if result.state == NO_SUBJECT]
    parts = [f"Green: {_claim(held)}"]
    if "sources_fetched" not in held:
        parts.append("Nothing in it traces to a source.")
    parts.append(f"Held: {_listed(held)}.")
    if empty:
        parts.append(f"No subject, so these proved nothing: {_listed(empty)}.")
    read = [said for name, said in DREAM_CLAIMS if name in held]
    if read:
        parts.append(f"Dreams are guesses, not findings: their checks read {' and '.join(read)}.")
    if "sources_fetched" in held:
        parts.append(
            "Every source was fetched this run and read through a summary of the page, which is not the page: "
            "a citation shows that summary was read, never that the claim is in the source."
        )
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
