<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# Shape of one winter, start to finish

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

The constraint is a single season played to completion, so the plan must establish whether there is an autumn preparation phase before scarcity, how long a full run takes in real minutes, how difficulty escalates as food thins, what the ending state is, and whether a failed run restarts the whole winter or something shorter.

## Findings

- Don't Starve treats winter as a bounded block of 15-16 in-game days preceded by autumn, and escalates inside it rather than just raising numbers: nights get longer, berry bushes/grass/saplings regrow very slowly, farms stop, and scripted threats (Deerclops, a walrus hunting party) arrive. The prep phase is explicitly about stockpiles and warmth gear bought before the clock starts. (sources: s6)
- A survival-design piece argues the common failure is a decreasing curve (early scarcity, then a comfortable late game) and recommends alternating pressure with recovery phases plus spikes, while noting that always-hard play just makes players tired of dying. It also recommends a stated end goal, giving "a winter calamity" as an example. (sources: s7)
- The Flame in the Flood ships one content arc with two failure contracts: Traveler keeps your equipment on death and lets you reload a checkpoint, Survivalist makes death permanent and drains survival faster. A single-winter run can be authored once and sold as both a gentle and a permadeath experience via a difficulty toggle. (sources: s8)
- The closest comparable, Shelter 2 (play an animal, feed young, seasons pass), ran about two hours and was faulted because after the strong opening "all semblance of structure disappears", and because unclear hunger feedback made it easy to end up with dead cubs. Short length was criticised less than the missing mid-game structure and unreadable needs. (sources: s9)
- A 27-year red squirrel dataset found juveniles that claimed a territory earlier were much more likely to survive their first winter, partly because a territory holds a cone cache, and timing mattered more when winters were colder or predators more abundant. This supports an autumn phase whose outcome visibly sets your winter odds. (sources: s10)
- **Assumption:** Concrete shape I would commit to: roughly 60-90 real minutes total, about 12-16 short days at 3-5 minutes each, with the first quarter as autumn caching and the last third as the hard scarcity peak; ending at the thaw with a readable account of what you survived. Build the mid/late winter peak first, since that is where the game either works or does not.

## Connections

- How much real squirrel behaviour to simulate informs Shape of one winter, start to finish
- What the first slice contains and how it is judged depends on Shape of one winter, start to finish
- Shape of one winter, start to finish conflicts with What makes it cozy and tense at once
- Shape of one winter, start to finish depends on The hoarding loop and what the player remembers

## Risks

- Difficulty runs downhill: by the time the player is competent, the stockpile is large and the last third — meant to be the scarcity peak — is the easiest part, which is the failure mode the survival-design source in the findings describes.
- An autumn prep phase decides the run before the interesting part begins; a bad autumn means a doomed winter the player must still sit through, and a good autumn means no winter pressure at all.
- The mid-game has no structure: the opening teaches and the end resolves, but the middle is repeated excursions, which is the specific criticism levelled at the closest animal-survival comparable in the findings.
- Restart cost is mismatched to run length: full-winter restarts after a late failure discard an hour of play, while cheap restarts remove all weight from failure.
- Session length collides with the audience — a run that only resolves in one unbroken sitting excludes the evenings-and-weekends player, while mid-run saves may undercut the tension of a single continuous winter.
- The arc is built to be survivable at all costs and the ending becomes a formality, so there is no readable account of what the player actually endured.
- Pacing is tuned against the developer's own expertise; the only person who has played the loop hundreds of times is the one setting the curve.

## Unknowns

- How long is a full run in real minutes, and is that length set by what the audience will sit through or by how long the loop stays interesting?
- How many in-game days, at what real-time length each, and does the day length change as winter deepens?
- Is there an autumn phase at all, and if so does its outcome visibly set the player's odds or merely stock the first few days?
- What escalates besides scarcity — night length, weather severity, predator presence, travel cost — and which of those can be built in the time available?
- Where does recovery sit in the curve: is there a thaw or a mild spell that lets the player breathe before the peak?
- What is the ending state: survival to the thaw, a stated goal met, or a graded outcome — and what does the game tell the player they achieved?
- Does failure restart the whole winter, the current day, or the last stretch, and does the player choose?
- Is the hard scarcity peak the first thing to build, and can it be tested at all without the autumn phase that feeds it?
- Does a single authored arc support both a gentle and a permadeath contract via one toggle, or do the two need different tuning?

## Decisions to make

- Build the mid-to-late scarcity peak first, versus building the run in chronological order from autumn.
- Include an autumn preparation phase in the first slice, or start the slice at the onset of scarcity with a granted starting cache.
- Escalate by scripted events on a schedule, by rising resource scarcity, or by both.
- Offer one tuning, or ship a gentle/keep-your-progress mode alongside a permadeath mode from the first slice.
- Set the restart unit: whole winter, a chapter, or a day.
- Allow saving mid-run, versus requiring one sitting, versus saving only at the den.
- Decide the end condition and whether it is binary survival or a graded account of the winter.
- Fix the real-minute target up front and tune content to it, versus letting length fall out of however much content gets built.
