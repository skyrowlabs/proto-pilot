---
title: "Drawing Freedom"
slug: drawing-freedom
shelf_status: planned
priority: high
updated: 2026-09-02
tags: [ui, verify, skeleton, archetypes, prompts]
summary: "Raise the visual ceiling of a generated app by ranking display options on whether the verifier can tell they worked — not on what Docker permits."
---

# Drawing Freedom

> **Status**: 🔴 Planned — designed, unreviewed
> **Shelf-Status**: planned
> **Priority**: High — it is the difference between output that is correct and
> output somebody wants to look at, and the cheapest rungs are blocked by our
> own rules rather than by anything real
> **Queue-Order**: unset until it is `ready`

## Problem

A generated app's visual ceiling is inline SVG inside a Jinja template. That is
a good ceiling for a board, a chart or a diagram, and it is the wrong ceiling
for anything that moves, anything computed per pixel, and anything whose whole
point is that it is *drawn*.

The ceiling was set by a constraint. The constraint is not real.

## What is actually true

Three things, checked rather than remembered, because every decision below
depends on them and all three were wrong in the prompts.

**1. The container has full outbound network access.** `STACK_BRIEF` tells
every code pass "The container has no outbound network access." The app service
sits on Compose's default bridge, nothing sets `internal: true`, and a
`python:3.12-slim` container on that default network reaches the open internet:

```
raw TCP egress: YES
CDN reachable from container: YES 200
```

That is a capability claim stated as fact, and nothing has ever checked it —
the exact class this repo spent 2026-09-01 naming.

**2. The no-CDN rule is unenforced, and the container could not enforce it.**
A `<script src="https://cdn…">` is fetched by the **browser**, not by the
container. So it would load on the machine that generated the app, pass the
browser stage, and fail for everybody else. Making finding 1 true — actually
isolating the network — would not fix this, because it is the wrong network.
The rule needs a grep, not a firewall.

**3. Build time has network, and needs no permission from anyone.** The
Dockerfile already runs `pip install`. Any single-file JavaScript library is
therefore a *skeleton file*: copied byte-for-byte like everything else in
`skeleton/`, served from `app/static/` which is already mounted, already
inside the hot-reload volume, and already byte-identical every generation.
No npm, no CDN, no build step, and no change to the fixed-stack invariant.

**4. The canvas verification already exists.** `browser.PAINTED_JS` reads pixels
back and fails a canvas that was never drawn on — precisely the failure every
other stage reports as fine. The reason canvas was discouraged was solved, and
the prompt never caught up.

## The axis that matters

Not "what does Docker allow", which is nearly everything. The binding
constraint is **can the verifier tell that it worked**, because that is this
tool's whole claim, and it is what actually separates these options:

| Rung | Ceiling | New deps | Verified by | Status today |
|---|---|---|---|---|
| SVG | Vector art, boards, charts, diagrams | none | It is in the DOM | Shipped, proven |
| Scoped CSS | Gradients, transforms, animation, clip-path, blend | none | DOM + browser stage | **Forbidden by our own rule** |
| Pillow raster | Arbitrary per-pixel, texture, plots | none — *installed* | 200 + bytes, assert not uniform | Available, unused |
| Canvas 2D | Real-time, interactive, animated | none | `PAINTED_JS` — already built | Permitted but discouraged |
| p5.js via `ASSETS` | Canvas, with an API the model knows cold | 1 vendored file | as canvas | Seam exists, empty |
| three.js / WebGL | 3D, shaders, per-pixel maths at 60fps | 1 vendored file | ⚠️ **nothing** | Blind spot |

The last row is the one to be careful about. `PAINTED_JS` says
`if (!ctx) return true; // webgl etc: assume drawn`. **A WebGL canvas is
assumed to have worked.** Shipping 3D before that is closed reintroduces
"worked fine, told nobody" at the exact moment the output is hardest to eyeball.

