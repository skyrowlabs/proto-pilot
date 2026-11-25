<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# The hoarding loop and what the player remembers

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

A squirrel's signature behaviour is burying food and finding it again, so the central design question is whether retrieval is tracked by the game, by the player's own memory, or by landmarks — each choice changes the core verb from bookkeeping to navigation to recall, and decides whether loss of a cache feels like drama or like paperwork.

## Findings

- A designer talk on cognitive maps argues HUDs and minimaps actively weaken route memory, and offers four concrete levers for a memorable space: cluster similar objects into districts, make edges (cliffs, walls) bold and deliberate, place revisitable convergence nodes, and connect with paths. Its test: play the level with the HUD off and see if players can still navigate. (sources: s4)
- The nearest shipped competitor, Winter Burrow (cozy mouse survival, Nov 2025), draws its main criticism exactly where this topic is risky: a reviewer calls the survival side a chore, cites walking "the same trail in and out of the burrow a hundred times," and says the absence of an in-game map makes gathering more frustrating rather than more tense. (sources: s3)
- Same review: being "constantly short on something" and converting raw items into intermediates (yarn, planks) before use is reported as tedium, not pressure. For a hoarding loop this suggests caches should be few, chunky and legible rather than many small deposits requiring tallying. (sources: s3)
- Real fox squirrels use "spatial chunking": in a study of 45 squirrels given 16 nuts of four types, those collecting from a central spot buried each type in its own general area — a mnemonic strategy. This is a ready-made, player-facing recall structure: cache by kind in a zone, so remembering means remembering four places, not forty. (sources: s5)
- **Assumption:** Recommended split: the game tracks that a cache exists and what is in it (no mental arithmetic), while position is the player's job via landmarks plus a small hard cap of diegetic marks — survival games that allow unlimited pins, and ones that cap them (Rust allows five), bracket the design space. The cap is what converts memory into a decision.
- **Assumption:** For a three-month slice, author cache loss rather than simulate it: a handful of scripted thefts or snow-buried landmarks with visible tells (tracks, a watching crow) reads as drama, whereas realistic pilferage rates applied to every cache reads as the game cheating. Build one forest clearing with three chunked cache zones and test retrieval with no map before building more.

## Connections

- The hoarding loop and what the player remembers conflicts with What makes it cozy and tense at once
- The hoarding loop and what the player remembers depends on Being small, cold and hunted in 2D
- How much real squirrel behaviour to simulate informs The hoarding loop and what the player remembers
- What the first slice contains and how it is judged depends on The hoarding loop and what the player remembers
- Shape of one winter, start to finish depends on The hoarding loop and what the player remembers

## Risks

- Retrieval becomes bookkeeping: if the game tracks caches in a list, the signature verb collapses into inventory management and the squirrel fantasy evaporates even though the system works.
- Retrieval becomes punishment: if position is entirely the player's memory with no marks and no map, a forgotten cache is unrecoverable through no learnable fault, and the findings' comparable shows unmapped gathering reading as frustration rather than tension.
- Many small deposits force tallying, which the findings flag as tedium; the hoarding fantasy pushes toward quantity while legibility pushes toward a handful of chunky caches, and quantity will win by default because it is easier to generate.
- Simulated pilferage applied broadly reads as the game cheating — loss without a visible agent is indistinguishable from a bug or a bad roll.
- Memory load is a hard accessibility and session-length problem: a player who returns after a week has lost their mental map and the run becomes unplayable even though the save is intact.
- The forest is built before it is navigable: without deliberate landmarks, districts and edges, remembering locations is impossible regardless of which retrieval rule is chosen, so art and level work done early may need to be redone.
- This topic directly conflicts with the cozy contract — cache loss is the main source of drama available and also the main thing that can make the run feel bleak.

## Unknowns

- Is the core verb meant to be navigation, recall, or planning — and which of the three does the target audience actually enjoy for an hour?
- Does the game track that a cache exists and its contents while leaving only position to the player, and is that split legible to a player or does it feel arbitrary?
- What is the right number of cache sites for one forest: few and chunky, or many and approximate?
- Does caching by kind into zones (one area per food type) actually reduce what a player must remember, or does it just add a sorting chore at burial time?
- How many diegetic marks (scratches, pins, bent twigs) can a player place before memory stops mattering — and is the cap felt as a decision or as a restriction?
- Can a cache be lost in a way that a player will read as drama rather than unfairness, and what visible tell is required for that — a rival seen, tracks, a sound at the time of theft?
- How does the player re-orient after a snowfall changes the landscape's appearance, and is that a deliberate mechanic or an accident of the art?
- Should the first slice be testable with the HUD and all markers off, and what does failure of that test tell us?

## Decisions to make

- Track caches in the game's UI, leave them entirely to player memory, or split tracking (contents yes, position no).
- Allow unlimited diegetic marks, cap them at a small number, or allow none.
- Author cache loss as a few scripted events with visible tells, versus simulating pilferage rates across all caches.
- Build one clearing with a few chunked cache zones and test retrieval before building more forest, versus building the full forest first.
- Make the chunk-by-type structure a rule the game enforces, a bonus it rewards, or a habit the player may invent.
- Offer a map, a markers-only compromise, or nothing — and whether a map is an accessibility option rather than a design choice.
- Decide whether forgetting a cache ends in permanent loss or in a costlier recovery (digging, searching, a hint).
