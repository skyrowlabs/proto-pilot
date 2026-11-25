<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# What makes it cozy and tense at once

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

The audience is defined by a pairing that usually pulls apart, so the slice has to settle which exact feelings count as cozy (shelter, warmth, a full cache) versus tense (cold, hunger, being hunted), how they alternate or overlap in a single session, and what would tip it into either bleak or toothless.

## Findings

- The Project Horseshoe cozy-games report defines coziness as "the fantasy of safety, abundance, and softness" yet explicitly allows danger: cozy spaces work as "reprieve or refuge" and contrast (cold rain on the window) heightens warmth as long as the threat never breaks in. It names Dark Souls bonfires as the model loop of desire, adventure, rest. (sources: s1)
- The same report lists what kills coziness, and two items hit a squirrel hoarding game directly: mandatory maintenance and needy dependents requiring constant care, and extrinsic obligation generally ("Almost any form of extrinsic reward generates a pressing transactional short-term need"). It advises making most activities optional and intrinsically satisfying. (sources: s1)
- Shelter (play as a badger mother) shows where irreversible loss lands: a reviewer calls it harrowing, "truly terrifying" and emotionally taxing rather than relaxing, with no checkpoints and cubs "gone for good." That design buys strong attachment at the cost of any coziness — useful as the boundary the slice should not cross. (sources: s2)
- Winter Burrow (2025), a mouse surviving winter, is the closest comparable, and a reviewer concludes it "isn't exactly a cosy game" and is "a lot more stressful to play than it looks": warmth, hunger and stamina cut trips short, spiders and predators patrol outside, while the burrow is the warm, decoratable core. (sources: s3)
- Winter Burrow's failure mode is instructive: the same review faults walking "the same trail in and out of the burrow a hundred times" before real progress, no in-game map, and "rudimentary" combat and crafting. The in/out rhythm is the right spine, but it goes from tense to tedious when each excursion is identical. (sources: s3)
- **Assumption:** A workable contract for the slice: tension is spatial and temporal (outside the den, late in a day), coziness is the bounded den where threat is audible but muted. Tip into bleak when a setback ends the run; tip into toothless when nothing in the cache can ever be lost. Prefer setbacks that cost comfort and time — a raided cache, a cold night — over death.

## Connections

- The hoarding loop and what the player remembers conflicts with What makes it cozy and tense at once
- Being small, cold and hunted in 2D informs What makes it cozy and tense at once
- How much real squirrel behaviour to simulate conflicts with What makes it cozy and tense at once
- What the first slice contains and how it is judged depends on What makes it cozy and tense at once
- Shape of one winter, start to finish conflicts with What makes it cozy and tense at once

## Risks

- The two halves cancel rather than alternate: a warmth/hunger clock running at all times makes the den a waiting room instead of a refuge, and the game lands as mildly stressful throughout rather than cozy or tense at any point.
- Tension is delivered by the only mechanism that is cheap to build — a draining meter — which reads as nagging maintenance rather than threat, exactly the thing the cozy-games report in the findings warns kills coziness.
- The audience splits in playtest: people who came for cozy quit at the first permanent loss, people who came for tense call it toothless, and the slice produces no clear verdict because it was aimed between them.
- Irreversible loss of something the player has invested in (a season's cache, a nestmate) buys attachment at the cost of the stated audience promise, per the prey-animal comparable in the findings; a single such event can retroactively recolour the whole run as bleak.
- The in-and-out rhythm the findings identify as the right spine degrades into sameness, so tension decays into tedium by the third or fourth excursion while the cozy side is unaffected — the game feels flat without either feeling broken.
- Marketing or framing language promises cozy, the mechanics deliver survival pressure, and early reactions are dominated by the mismatch rather than by the design itself.
- Conflict with the caching, pacing and simulation topics is structural, not incidental: each of those gets more interesting as it gets harsher, so the contract will be eroded by every downstream decision unless it is written down as a constraint the other topics must obey.

## Unknowns

- Does the target audience want cozy and tense interleaved within a single session, or cozy as the frame and tense as the content — and do those two readings even produce different builds?
- Which specific feeling is doing the work of 'cozy' here: physical warmth, spatial safety, material abundance, or competence at a mastered routine?
- What is the largest setback a player will accept without the run feeling punitive — losing time, losing comfort, losing stored food, or losing the run?
- Does threat that is audible but cannot reach the den actually heighten the den's warmth, or does it just prevent the player from relaxing in it?
- Can tension be purely spatial and temporal (outside, late) with no always-on timer, and does the game still feel like survival if the den pauses all pressure?
- What does a player do inside the den that is intrinsically satisfying rather than an obligation, and is there anything to do there at all in the first slice?
- Is 'bleak' caused by the severity of losses or by their unpredictability — and which one do testers actually report?

## Decisions to make

- Write the contract as a hard constraint on all other topics, or treat it as an emergent tone to be tuned after the loop exists.
- Pause or near-pause all survival pressure inside the den, versus running a slow drain everywhere so the den is only a better place to be.
- Permit permanent loss of stored food at all, versus capping every setback at cost of time and comfort with nothing unrecoverable.
- Make cozy activities optional and intrinsically rewarding, versus making den upkeep a required step in the loop.
- Give the den a decoration or nest-building layer in the first slice, or defer all of it and test the outside loop alone.
- Target one pole and let the other be flavour, versus committing to genuine alternation and accepting that it costs pacing work.
- Resolve the cozy/tense tradeoff by difficulty setting (player chooses), versus by a single authored tuning the developer stands behind.