## Which axis does a display capability belong to

The test, and it falls straight out of the archetype/theme split:

> **If it needs an offline baseline, it is an archetype. If it does not, it is
> a theme.**

Palette, motif, drawn subject and a stylesheet cost one prompt fragment and no
baseline — theme. A tick loop, a canvas, a 3D scene changes what the pages
*are* and needs a deterministic implementation CI can run — archetype. That the
question answers itself is some evidence the two axes were cut in the right
place.

## Phase 1 — Stop lying in the prompts, and enforce the rule that is real

Cheap, and first because every later phase reasons from these sentences.

- [ ] `STACK_BRIEF` stops claiming the container has no outbound network. The
      rule it was protecting is real and worth keeping — state it as a rule:
      *you may not fetch anything at runtime*, with the reason, which is that
      the prototype must run on a machine that has never seen the internet
- [ ] A gate: no generated template may reference an external URL. This is the
      only thing that has ever enforced no-CDN, and it is three lines of regex
      over `app/templates/*.html`. It belongs in `verify`, not only in tests,
      because it is a property of the generated app rather than of this repo
- [ ] Decide and record whether the container *should* be isolated. It is a
      separate question from the rule above and the answer is probably no: the
      spec has an `external_apis` field, and an app that legitimately calls one
      would be broken by an isolation that never enforced the CDN rule anyway
- [ ] `intake.SYSTEM`'s capability list is re-checked against what is actually
      true after this phase, since it is the prompt that decides what goes in
      `limits` — and a wrong `limits` line is the tool promising less than it
      can do, in the user's own words, on the review screen

## Phase 2 — Scoped CSS, and the theme axis stops working around its absence

The cheapest rung, and it is blocked by us rather than by anything.

- [ ] The UI pass may write `app/static/theme.css`, a second stylesheet linked
      after `app.css`. It may not redefine the chrome classes; a test asserts
      that, because "do not write CSS" exists to prevent a second design
      system, and that reason survives — it just does not require zero CSS
- [ ] `ui.theme_block()` drops the apology. It currently says colour arrives as
      `fill` and `stroke` "because you may not write CSS", which is a workaround
      for a self-imposed rule described as if it were a constraint
- [ ] The offline baseline writes no `theme.css`, exactly as it ignores `theme`
      — the same reason: a theme must cost no baseline maintenance
- [ ] `files.py`'s allowed paths grow by one, deliberately and visibly. This is
      a load-bearing invariant and widening it is a decision, not a detail

## Phase 3 — Canvas stops being discouraged, and `simulator` becomes possible

The biggest capability win on the list, and it needs **no new dependency**.

- [ ] `ui.TASK`'s JavaScript section is rewritten from "here is why to avoid a
      canvas" to "here is when to reach for one", because the verification it
      was hedging against already exists
- [ ] `simulator` archetype: a tick loop, a canvas, and state that still lives
      in Postgres — the page must still work with JavaScript off, showing the
      current state as text or SVG. That rule is what makes a simulator
      verifiable rather than a black rectangle
- [ ] Its offline baseline. A deterministic simulation small enough to be
      honest and real enough to exercise a canvas end to end in CI — the same
      bar `turn-based-game` met with tic-tac-toe
- [ ] The generated smoke suite asserts a *tick changes state*, the direct
      analogue of `test_playing_to_a_win_shows_the_result`. A suite that checks
      for 200s cannot tell a running simulation from a paused one
- [ ] This is the plan the archetypes plan deferred `simulator` to. It turns
      out not to need the `ASSETS` seam at all, which is worth recording:
      the thing that looked like it needed a vendored asset needed a prompt
      change and a verifier that already existed

## Phase 4 — Pillow, which has been installed and unused all along

- [ ] The routes pass gets a worked example of serving a computed image, and
      the UI pass of pointing an `<img>` at it. Both prompts already mention
      this in one sentence and neither shows it
