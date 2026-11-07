"""One good model run for the plan's passes, for a test to spoil a response of."""

from __future__ import annotations

import copy

IDEA = "start a community tool library"
SLUGS = ["members", "lending", "space", "tools", "money", "safety"]
PLAN_PASS_NAMES = ["scope", "outline", "connect", "consider", "start"]
DREAM_PASS_NAMES = ["collect", "evaluate", "propose"]
PASS_NAMES = [*PLAN_PASS_NAMES, *DREAM_PASS_NAMES]


def outline_of(slugs: list[str]) -> dict:
    return {"topics": [{"slug": s, "title": s.title(), "why": f"{s} matters"} for s in slugs]}


def consider_of(slugs: list[str]) -> dict:
    return {"topics": [{"slug": s, "risks": ["r"], "unknowns": ["u?"], "decisions": ["d"]} for s in slugs]}


def edge(source: str, target: str, kind: str = "depends-on") -> dict:
    return {"from_topic": source, "to_topic": target, "kind": kind}


def step(topic: str) -> dict:
    return {"topic": topic, "action": f"Work on {topic}.", "why": "It comes now."}


def dream_row(lens: str = "who-else", anchor: str = "members", word: str = "seeds") -> dict:
    return {
        "title": f"{word.title()} too",
        "what_if": f"the library lent {word} as well as saws",
        "lens": lens,
        "anchor": anchor,
        "takes": "A shelf.",
    }


def judged_row(dream_id: str, verdict: str = "proposed", duplicate_of: str = "") -> dict:
    scores = {"pull": "high", "reach": "low", "cost": "medium", "fit": "high"}
    return {
        "id": dream_id,
        **scores,
        "verdict": verdict,
        "reason": f"{dream_id} decided.",
        "duplicate_of": duplicate_of,
    }


def proposal_row(dream_id: str) -> dict:
    return {"id": dream_id, "if_adopted": f"{dream_id} changes the first step."}


GOOD = {
    "scope": {"goal": "Decide.", "audience": "Neighbours", "horizon": "A year", "constraints": [], "questions": []},
    "outline": outline_of(SLUGS),
    "connect": {"edges": [edge("lending", "members"), edge("money", "space", "informs")]},
    "consider": consider_of(SLUGS),
    "start": {"steps": [step("members")]},
    "collect": {"dreams": [dream_row(), dream_row("the-opposite", word="bread")]},
    "evaluate": {"dreams": [judged_row("d1"), judged_row("d2", "set-aside")]},
    "propose": {"proposals": [proposal_row("d1")]},
}


def repair_of(edges: list[dict], topics: list[str]) -> dict:
    """A repair response: the complete edges, and a step for each of `topics`."""
    return {"edges": edges, "steps": [step(topic) for topic in topics]}


def script(**overrides: object) -> list:
    """The responses of a good run, in pass order, with any replaced by name.

    The dreams anchor to the outline's first topic, whichever outline this run has.
    """
    responses = {**GOOD, **overrides}
    outlined = responses["outline"]
    if "collect" not in overrides and isinstance(outlined, dict) and outlined.get("topics"):
        first = outlined["topics"][0]["slug"]
        responses["collect"] = {"dreams": [{**row, "anchor": first} for row in GOOD["collect"]["dreams"]]}
    return [copy.deepcopy(responses[name]) for name in PASS_NAMES]
