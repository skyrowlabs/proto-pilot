"""Passes.

Each pass module exports:

    NAME     str
    WRITES   tuple[str, ...]   -- paths it is allowed to produce, or () for
                                  `repair`, whose set is the whole target's
    SCHEMA   dict              -- JSON Schema for its structured output
    build(spec, ctx)           -> (system_prompt, user_prompt)
    offline(spec, ctx)         -> dict matching SCHEMA

Two implementations of every pass is the design, not duplication: `build` is
checked against `offline` by the test suite, and a pass whose prompt asks for
something the baseline cannot express has no worked example.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from protopilot import targets
from protopilot.files import GeneratedFile, write_all
from protopilot.llm import LLM
from protopilot.spec import Spec


@dataclass
class PassContext:
    """What a pass can see: the project on disk, and what earlier passes said.

    Later passes read the *real generated source* rather than a description of
    it. A routes pass told "there is a Trip model" will invent a field name;
    one handed models.py will not.
    """

    project_dir: Path
    notes: dict[str, str] = field(default_factory=dict)
    # Free-text instruction for an incremental change (`proto add`).
    change: str = ""
    # The archetype the classifier chose, known before intake runs and needed
    # by it: intake picks the entities, and "a match and its moves" versus "a
    # table of games" is a decision only the shape can settle. Every other pass
    # reads it off the spec; intake has no spec yet, which is what it is for.
    archetype: str = ""
    # A formatted VerifyResult, set only when the repair pass is running.
    failure: str = ""

    def read(self, rel: str) -> str:
        path = self.project_dir / rel
        return path.read_text() if path.exists() else ""

    def sources(self, *rels: str) -> str:
        """Format existing files for a prompt, skipping ones not yet written."""
        chunks = []
        for rel in rels:
            body = self.read(rel)
            if not body.strip():
                continue
            lang = "html" if rel.endswith(".html") else "python"
            chunks.append(f"### `{rel}`\n\n```{lang}\n{body}\n```")
        return "\n\n".join(chunks)

    def template_files(self) -> list[str]:
        root = self.project_dir / "app" / "templates"
        if not root.is_dir():
            return []
        return sorted(f"app/templates/{p.name}" for p in root.glob("*.html") if p.name != "base.html")


@dataclass
class PassResult:
    name: str
    files: list[Path]
    notes: str


def run_pass(module: ModuleType, spec: Spec, ctx: PassContext, llm: LLM) -> PassResult:
    """Produce a pass's files and write them, or raise."""
    if llm.offline:
        data = module.offline(spec, ctx)
    else:
        system, user = module.build(spec, ctx)
        data = llm.structured(system=system, user=user, schema=module.SCHEMA, label=module.NAME)
    files = [GeneratedFile(path=f["path"], content=f["content"]) for f in data["files"]]
    # The write guard's allowlist is the running target's, not this module's:
    # a terminal tree has no `app/templates/*.html` and a web tree has no
    # `app/screens.py`. Resolved from the spec at the moment of writing, so the
    # guard cannot be a step behind the tree it is guarding.
    target = targets.for_spec(spec)
    written = write_all(ctx.project_dir, files, module.NAME, target.WRITABLE, target.PROTECTED)
    notes = data.get("notes", "")
    ctx.notes[module.NAME] = notes
    return PassResult(name=module.NAME, files=written, notes=notes)