- [ ] A verify rail: an image route returns image bytes and the image is not
      uniform. A single flat colour is the raster form of the blank canvas
- [ ] Candidate uses named in the archetype briefs rather than in the shared
      brief, since "generate a texture" is not true of a gear tracker

## Phase 5 — One vendored library, on evidence

Deliberately last of the additive rungs, and conditional.

- [ ] **Gate: only if Phase 3 shows hand-written canvas failing often enough to
      matter.** Measure it, do not assume it. A megabyte per generated tree is
      a real cost and "the model would probably do better with p5" is a hunch
      until the repair-loop numbers say so
- [ ] If taken: p5.js as the first `ASSETS` entry, shipped in `skeleton/` and
      copied byte-for-byte, never fetched. `setup()`/`draw()` is structurally
      hard to get wrong and the corpus behind it is enormous
- [ ] The characterisation discipline applies: a vendored file must be
      byte-identical every generation or the golden manifests start churning

## Phase 6 — WebGL and 3D, gated on closing the blind spot

- [ ] **Prerequisite, not a task: `PAINTED_JS` must stop assuming a WebGL
      canvas was drawn.** `gl.readPixels` into a small buffer, or `toDataURL`
      on the WebGL canvas, and judge it the way a 2D canvas is judged. Until
      this lands, 3D output is unobserved and the tool's central claim does not
      hold for it
- [ ] Only then: three.js as an `ASSETS` entry, and the intake prompt's "3D is
      not buildable at all" becomes a capability rather than a `limits` line
- [ ] The concrete payoff, worth naming because it is the same idea twice: *"a
      cat and dog themed 3d chess app"* was the live-call test idea in both
      Phase 3 and Phase 4 of the archetypes plan, and the classifier honestly
      refused the 3D both times. This is what turns that refusal into a build

## Acceptance

- [ ] `./pp check pre-push` green
- [ ] No prompt asserts a runtime capability that is false; the network claim
      in particular is either true or restated as a rule
- [ ] A generated app referencing an external URL from a template fails verify,
      with the URL named
- [ ] A themed app writes `theme.css`, and a test proves it cannot redefine a
      chrome class
- [ ] A generated `simulator` boots, its canvas passes `PAINTED_JS`, its page
      still shows current state with JavaScript disabled, and its own suite
      asserts a tick changed something
- [ ] The offline baseline for `simulator` runs in CI with no Docker and no key
- [ ] Phase 5 is either taken with numbers behind it or left untaken with the
      numbers recorded
- [ ] If Phase 6 is taken, a WebGL canvas that was never drawn on fails verify —
      demonstrated, not assumed

## Dropped, and why

**A build step: npm, esbuild, a multi-stage Dockerfile.** It is the obvious way
to get every library at once and it costs the two things that make this tool
work. The fixed skeleton is debugged once rather than once per prototype, and a
build step makes each tree's failure modes its own. It also breaks hot reload,
which the repair loop depends on: `./app` is volume-mounted so uvicorn picks up
an edit in seconds, and a compile step puts a rebuild in that loop.

**Any CDN.** Not because of the container — the container's egress is
irrelevant, since the browser does the fetching. Because a prototype that needs
someone else's uptime to render is not a prototype you can hand to somebody, and
because it would pass verification on the machine that built it and fail
everywhere else, which is the worst possible shape for a defect.

**Letting the model write `app.css`.** The chrome stylesheet stays skeleton. The
rule against a second design system is right; Phase 2 keeps it by scoping the
second sheet rather than by forbidding CSS outright.

**Vendoring p5 or three.js up front.** Both are defensible and neither is
justified before the evidence. Phase 5 exists to make that a measurement.

**Isolating the container's network to make the prompt true.** It would enforce
nothing the rule needs — the CDN case is browser-side — and it would break the
`external_apis` field the spec already has. Fixing a false sentence by making
the world match it is only correct when the sentence was worth having.
