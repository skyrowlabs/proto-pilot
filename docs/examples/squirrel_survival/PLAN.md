<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# A survival game where you play a squirrel getting through its first winter

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source.

## The idea

a survival game where you play a squirrel getting through its first winter

**Goal:** decide whether a small playable slice is worth building, and what to build first

**Audience:** players who like short survival games that are cozy but tense

**Horizon:** about three months of evenings and weekends, one developer

## Constraints

- 2D and single-player
- one forest and one winter, start to finish
- Multiplayer is out of scope
- Monetisation and a storefront launch are out of scope

## Out of scope

- multiplayer
- monetisation and a storefront launch

## Open questions

- What would count as evidence that the slice is worth continuing — the developer's own judgement while playing, or feedback from outside playtesters?
- Does the developer already have an engine and 2D toolchain they work in, or is choosing one part of what the plan has to settle?
- Is art and audio production part of this three months, or is the slice expected to run on placeholder assets?

## Topic map

- [What makes it cozy and tense at once](topics/cozy_tense_contract.md): The audience is defined by a pairing that usually pulls apart, so the slice has to settle which exact feelings count as cozy (shelter, warmth, a full cache) versus tense (cold, hunger, being hunted), how they alternate or overlap in a single session, and what would tip it into either bleak or toothless.
- [The hoarding loop and what the player remembers](topics/caching_and_memory_loop.md): A squirrel's signature behaviour is burying food and finding it again, so the central design question is whether retrieval is tracked by the game, by the player's own memory, or by landmarks — each choice changes the core verb from bookkeeping to navigation to recall, and decides whether loss of a cache feels like drama or like paperwork.
- [Shape of one winter, start to finish](topics/winter_arc_pacing.md): The constraint is a single season played to completion, so the plan must establish whether there is an autumn preparation phase before scarcity, how long a full run takes in real minutes, how difficulty escalates as food thins, what the ending state is, and whether a failed run restarts the whole winter or something shorter.
- [Being small, cold and hunted in 2D](topics/prey_animal_verbs.md): The moment-to-moment feel depends on which animal pressures become mechanics — warmth, energy and torpor, predators overhead, climbing and the vertical layer of trees — and 2D means deciding whether the forest reads as a side-on climbable space or a top-down ground space, since that choice governs every control, threat and level layout downstream.
- [How much real squirrel behaviour to simulate](topics/simulation_versus_legibility.md): Animal authenticity is likely part of the appeal, but every hidden system (weather, food spoilage, predator routines, body condition) needs a readable surface the player can plan against, so it must be established where fidelity earns its keep and where an invisible simulation would just feel like unfair randomness.
- [What the first slice contains and how it is judged](topics/slice_scope_and_evidence.md): With one developer and roughly three months of evenings, the decision to build hinges on naming the smallest slice that tests the risky assumption rather than the easy one, what art and audio pipeline a solo developer can actually sustain for a forest and a winter, which playtest reactions would count as a yes, and what observation would make abandoning it the right call.

## How the topics connect

- The hoarding loop and what the player remembers conflicts with What makes it cozy and tense at once
- The hoarding loop and what the player remembers depends on Being small, cold and hunted in 2D
- Being small, cold and hunted in 2D informs What makes it cozy and tense at once
- How much real squirrel behaviour to simulate conflicts with What makes it cozy and tense at once
- How much real squirrel behaviour to simulate depends on Being small, cold and hunted in 2D
- How much real squirrel behaviour to simulate informs The hoarding loop and what the player remembers
- How much real squirrel behaviour to simulate informs What the first slice contains and how it is judged
- How much real squirrel behaviour to simulate informs Shape of one winter, start to finish
- What the first slice contains and how it is judged conflicts with Being small, cold and hunted in 2D
- What the first slice contains and how it is judged depends on The hoarding loop and what the player remembers
- What the first slice contains and how it is judged depends on What makes it cozy and tense at once
- What the first slice contains and how it is judged depends on Being small, cold and hunted in 2D
- What the first slice contains and how it is judged depends on Shape of one winter, start to finish
- Shape of one winter, start to finish conflicts with What makes it cozy and tense at once
- Shape of one winter, start to finish depends on The hoarding loop and what the player remembers

