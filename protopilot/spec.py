"""The spec is the contract between the human, the model, and every pass.

Everything downstream reads this and nothing else about the user's intent.
It is deliberately small: a spec you cannot review in thirty seconds is a
spec nobody reviews, and an unreviewed spec is just the model's first guess
wearing a schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SPEC_FILENAME = "spec.json"
SPEC_DIR = ".protopilot"

# Kept small on purpose. Every type here has an unambiguous mapping to a
# SQLAlchemy column, a form input, and a seed-value generator. A type we
# cannot render in all three places is a type that produces a broken app.
FieldType = Literal["str", "text", "int", "float", "bool", "date", "datetime"]

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class Field_(BaseModel):
    """One column on one entity."""

    model_config = {"populate_by_name": True}

    name: str = Field(description="snake_case attribute name")
    type: FieldType = "str"
    required: bool = True
    label: str = ""

    @field_validator("name")
    @classmethod
    def _snake(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"field name must be snake_case: {v!r}")
        if v in {"id", "metadata"}:
            raise ValueError(f"field name {v!r} is reserved")
        return v

    def human_label(self) -> str:
        return self.label or self.name.replace("_", " ").capitalize()


class Entity(BaseModel):
    """One table, one model class, one set of CRUD routes."""

    name: str = Field(description="PascalCase singular, e.g. Trip")
    plural: str = Field(default="", description="snake_case plural, e.g. trips")
    fields: list[Field_] = Field(default_factory=list)
    belongs_to: str | None = Field(default=None, description="PascalCase name of the parent entity, or null")

    @field_validator("name")
    @classmethod
    def _pascal(cls, v: str) -> str:
        if not PASCAL_RE.match(v):
            raise ValueError(f"entity name must be PascalCase: {v!r}")
        return v

    def model_post_init(self, __context: object) -> None:
        if not self.plural:
            object.__setattr__(self, "plural", _pluralise(_snake(self.name)))

    @property
    def table(self) -> str:
        return self.plural

    @property
    def var(self) -> str:
        return _snake(self.name)


class Screen(BaseModel):
    """One page. `kind` decides the template shape, not the model's mood."""

    name: str
    path: str = Field(description="URL path, e.g. /trips or /trips/{id}")
    entity: str | None = None
    kind: Literal["list", "detail", "form", "custom"] = "list"

    @field_validator("path")
    @classmethod
    def _leading_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"screen path must start with '/': {v!r}")
        return v


class Theme(BaseModel):
    """How it should look and feel. Orthogonal to what it *is*.

    A themed chess app is archetype `turn-based-game` and theme `cats`, and
    keeping those on separate axes is what stops the work being the product of
    the two: a theme costs one prompt fragment and no offline baseline at all.

    Every field is free text, and deliberately not an enum. Whatever closed set
    we picked, the first person to want something outside it would be refused --
    and a theme the UI pass interprets loosely is a better outcome than a theme
    the schema rejects.
    """

    palette: str = Field(default="", description="e.g. 'warm earth tones', 'high-contrast neon'")
    motif: str = Field(default="", description="the recurring visual idea, e.g. 'paw prints'")
    tone: str = Field(default="", description="e.g. 'playful', 'clinical', 'hand-drawn'")
    subject: str = Field(default="", description="what the drawn artwork depicts, e.g. 'cats and dogs'")

    def is_empty(self) -> bool:
        return not any((self.palette, self.motif, self.tone, self.subject))

    def describe(self) -> str:
        parts = [p for p in (self.subject, self.palette, self.motif, self.tone) if p]
        return ", ".join(parts)


