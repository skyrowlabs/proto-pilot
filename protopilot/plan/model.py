"""The plan: what `.protopilot/plan.json` holds, and all the markdown is drawn from.

Validators here refuse only what is unsafe to store: a topic slug becomes a
filename, so it is checked, and two topics sharing one would lose a file.
Coherence (dangling edges, unlabelled findings, cycles) stays representable,
because the verifier has to load a broken plan to name what is wrong with it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from protopilot.spec import SLUG_RE, SPEC_DIR

PLAN_FILENAME = "plan.json"
#: A slug names a file or a directory, and a filesystem refuses a long one at write time.
MAX_SLUG_LENGTH = 64

EdgeKind = Literal["depends-on", "informs", "conflicts-with"]
Verdict = Literal["proposed", "set-aside"]


def _checked_slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"slug must be snake_case: {value!r}")
    if len(value) > MAX_SLUG_LENGTH:
        raise ValueError(f"slug must be at most {MAX_SLUG_LENGTH} characters: {value!r}")
    return value


class _Record(BaseModel):
    # A misspelt field in plan.json is an error, never a value quietly dropped.
    model_config = ConfigDict(extra="forbid")


class Source(_Record):
    id: str
    title: str
    url: str


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
    topics: list[Topic] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    dreams: list[Dream] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

    _slug = field_validator("slug")(_checked_slug)

    @model_validator(mode="after")
    def _one_file_per_topic(self) -> "Plan":
        slugs = [t.slug for t in self.topics]
        repeated = sorted({s for s in slugs if slugs.count(s) > 1})
        if repeated:
            raise ValueError(f"topic slugs must be unique: {', '.join(repeated)}")
        return self

    # -- persistence ---------------------------------------------------

    @classmethod
    def load(cls, tree: Path) -> "Plan":
        return cls.model_validate_json(plan_path(tree).read_text(encoding="utf-8"))

    def save(self, tree: Path) -> Path:
        path = plan_path(tree)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path


def plan_path(tree: Path) -> Path:
    return Path(tree) / SPEC_DIR / PLAN_FILENAME
