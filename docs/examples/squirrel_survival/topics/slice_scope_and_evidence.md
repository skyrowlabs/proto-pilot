<!-- Rendered from .protopilot/plan.json. A re-render overwrites this file: do not edit it. -->

# What the first slice contains and how it is judged

> **Researched.** Cited findings rest on pages fetched during this run, each read through a model's summary of the page, not the page itself, so a citation shows the summary was read, never that the claim is in the source. Anything uncited is an assumption.

Part of [A survival game where you play a squirrel getting through its first winter](../PLAN.md).

With one developer and roughly three months of evenings, the decision to build hinges on naming the smallest slice that tests the risky assumption rather than the easy one, what art and audio pipeline a solo developer can actually sustain for a forest and a winter, which playtest reactions would count as a yes, and what observation would make abandoning it the right call.

## Findings

- Ron Gilbert argues the vertical slice is "a dumb way to build a game": it burns time and money producing something that looks \~90% done, and he recommends a prototype only where the gameplay or tech is genuinely risky, then iterative layering. For this project that means an ugly prototype of the hoard-and-starve loop, not a pretty forest. (sources: s18)
- Shelter, the closest commercial reference (prey animal, scarcity, young to feed), was faulted for exactly the risky part: food was so plentiful the feeding tension never appeared, levels could be restarted with fresh cubs at no penalty, and most encounters reduced to waiting then dashing. Its art was praised regardless. (sources: s19)
- **Assumption:** That review pattern suggests the slice's pass/fail question is whether scarcity bites and losses stick, not whether winter looks good. A credible yes is a tester who hesitates over which cache to dig up or rations food; a no is a tester who never feels short of anything, or who shrugs at a loss and restarts.
- A solo dev's playtesting account advises testing with placeholder graphics, watching for hesitation and confusion rather than asking for opinions ("I don't like this" is too broad to act on), and treating one player quitting in frustration as actionable signal. It sets no continue/stop threshold. (sources: s20)
- Useful abandonment tests: cost-to-finish math ignoring sunk time (if finishing needs a "somehow", it's doomed), and the redesign test — the loop still bores you and testers after several genuine redesign attempts. Define done up front as a few trusted signals checked on a schedule, e.g. testers finishing the build. (sources: s21)
- Hour budgets argue for brutal first-slice scope: one tracked solo project logged 3,850 hours over 600 days, with over half of the first year's 1,050 hours on prototyping and R&D alone, though the dev later reckoned a prototype phase could be 60-80 hours. Three months of evenings is plausibly 120-200 hours total. (sources: s22)

## Connections

- How much real squirrel behaviour to simulate informs What the first slice contains and how it is judged
- What the first slice contains and how it is judged conflicts with Being small, cold and hunted in 2D
- What the first slice contains and how it is judged depends on The hoarding loop and what the player remembers
- What the first slice contains and how it is judged depends on What makes it cozy and tense at once
- What the first slice contains and how it is judged depends on Being small, cold and hunted in 2D
- What the first slice contains and how it is judged depends on Shape of one winter, start to finish

## Risks

- The slice tests the easy assumption: a pretty forest and nice movement get built because they are tractable, while the risky question — does scarcity bite and do losses stick — goes untested, which is the trap the vertical-slice critique in the findings describes.
- Food ends up plentiful and the central tension never appears, the exact fault the closest prey-animal comparable drew; a solo developer tuning their own game is systematically biased toward generosity.
- Restarting at no penalty hollows out the stakes, and the slice therefore cannot measure whether loss matters because loss has been made free.
- Hour budget overrun: three months of evenings is a modest total, and the findings' logged solo-project numbers suggest prototyping alone can consume a large fraction of it, so the slice ends half-built and unjudgeable.
- Art and audio for a forest and a winter is an open-ended pipeline; committing to a style the developer cannot sustain for a full season means either a visibly unfinished game or months of unplanned asset work.
- Playtest feedback is collected as opinions rather than observed behaviour, so the result is unactionable and the build/no-build decision is made on vibes.
- No stop condition is defined in advance, so sunk time decides continuation; the project survives on the strength of the effort already spent rather than the evidence.
- The slice conflicts with the prey-animal verbs topic: climbing, verticality and expressive animation are the most appealing things to build and the least informative about whether the game works.
- Testers are drawn from people predisposed to like it (friends, the developer's circle), producing a false positive that only surfaces much later.

## Unknowns

- What is the single riskiest assumption — that hoarding and retrieval is fun, that scarcity creates tension, or that cozy and tense coexist — and which one can actually be tested first?
- What is the smallest build that answers that question, and can it be answered with placeholder art?
- What is the realistic hour budget for three months of evenings and weekends, and how much of it is prototyping versus content?
- What art and audio pipeline can one person sustain for an entire forest and season, and has that been tested on a representative sample asset rather than a hero asset?
- Which observed tester behaviours count as a yes — hesitating over which cache to open, rationing, returning for a second run — and how many testers must show them?
- Which observed behaviours count as a no — never feeling short, shrugging at a loss, quitting in frustration — and is a single frustrated quit treated as signal?
- How many genuine redesign attempts are allowed before the loop is judged unsalvageable?
- What does the cost-to-finish look like ignoring time already spent, and does the plan contain a step that currently reads as 'somehow'?
- Where do testers who are not friends or peers come from, and does recruiting them fit inside the timeline?
- How is progress checked on a schedule rather than at the end, and what are the checkpoints?

## Decisions to make

- Build an ugly prototype of the hoard-and-starve loop, versus a polished vertical slice of one area.
- Name the one risky assumption the slice must test and cut everything that does not serve it, versus testing several at once.
- Fix the hour budget and timebox the slice, versus building to a feature list and letting the schedule move.
- Choose an art style for sustainability first, versus for appeal first — and decide whether the slice ships with placeholders.
- Define the pass/fail signals and the stop condition in writing before building, versus deciding after seeing the build.
- Decide whether failure in the slice carries a penalty, since testing whether losses stick requires that they do.
- Test with strangers, versus with people the developer knows, versus both in sequence.
- Set a checkpoint schedule with named signals, versus a single go/no-go at the end of three months.
- Decide in advance what would make abandoning it the right call, and who makes that call.