class Spec(BaseModel):
    """The whole app, as far as proto-pilot is concerned."""

    name: str = Field(description="Human-readable app name")
    slug: str = Field(description="snake_case identifier; also the DB name")
    purpose: str = Field(description="One sentence: what this app is for")
    entities: list[Entity] = Field(default_factory=list)
    screens: list[Screen] = Field(default_factory=list)
    auth: Literal["none", "password"] = "none"
    jobs: list[str] = Field(default_factory=list)
    external_apis: list[str] = Field(default_factory=list)
    port: int = 8080
    protopilot_version: str = "0.1.0"
    # What SHAPE of thing this is. Selects the question set, the screen rule,
    # the prompt fragments the code passes are given, and the offline baseline.
    # Defaulted rather than required, so every spec written before archetypes
    # existed still loads and still generates the app it always did.
    archetype: str = "crud"
    # How it should LOOK. Read by the UI pass and by nothing else -- a theme
    # that can reach routes or models is an archetype wearing the wrong name.
    theme: Theme | None = None
    # Answers to the archetype's FIXED questions, keyed by their stable id.
    # Model-invented questions have model-invented ids and no contract, so they
    # keep going to `direction`; this field is the half that has a schema.
    answers: dict[str, str] = Field(default_factory=dict)
    # The archetype's own typed slice, validated by its `EXTRA` model rather
    # than by this one. `Spec` stays a single loadable type -- a subclass per
    # archetype would break `Spec.load`, which does not know the archetype
    # until after it has parsed the file.
    extra: dict = Field(default_factory=dict)
    # Free-text direction the user gave, carried through to every pass so
    # "make it feel like a kanban board" survives past intake.
    direction: str = ""
    # What the fixed stack cannot do for this idea, in plain sentences.
    # Empty when the idea fits as asked. Shown at the review checkpoint,
    # because quietly building something smaller than what was asked for is
    # the failure mode that looks exactly like success.
    limits: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"slug must be snake_case: {v!r}")
        return v

    # -- persistence ---------------------------------------------------

    @classmethod
    def load(cls, project_dir: Path) -> "Spec":
        path = Path(project_dir) / SPEC_DIR / SPEC_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"no spec at {path} -- is {project_dir} a proto-pilot project?")
        return cls.model_validate_json(path.read_text())

    def save(self, project_dir: Path) -> Path:
        path = Path(project_dir) / SPEC_DIR / SPEC_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2) + "\n")
        return path

    # -- helpers -------------------------------------------------------

    def entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)

    def summary(self) -> str:
        """What gets printed for the human review checkpoint."""
        lines = [f"{self.name} ({self.slug})  ->  port {self.port}", f"  {self.purpose}"]
        lines.append(f"  archetype: {self.archetype}")
        if self.theme and not self.theme.is_empty():
            lines.append(f"  theme: {self.theme.describe()}")
        if self.direction:
            lines.append(f"  direction: {self.direction}")
        for key, value in self.answers.items():
            lines.append(f"    {key}: {value}")
        lines.append("  entities:")
        for e in self.entities:
            parent = f" (belongs to {e.belongs_to})" if e.belongs_to else ""
            lines.append(f"    {e.name}{parent}")
            for f in e.fields:
                req = "" if f.required else "?"
                lines.append(f"      {f.name}{req}: {f.type}")
        lines.append("  screens:")
        for s in self.screens:
            lines.append(f"    {s.path:<24} {s.kind:<8} {s.name}")
        lines.append(f"  auth: {self.auth}")
        if self.jobs:
            lines.append(f"  jobs: {', '.join(self.jobs)}")
        if self.external_apis:
            lines.append(f"  external apis: {', '.join(self.external_apis)}")
        if self.limits:
            # Last, and named plainly, because this is the part a reviewer
            # most needs to disagree with before any tokens are spent.
            lines.append("  not in this version:")
            for limit in self.limits:
                lines.append(f"    - {limit}")
        return "\n".join(lines)


def checkable_paths(spec: "Spec") -> list[str]:
    """Screen paths a browser can actually fetch.

    Detail screens carry `{row_id}`, and the seed pass guarantees rows exist,
    so `1` is a safe substitution. Anything with a placeholder we cannot fill
    is dropped rather than guessed at -- a 404 from a made-up URL would be
    reported as a broken screen, which is worse than not checking it.
    """
    paths = []
    for screen in spec.screens:
        path = screen.path
        if "{row_id}" in path:
            path = path.replace("{row_id}", "1")
        if "{" in path:
            continue
        paths.append(path)
    return paths


def _snake(pascal: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", pascal).lower()


def _pluralise(word: str) -> str:
    """Deliberately naive. A wrong plural is a cosmetic bug in a prototype;
    an irregular-noun table is a maintenance burden forever."""
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and not word.endswith(("ay", "ey", "iy", "oy", "uy")):
        return word[:-1] + "ies"
    return word + "s"


#: Spec fields the intake model does not decide, and is therefore not shown.
#:
#: `_strictify` marks every property in the schema as required, so a field left
#: in here is a field the model MUST invent a value for. `archetype` and `theme`
#: are classified by the clarify pass, and `answers` is assembled by the tool
#: from what the human actually chose -- asking intake to guess any of the three
#: would produce a confident second opinion that silently overwrites the first.
MODEL_OWNED_EXCLUSIONS = ("archetype", "theme", "answers", "extra")


def intake_schema() -> dict:
    """JSON Schema handed to the model for the intake pass.

    Generated from the pydantic model rather than hand-written, so a field
    added above cannot silently fail to reach the model -- minus the fields
    listed in `MODEL_OWNED_EXCLUSIONS`, which have an owner that is not intake.
    """
    schema = Spec.model_json_schema()
    schema = _inline_defs(schema)
    for name in MODEL_OWNED_EXCLUSIONS:
        schema.get("properties", {}).pop(name, None)
    _strictify(schema)
    return schema


def _inline_defs(schema: dict) -> dict:
    """Resolve $ref/$defs into a single self-contained schema.

    The API's json_schema format wants one object; pydantic emits refs.
    """
    defs = schema.pop("$defs", {})

    def walk(node: object) -> object:
        if isinstance(node, dict):
            if "$ref" in node:
                key = node["$ref"].rsplit("/", 1)[-1]
                target = walk(json.loads(json.dumps(defs[key])))
                extra = {k: v for k, v in node.items() if k != "$ref"}
                assert isinstance(target, dict)
                target.update(extra)
                return target
            # anyOf [X, null] -> keep as-is; the API handles union types.
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    result = walk(schema)
    assert isinstance(result, dict)
    return result


def _strictify(node: object) -> None:
    """Every object gets additionalProperties:false and a full `required`.

    Structured output needs this to be strict; and a model that can invent
    a key is a model that will, once, in the pass you did not test.
    """
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = sorted(node["properties"].keys())
        for value in node.values():
            _strictify(value)
    elif isinstance(node, list):
        for value in node:
            _strictify(value)
