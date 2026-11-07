"""One good model run for the plan's passes, for a test to spoil a response of."""

from __future__ import annotations

import copy

IDEA = "start a community tool library"
SLUGS = ["members", "lending", "space", "tools", "money", "safety"]
PASS_NAMES = ["scope", "outline", "connect", "consider", "start"]


def outline_of(slugs: list[str]) -> dict:
    return {"topics": [{"slug": s, "title": s.title(), "why": f"{s} matters"} for s in slugs]}


def consider_of(slugs: list[str]) -> dict:
    return {"topics": [{"slug": s, "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]} for s in slugs]}


def edge(source: str, target: str, kind: str = "depends-on") -> dict:
    return {"from_topic": source, "to_topic": target, "kind": kind}


def step(topic: str) -> dict:
    return {"topic": topic, "action": f"Work on {topic}.", "why": "It comes now."}


GOOD = {
    "scope": {"goal": "Decide.", "audience": "Neighbours", "horizon": "A year", "constraints": [], "questions": []},
    "outline": outline_of(SLUGS),
    "connect": {"edges": [edge("lending", "members"), edge("money", "space", "informs")]},
    "consider": consider_of(SLUGS),
    "start": {"steps": [step("members")]},
}


def script(**overrides: object) -> list:
    """The five responses of a good run, in pass order, with any replaced by name."""
    return [copy.deepcopy({**GOOD, **overrides}[name]) for name in PASS_NAMES]
