"""Copy the skeleton into a target directory, substituting @@NAME@@ tokens.

`@@NAME@@` rather than `{{NAME}}` because the skeleton ships Jinja templates,
and a substitution syntax that collides with the templating language of the
thing you are templating is a bug waiting for the first `{{ app_name }}`.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from protopilot.spec import Spec

TOKEN_RE = re.compile(r"@@([A-Z][A-Z0-9_]*)@@")

# Copied byte-for-byte. A stray .pyc in the skeleton would otherwise blow up
# the copy with a UnicodeDecodeError.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pyc"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}

SKELETON_DIR = Path(__file__).resolve().parent.parent / "skeleton"


def project_name(spec: Spec, target: Path | None = None) -> str:
    """The Docker Compose project name: unique per directory, not per slug.

    The slug alone is not unique. Generating the same idea twice -- which is
    what iterating on one looks like -- produced two trees with one compose
    project between them, and the second `up` silently adopted the first's
    containers and took its app down. The suffix is the target path, so two
    trees never collide and the same tree is stable across runs.
    """
    if target is None:
        return spec.slug
    digest = hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()[:6]
    return f"{spec.slug}_{digest}"


def substitutions(spec: Spec, target: Path | None = None) -> dict[str, str]:
    return {
        "APP_NAME": spec.name,
        "APP_SLUG": spec.slug,
        "APP_PURPOSE": spec.purpose,
        "PORT": str(spec.port),
        "PROJECT": project_name(spec, target),
    }


def render(text: str, values: dict[str, str]) -> str:
    """Substitute every @@TOKEN@@, raising on one we have no value for.

    Strict on purpose: an unknown token would otherwise ship literally into
    somebody's prototype and be discovered by them rather than by us.
    """
    unknown = {m.group(1) for m in TOKEN_RE.finditer(text)} - set(values)
    if unknown:
        raise KeyError(f"unknown placeholder(s): {', '.join(sorted(unknown))}")
    return TOKEN_RE.sub(lambda m: values[m.group(1)], text)


def render_skeleton(spec: Spec, target: Path, skeleton: Path | None = None) -> list[Path]:
    """Materialise the fixed tree. Returns the files written, relative paths."""
    skeleton = skeleton or SKELETON_DIR
    if not skeleton.is_dir():
        raise FileNotFoundError(f"skeleton not found at {skeleton}")
    values = substitutions(spec, target)
    target.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for src in sorted(skeleton.rglob("*")):
        if any(part in SKIP_DIRS for part in src.relative_to(skeleton).parts):
            continue
        rel = src.relative_to(skeleton)
        dest = target / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in BINARY_SUFFIXES:
            shutil.copyfile(src, dest)
        else:
            dest.write_text(render(src.read_text(), values))
        written.append(rel)
    return written