## Where to start

1. **Being small, cold and hunted in 2D:** Spend the first evenings settling the camera question and nothing else: build two throwaway grey-box movement tests of the same patch of forest — one side-on with a climbable trunk, one flat ground view — and record for each what the animal's body can express on screen, how many sprite states the walk/climb/freeze set would need, and whether an aerial threat with a visible tell can be dodged at all. Then write down the chosen perspective, the list of pressures that become mechanics versus stay as fiction, and the one threat type the slice will ship with, as a decision you will not revisit. Everything else in this plan is downstream of a choice that is effectively irreversible: controls, threat design, every level, and the art pipeline all inherit it, and this topic is the only one whose wrong answer would consume most of the available time to undo. It also depends on no other topic, so there is nothing to wait for. Settling it first converts the biggest budget risk into a fixed constraint the remaining steps can be planned against, rather than something discovered late.
2. **What makes it cozy and tense at once:** Write a one-page contract, in the chosen perspective's terms, that states which feelings count as cozy and which as tense, where each is allowed to live (place and time of day), and the largest setback a run may inflict — then state the two boundary conditions explicitly: what would make it bleak and what would make it toothless. Make it a rule the later steps must obey, with any always-on pressure meter named as permitted or forbidden up front. This depends on nothing, so it could have come first, but it is cheap to settle and only becomes concrete once the perspective and the pressures are fixed. It comes before caching, pacing and scope because each of those gets more interesting as it gets harsher, and without a written constraint the contract will be eroded one reasonable decision at a time. Putting it here means later steps are judged against a standard that already exists.
3. **The hoarding loop and what the player remembers:** Prototype one small patch of forest with a handful of distinct landmarks and a few chunky cache sites, then test retrieval with the HUD and all markers switched off: can a player find what they buried, and what minimum support (diegetic marks, a capped number of them, cache contents tracked but not position) makes that possible without turning recall into a list to read. Decide and record which of navigation, recall or planning is the core verb, and what visible tell a lost cache must carry. The signature verb can only be designed once the space it happens in has a perspective, and it must be designed against the contract so that cache loss is drama rather than unfairness. It comes before pacing because the length and escalation of a winter are shaped by how many cache sites exist and how long retrieval takes. It is also the cheapest place to discover that the loop is bookkeeping rather than a game, which is the finding most likely to stop the project early and cheaply.
4. **Shape of one winter, start to finish:** Lay out the season on paper as a day-by-day curve: total real minutes, number and length of days, whether an autumn phase exists and what its outcome visibly changes, what escalates besides scarcity, where recovery sits, what the ending state tells the player, and what a failure restarts. Then build only the scarcity peak — the hardest stretch — and play it with a hand-set starting stockpile, so the curve's worst case is testable before the phases that feed it exist. The arc can only be shaped once the retrieval loop's cost per excursion is known, because that is the unit the whole season is measured in. Building the peak rather than the opening comes here because the question the arc has to answer is whether difficulty rises or quietly falls away, and the only stretch that answers it is the one nothing else depends on. It must precede scope, since run length and restart cost set what a single playtest session can even observe.
5. **What the first slice contains and how it is judged:** Name the single riskiest assumption the slice exists to test, then write the slice definition around it: the smallest build that tests it with placeholder art, the hour budget for the three months with prototyping separated from content, the sustainable art and audio pipeline proven on an ordinary asset rather than a showpiece, the tester behaviours that count as a yes and as a no, where non-friend testers come from, scheduled checkpoints, and a stop condition agreed in advance. This is the decision the whole exercise is for, and it depends on all four earlier topics: the scope is bounded by the perspective's art cost, the contract's limits on harshness, the loop's shape, and the arc's length and restart rules. It comes last because a stop condition written before those are known would be unenforceable, and because the pass/fail signals must be phrased as observations of the specific loop that now exists rather than as general opinions about whether winter looks good.

Extensions of the idea are kept apart, in [dreams.md](dreams.md).
