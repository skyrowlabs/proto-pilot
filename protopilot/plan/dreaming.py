"""The pool's rules: what a round may add, and what a person may do to a dream.

A round adds and never rewrites, so a dream's id, words and verdict survive every
later round. A dream that would turn a plan red is removed here, with a sentence
saying so: dreams are extras, and repair is for the plan. Only `promoted` turns a
dream into a topic, and only `pipeline.promote` calls it, for `proto dream promote`.
"""

from __future__ import annotations

from protopilot.plan import baseline, render, verify
from protopilot.plan.lenses import Lens
from protopilot.plan.model import DREAM_FIELD_WORDS, DREAM_WORD_CAP, MAX_SLUG_LENGTH, Dream, Plan, Topic, dream_words
from protopilot.plan.passes import PlanPassError, writable

#: Decision 3's small count: one dream through each lens, as a plan is made.
PLAN_PER_LENS = 1
#: `proto dream` is asked for, so it goes wider.
ROUND_PER_LENS = 2
#: What a promoted dream's old reason was for: it argued something else, and must not read as why.
EARLIER = {"proposed": "Proposed before", "set-aside": "Set aside before", "dropped": "Dropped before"}


def _repeats(dream: Dream, other: Dream) -> bool:
    """The same words, which needs no judgement. Nearly the same is `evaluate`'s to say."""
    return any(verify.plain(getattr(dream, f)) == verify.plain(getattr(other, f)) for f in ("title", "what_if"))


def _unfit(dream: Dream, plan: Plan, held: list[Dream], lenses: tuple[Lens, ...]) -> str:
    """Why `dream` may not enter the pool, or an empty string."""
    if verify.dream_length(dream) > DREAM_WORD_CAP:
        return f"it runs to {verify.dream_length(dream)} words, past the cap of {DREAM_WORD_CAP}"
    for field, most in DREAM_FIELD_WORDS.items():
        said = getattr(dream, field)
        try:
            writable(said)
        except UnicodeEncodeError:
            return f"its {field} cannot be written as text"
        if not said:
            return f"its {field} is empty"
        if dream_words(said) > most:
            return f"its {field} runs to {dream_words(said)} words, past its {most}"
    if dream.lens not in {lens.slug for lens in lenses}:
        return f"its lens {dream.lens!r} was not asked for"
    if dream.anchor not in {topic.slug for topic in plan.topics}:
        return f"its anchor {dream.anchor!r} is not a topic"
    twin = next((other for other in held if _repeats(dream, other)), None)
    return f"it repeats {twin.id}" if twin else ""


def admit(plan: Plan, before: Plan, lenses: tuple[Lens, ...]) -> tuple[Plan, list[str]]:
    """`plan` with only the new dreams it may hold, and a sentence for each it may not."""
    known = {dream.id for dream in before.dreams}
    held, notes = list(before.dreams), []
    for dream in plan.dreams:
        if dream.id in known:
            continue
        reason = _unfit(dream, plan, held, lenses)
        if reason:
            notes.append(f"left out {dream.id}: {reason}")
        else:
            held.append(dream)
    return plan.revised(dreams=held), notes


def settle(plan: Plan, before: Plan) -> tuple[Plan, list[str]]:
    """`plan` with no new dream that would fail a check, so a round cannot turn a good plan red."""
    known = {dream.id for dream in before.dreams}
    try:
        found, _ = verify.leaks(plan, render.render(plan))
    except ValueError as exc:
        raise PlanPassError(f"this round's dreams cannot be drawn: {exc}") from exc
    copies = {leak.dream: f"its {leak.field} repeats {leak.page}" for leak in reversed(found)}
    reasons = {d.id: "evaluate gave it no verdict" for d in plan.dreams if d.verdict is None} | copies
    gone = {name: reason for name, reason in reasons.items() if name not in known}
    notes = [f"left out {name}: {reason}" for name, reason in sorted(gone.items())]
    return plan.revised(dreams=[dream for dream in plan.dreams if dream.id not in gone]), notes


def find(plan: Plan, dream_id: str) -> Dream:
    """The dream with this id; the refusal lists the ones there are."""
    for dream in plan.dreams:
        if dream.id == dream_id:
            return dream
    held = ", ".join(dream.id for dream in plan.dreams) or "none"
    raise ValueError(f"this plan has no dream {dream_id!r}; it holds: {held}")


def _replaced(plan: Plan, dream: Dream, **changes: object) -> list[Dream]:
    return [item.model_copy(update=changes) if item.id == dream.id else item for item in plan.dreams]


def _free_slug(plan: Plan, title: str) -> str:
    """A topic slug from `title` that no topic holds, numbered if it must be."""
    taken = {topic.slug for topic in plan.topics}
    base = baseline.slug_for(title)
    number = 2
    slug = base
    while slug in taken:
        suffix = f"_{number}"
        slug = f"{base[: MAX_SLUG_LENGTH - len(suffix)]}{suffix}"
        number += 1
    return slug


def promoted(plan: Plan, dream: Dream) -> Plan:
    """The dream as the plan's last topic, with nothing known about it yet. A person's act alone."""
    if dream.verdict == "promoted":
        raise ValueError(f"dream {dream.id} is already the topic {dream.promoted_to}")
    topic = Topic(slug=_free_slug(plan, dream.title), title=dream.title, why=f"What if {dream.what_if}")
    earlier = f"{EARLIER.get(dream.verdict or '', 'Before')}: {dream.reason}" if dream.reason else ""
    return plan.revised(
        topics=[*plan.topics, topic],
        dreams=_replaced(plan, dream, verdict="promoted", promoted_to=topic.slug, reason=earlier),
    )


def dropped(plan: Plan, dream: Dream, why: str) -> Plan:
    """The dream ruled out with a person's reason. It stays, so no round offers it again."""
    if dream.verdict == "promoted":
        raise ValueError(f"dream {dream.id} is the topic {dream.promoted_to} now, and a topic is not dropped here")
    if dream.verdict == "dropped":
        raise ValueError(f"dream {dream.id} is already dropped: {dream.reason}")
    reason = baseline.clean(why)
    if not reason:
        raise ValueError("--why needs a reason, because what was ruled out is the expensive half")
    return plan.revised(dreams=_replaced(plan, dream, verdict="dropped", reason=reason))
