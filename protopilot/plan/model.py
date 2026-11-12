"""The plan: what `.protopilot/plan.json` holds, and all the markdown is drawn from.

Validators here refuse only what is unsafe to store: a topic slug becomes a
filename, so it is checked, and two topics sharing one would lose a file.
Coherence (dangling edges, unlabelled findings, cycles) stays representable,
because the verifier has to load a broken plan to name what is wrong with it.
A dream's cap is coherence too: over it, a dream stays loadable and goes red.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: Where a plan keeps its own files inside its tree. A plan on disk is found by this name.
PLAN_DIR = ".protopilot"
PLAN_FILENAME = "plan.json"
#: A slug becomes a filename and a link target, so it is lowercase, underscored and starts with a letter.
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
#: A slug names a file or a directory, and a filesystem refuses a long one at write time.
MAX_SLUG_LENGTH = 64

EdgeKind = Literal["depends-on", "informs", "conflicts-with"]
#: `proposed` and `set-aside` are a model's to give; `dropped` and `promoted` only a person's.
Verdict = Literal["proposed", "set-aside", "dropped", "promoted"]
MODEL_VERDICTS: tuple[Verdict, ...] = ("proposed", "set-aside")
#: `not judged` is the offline twin's, which cannot rank anything.
Rating = Literal["low", "medium", "high", "not judged"]
MODEL_RATINGS = ("low", "medium", "high")
TWIN_RATINGS = (*MODEL_RATINGS, "not judged")
RUBRIC = ("pull", "reach", "cost", "fit")
Depth = Literal["shallow", "standard", "deep"]

#: The topics an outline holds at each `--depth`. Depth is also the research effort.
TOPIC_COUNTS: dict[str, int] = {"shallow": 4, "standard": 6, "deep": 8}
DEFAULT_DEPTH = "standard"
MIN_TOPICS = min(TOPIC_COUNTS.values())
MAX_TOPICS = max(TOPIC_COUNTS.values())
#: A title, one sentence, and a phrase. Unconstrained dreams measured a median of 42
#: words and a maximum of 51, so a cap above that would never bind; a dream that wants
#: more is a topic. The fields are the budget, so spaced text the schema allows fits the cap.
DREAM_FIELD_WORDS = {"title": 6, "what_if": 26, "takes": 12}
DREAM_WORD_CAP = sum(DREAM_FIELD_WORDS.values())
#: What ends a word in the schema's pattern. A model held to `\S+` joined 28 words with
#: hyphens, so punctuation has to break one. `dream_words` is the exact count, and stricter.
WORD_BREAK = r"\s/_,.;:!?\u00b7\u200b\u2010-\u2015\u2212-"
#: The longest run of letters that counts as one word, so nothing is free for having no spaces.
MOST_WORD_CHARS = 24
#: A run of letters, with the apostrophe of "it's" or "don't" kept in it.
WORD = re.compile(r"[^\W_]+(?:['\u2019][^\W_]{1,2})?")
#: Han and kana, which are written without spaces, so no space can end a word in them.
UNSPACED = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]")
DREAM_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def _checked_slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"slug must be snake_case: {value!r}")
    if len(value) > MAX_SLUG_LENGTH:
        raise ValueError(f"slug must be at most {MAX_SLUG_LENGTH} characters: {value!r}")
    return value


def _checked_dream_id(value: str) -> str:
    if not DREAM_ID.fullmatch(value):
        raise ValueError(f"a dream id must be a short lowercase name: {value!r}")
    return value


def _checked_topic_link(value: str) -> str:
    return _checked_slug(value) if value else value


def dream_words(text: str) -> int:
    """Words in `text`, whatever joins them: two unspaced characters are one, and a symbol is one."""
    count = sum(unicodedata.category(char) == "So" for char in text)
    for run in WORD.findall(text):
        unspaced = len(UNSPACED.findall(run))
        count += (unspaced + 1) // 2 + -(-(len(run) - unspaced) // MOST_WORD_CHARS)
    return count


class _Record(BaseModel):
    # A misspelt field in plan.json is an error, never a value quietly dropped.
    model_config = ConfigDict(extra="forbid")


class Source(_Record):
    id: str
    title: str
    url: str
    # What research said when it made this source. The verifier reads the ledger, never this.
    fetched: bool = False


#: `nothing cited` is a call that worked and cited no page it fetched, which is not research.
ResearchState = Literal["researched", "failed", "nothing cited"]


class Fetch(_Record):
    """One `WebFetch` in a research transcript, and whether it brought back usable content."""

    url: str
    usable: bool
    why: str = Field(default="", description="Why the heuristic called it unusable")


class TopicResearch(_Record):
    """One topic's research: the ledger drawn from its transcript, never from what the model said."""

    topic: str
    state: ResearchState
    failure: str = ""
    # The transcript's file under `.protopilot/research/`, and its hash, so an edit to either shows.
    transcript: str = ""
    sha256: str = ""
    fetches: list[Fetch] = Field(default_factory=list)
    # URLs a finding cited that no usable fetch backs; those findings were made assumptions.
    unfetched: list[str] = Field(default_factory=list)


