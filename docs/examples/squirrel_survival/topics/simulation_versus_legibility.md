<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# How much real squirrel behaviour to simulate

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

Animal authenticity is likely part of the appeal, but every hidden system (weather, food spoilage, predator routines, body condition) needs a readable surface the player can plan against, so it must be established where fidelity earns its keep and where an invisible simulation would just feel like unfair randomness.

## Findings

- Grey squirrels don't hibernate and can't store enough energy to go long without food: in very cold weather they sit in a thicker, often shared winter drey and come out intermittently to dig up caches. That supports a loop of short, cold-gated foraging trips out from a warm nest hub rather than any sleep-through-winter mechanic. (sources: s14)
- The same factsheet asserts autumn caches are spread out and relocated "by smell, rather than memory," with many never recovered. Popular natural history and the research literature disagree on this, so the cache-finding rule is a free design choice — you can safely build the loop on the player's own memory without feeling inauthentic. (sources: s14)
- **Assumption:** Field work on PIT-tagged acorns (Steele et al.) reportedly found caches disturbed within \~0.5–5 days when other squirrels were present but intact 16–27 days once neighbours were removed; Jacobs-lab work shows spatial memory and caches chunked by nut type. Pilferage is authentic, but only reads as fair if a visible rival does it.
- A design essay on realism argues that modelling spoilage from temperature, humidity and container turns survival into "obsessive-compulsive inventory management," and recommends collapsing systems into a few readable states, exposing the rules, and capping variance so one bad roll can't erase hours. Treat weather and body condition as readable pressures, not detailed models. (sources: s15)
- A review of Shelter 2, the closest comparable (play an animal, feed dependents), says its hunger meter, highlighted prey and collectibles felt grafted-on and "never grow past their primitive first impression," in a world that is huge but empty, while the real feeling came from the cubs. Simulated systems must carry the stakes, not sit beside them. (sources: s16)
- A study of a deliberately inscrutable game (Kirman, Linehan & Feltwell 2022) found players begin with systematic reasoning and, when they can't link action to effect, split between frustration and accepting the game as role-play. Only the second group tolerates opacity, and a cozy-but-tense survival audience is mostly the first. (sources: s17)

## Connections

- How much real squirrel behaviour to simulate conflicts with What makes it cozy and tense at once
- How much real squirrel behaviour to simulate depends on Being small, cold and hunted in 2D
- How much real squirrel behaviour to simulate informs The hoarding loop and what the player remembers
- How much real squirrel behaviour to simulate informs What the first slice contains and how it is judged
- How much real squirrel behaviour to simulate informs Shape of one winter, start to finish

## Risks

- Hidden systems read as randomness: weather, spoilage, body condition and predator routines each need a visible surface, and any one of them left opaque makes planning feel pointless and losses feel arbitrary.
- Detailed spoilage or condition modelling turns the game into obsessive inventory management, the failure the design source in the findings names, which also directly violates the cozy contract.
- Authenticity is pursued where no player can perceive it, consuming time that buys nothing — fidelity in systems whose outputs never reach the screen.
- Variance is uncapped and one bad roll erases an hour; this is the single most run-destroying form of unfairness in a survival game and the hardest to notice in short self-testing.
- Simulated systems sit beside the stakes rather than carrying them, the criticism of the closest animal comparable in the findings: the meters feel grafted on while the emotional weight lives somewhere the simulation does not touch.
- The audience is mostly systematic reasoners who need action linked to effect; opacity that a role-play-minded player would tolerate will instead read as broken to this audience.
- Real behaviour and good play diverge — authentic squirrel strategy may be boring to execute — and resolving that by splitting the difference produces something neither authentic nor fun.
- Sources on real behaviour disagree (the findings note conflicting claims about scent versus memory), so 'authentic' may be unfalsifiable as a design criterion while still being used to justify decisions.

## Unknowns

- Which systems does the player need to predict in order to plan, and which only need to be felt?
- Can each simulated system be collapsed into a few named, readable states, and does doing so lose anything players would notice?
- Are the rules exposed to the player directly (stated in-game), inferable from consistent feedback, or left to be learned by loss?
- What variance cap keeps a run from being destroyed by one event, and is the cap stated or hidden?
- Does authenticity matter to the target audience as accuracy, or only as the feeling of being a small animal?
- Where the natural history is contested, which reading does the game adopt — and is that chosen for fidelity or for playability?
- Does pilferage require a visible rival on screen to read as fair, and does the slice have the budget for one?
- Is weather a schedule the player can learn, a forecastable signal, or a surprise?
- What is the minimum feedback that makes hunger and cold readable before they become fatal — and how early must the warning come?

## Decisions to make

- Collapse each system to a handful of named states, versus modelling continuous values underneath with a simplified display.
- State the rules openly in-game, versus letting players infer them from consistent cues.
- Include food spoilage at all, versus making stored food permanent until taken.
- Make weather a learnable schedule, a forecast the player can read, or an unforecastable event.
- Attribute every loss to a visible agent or cause, versus permitting unattributed losses.
- Set a hard variance cap on how much a single event may cost, and whether to tell the player it exists.
- Resolve contested natural history in favour of playability and say so, versus in favour of fidelity and design around it.
- Spend simulation depth on the cache and weather systems, versus on the threats, versus on body condition — choosing one.
