<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# Being small, cold and hunted in 2D

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

The moment-to-moment feel depends on which animal pressures become mechanics — warmth, energy and torpor, predators overhead, climbing and the vertical layer of trees — and 2D means deciding whether the forest reads as a side-on climbable space or a top-down ground space, since that choice governs every control, threat and level layout downstream.

## Findings

- Gray squirrels do not hibernate: they scatter-hoard several thousand caches per season and relocate them by spatial memory against near and distant landmarks, with scent unreliable once ground is snow-covered. Only \~1 in 4 kits reach age one. That gives a free, legible mechanic: snow degrades smell-based recovery, so the player must navigate by remembered landmarks. (sources: s11)
- Real pressures map cleanly onto a vertical layer stack: main predators are hawks, owls and snakes; dense canopy and midstory give cover from aerial hunters; insulated dreys (30–60cm, moss/grass/feathers) cut heat loss and squirrels share them in cold spells; leaf-nest young survive 40% worse than cavity-den young; squirrels descend trunks head-first. (sources: s11)
- Perspective is mostly an art-budget decision for a solo dev: top-down needs \~1x sprite sets, side view 1–1.5x (mirrored, with handedness fixes), isometric 2–2.5x. Top-down also shows only the tops of heads — which would hide the tail, posture and shivering that carry a squirrel's whole read. (sources: s12)
- Rain World is the cautionary precedent for simulated predators in a 2D side-on world: creatures pursue their own goals, persist offscreen and have no fixed patrol routes, and the devs concede this made the game frustratingly hard, produced no-win situations for new players, and forced added guidance. Rooms were tuned to offer several evasion routes (ground, vents, pipework). (sources: s13)
- **Assumption:** For a cozy-tense slice, telegraph rather than simulate: one scripted aerial threat with a readable tell (shadow, alarm chatter from other squirrels, a few seconds to reach the trunk) gives tension that can be learned, while a self-interested predator AI risks the unfair deaths Rain World's team describe. Simulation depth belongs in the cache/weather systems, not the hunter.
- **Assumption:** The closest commercial comparable is Winter Burrow (2025), a cozy small-animal winter survival game with a warmth clock and crafting, usually described as laid-back with a bittersweet edge; squirrel-specific caching games appear to be mostly free game-jam entries. Verify its camera and reception directly before positioning against it.

## Connections

- The hoarding loop and what the player remembers depends on Being small, cold and hunted in 2D
- Being small, cold and hunted in 2D informs What makes it cozy and tense at once
- How much real squirrel behaviour to simulate depends on Being small, cold and hunted in 2D
- What the first slice contains and how it is judged conflicts with Being small, cold and hunted in 2D
- What the first slice contains and how it is judged depends on Being small, cold and hunted in 2D

## Risks

- The perspective choice is effectively irreversible and sits upstream of controls, threats and every level: choosing wrong costs most of the slice's budget to undo.
- A top-down camera hides the animal's read — tail, posture, shivering — which the findings identify as where the squirrel character lives; a side view preserves it but doubles the sprite work and adds handedness problems for a solo artist.
- A side-on climbable forest implies a vertical layer stack (ground, trunk, midstory, canopy), which multiplies level authoring, collision and threat design beyond what three months supports.
- Self-interested predator AI produces unfair deaths and no-win situations, the precedent the findings describe; the developer discovers this only after building it, late.
- Too many pressures at once: warmth, energy, torpor, aerial threat and climbing each need a readable surface, and stacking them makes the moment-to-moment feel busy rather than tense.
- Climbing controls are a genuine feel problem — head-first descent, branch-to-branch traversal — and can absorb unbounded iteration time while contributing nothing to the hoard-and-starve question the slice exists to test.
- Threat tells are built but not learnable: if the player cannot reliably convert the tell into a successful escape, the predator becomes weather rather than an opponent.
- This topic conflicts with the slice scope: the most expressive version of the animal is also the most expensive thing to build.

## Unknowns

- Is the forest a side-on climbable space or a top-down ground space — and which one does the caching loop actually need?
- Does verticality earn its cost, or can cover-from-above be expressed in a flat space through canopy density alone?
- Which pressures become mechanics and which stay as fiction: warmth, energy, torpor, cold-weather sheltering, nest insulation?
- How much time does a readable aerial threat need to give the player between tell and strike, and can that be tuned to feel fair without feeling trivial?
- Is there one threat type in the slice or several, and do ground and aerial threats require different evasion verbs?
- Should each space offer multiple escape routes by construction, and what does that constraint cost in level authoring time?
- Can snow be used as a mechanic that degrades scent-based recovery and forces landmark navigation, and is that legible to a player who does not know the natural history?
- What does the player's body condition look like on screen — meters, animation, sound, or a mix — and can it be read at a glance mid-chase?
- Does sharing a nest or any social element belong in the slice, or is it a second-pass feature?

## Decisions to make

- Commit to side-on or top-down before any art is produced, and record why, versus prototyping both at throwaway fidelity.
- Build climbing as a core traversal verb, versus restricting trees to a few fixed escape points.
- Use scripted, telegraphed threats, versus a persistent simulated predator with its own goals.
- Pick a maximum number of simultaneous survival pressures for the slice and cut the rest.
- Express body condition through animation and sound, through explicit meters, or both.
- Decide whether warmth is a timer, a location property, or a consequence of nest quality.
- Spend the art budget on expressive animation for one animal, versus on more environment and threat variety.