class Finding(_Record):
    text: str
    # Required, so nothing reaches a plan unlabelled by default.
    assumption: bool
    source_ids: list[str] = Field(default_factory=list)


class Topic(_Record):
    slug: str
    title: str
    why: str = Field(description="One line on why this topic matters to the idea")
    findings: list[Finding] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)

    _slug = field_validator("slug")(_checked_slug)


class Edge(_Record):
    """`from_topic` is the subject: for `depends-on`, it needs `to_topic`."""

    from_topic: str
    to_topic: str
    kind: EdgeKind


class Step(_Record):
    topic: str
    action: str
    why: str


class Dream(_Record):
    id: str
    title: str
    what_if: str
    lens: str
    anchor: str = Field(description="The topic slug this dream extends")
    takes: str = Field(description="What it would take")
    verdict: Verdict | None = None
    reason: str = ""
    if_adopted: str = ""
    # Four answers, never summed: one number would hide why a dream ranked where it did.
    pull: Rating | None = None
    reach: Rating | None = None
    cost: Rating | None = None
    fit: Rating | None = None
    promoted_to: str = Field(default="", description="The topic a person turned this dream into")

    _id = field_validator("id")(_checked_dream_id)
    _promoted_to = field_validator("promoted_to")(_checked_topic_link)


class Plan(_Record):
    slug: str
    title: str
    idea: str
    direction: str = ""
    goal: str = ""
    audience: str = ""
    horizon: str = ""
    constraints: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    # False unless research ran, so a plan that forgets to say is stamped.
    researched: bool = False
    # What was asked for, and what research will read. None for the offline
    # baseline, which has no depth, and then plan.json omits the key.
    depth: Depth | None = None
    topics: list[Topic] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    dreams: list[Dream] = Field(default_factory=list)
    # Why the run's dreaming stopped, for `dreams.md`. Empty is the usual case, and then
    # plan.json omits the key. A failed dream costs the extras, never the plan.
    dream_failure: str = ""
    sources: list[Source] = Field(default_factory=list)
    # The research ledger, one record per topic research was tried on. Empty for a plan never
    # researched, and then plan.json omits it, as it omits `research_failure`.
    research: list[TopicResearch] = Field(default_factory=list)
    # Why research did not run at all, for `PLAN.md`.
    research_failure: str = ""

    _slug = field_validator("slug")(_checked_slug)

    @model_validator(mode="after")
    def _one_file_per_topic(self) -> "Plan":
        slugs = [t.slug for t in self.topics]
        repeated = sorted({s for s in slugs if slugs.count(s) > 1})
        if repeated:
            raise ValueError(f"topic slugs must be unique: {', '.join(repeated)}")
        return self

    def revised(self, **changes: object) -> "Plan":
        """A copy with `changes`, validated: `model_copy` would skip the slug checks."""
        return Plan.model_validate({**self.model_dump(), **changes})

    def needs(self) -> dict[str, set[str]]:
        """Each topic's `depends-on` targets; an edge from a topic the plan lacks is the map's to report."""
        needs: dict[str, set[str]] = {topic.slug: set() for topic in self.topics}
        for edge in self.edges:
            if edge.kind == "depends-on" and edge.from_topic in needs:
                needs[edge.from_topic].add(edge.to_topic)
        return needs

    def research_of(self, slug: str) -> TopicResearch | None:
        return next((record for record in self.research if record.topic == slug), None)

    def summary(self) -> str:
        """What the outline checkpoint prints; a topic left out here is one nobody reviews."""
        lines = [self.title, f"  goal: {self.goal or 'not established'}"]
        lines += [f"  audience: {self.audience}"] if self.audience else []
        lines += [f"  horizon: {self.horizon}"] if self.horizon else []
        lines += [f"  constraint: {item}" for item in self.constraints]
        lines += [f"  open question: {item}" for item in self.questions]
        if self.depth:
            lines.append(f"  depth: {self.depth} ({len(self.topics)} topics)")
        lines.append("  topics:")
        lines += [f"    {n}. {t.title} ({t.slug}): {t.why}" for n, t in enumerate(self.topics, start=1)]
        return "\n".join(lines)

    # -- persistence ---------------------------------------------------

    @classmethod
    def load(cls, tree: Path) -> "Plan":
        return cls.model_validate_json(plan_path(tree).read_text(encoding="utf-8"))

    def save(self, tree: Path) -> Path:
        """Land plan.json whole or not at all; a save that fails leaves the disk as it found it."""
        path = plan_path(tree)
        data = self.model_dump(mode="json")
        if self.depth is None:
            del data["depth"]
        for key in ("dream_failure", "research", "research_failure"):
            if not data[key]:
                del data[key]
        absent = [folder for folder in (path.parent, *path.parent.parents) if not folder.exists()]
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(temp, path)
        except BaseException:
            with suppress(OSError):
                temp.unlink(missing_ok=True)
                for folder in absent:
                    folder.rmdir()
            raise
        return path


def plan_path(tree: Path) -> Path:
    return Path(tree) / PLAN_DIR / PLAN_FILENAME
