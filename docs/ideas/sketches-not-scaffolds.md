# Sketches, not scaffolds — the terminal pivot

> **Status: a direction, decided.** Captured 2026-09-03. It supersedes
> [hosted.md](hosted.md), which is now tabled.
>
> **A plan has been cut from its first buildable slice** —
> [`docs/TODO/terminal-target.md`](../implementations/spec/terminal-target.md), the `target`
> axis and the terminal target, gated on a measurement. This doc stays here and
> holds the *argument*; the plan holds the phases and does not repeat it.
>
> **That slice landed 2026-09-04.** `proto new` builds a Textual + SQLite
> terminal app unless told otherwise — decision 1 below is now what the code
> does, not what it intends. Decision 2 is unchanged in effect and decision 3 is
> still a decision without a flip. The web target stays reachable by
> `--target web`, green and generated in CI.
>
> That is a refinement of this folder's own rule, which said a doc moves to
> `docs/TODO/` when someone decides to build it. It moves when the **whole**
> idea becomes the plan. When a plan is cut from a **slice**, the idea stays and
> is linked — because the two are not duplicates. One is why, one is how, and
> the workspace rule that governs both is that a doc lives where it changes.
> Decisions 2 and 3 here are not build tasks and have no plan to move into.

## Three decisions

1. **proto.pilot emits a terminal app, not a web app.** The target medium changes.
2. **The artifact is a sketch to learn from, not a scaffold to build on.** Not a
   softening of the current disclaimer — a change to what gets generated.
3. **It ships as an open-source project other developers run, not as a service we
   host** — the same shape as skeletor. This answers the open question in the
   project brief, and it answers it with a third option that was never on the
   list: not "internal instrument" and not "minor product", but a tool given
   away. The repo already has the MIT licence, the `v0.1.0` tag and the
   `develop` branch cut for exactly this; what it has not had is the decision.

## The request was never "make me a camping app"

The README sells `proto new "track camping gear across trips"` and hands back a
FastAPI + Postgres app. That framing invites a comparison the tool loses: against
v0, bolt.new, Lovable and Replit, "describe an app, get an app" is a race to
build something you would keep, and this tool explicitly does not want to be kept.

The real request has a different shape:

> Iterate to this idea and show me a prototype. It is nothing that would be built
> on. It is an idea to test and learn from.

Two words in that carry the design. **Iterate** — the value is in the loop, not
the artifact. **Learn** — the output is evidence about an idea, and evidence is
allowed to be ugly, partial and thrown away by lunchtime.

## The medium has to enforce the disclaimer, because prose does not

`README.md` already says the output is "not a starting point for production — a
thing to look at this afternoon." Then it hands you FastAPI, SQLAlchemy 2.0,
Postgres, a Dockerfile and a compose file. **That is the shape of a real
application**, and the shape wins over the sentence every time. Somebody will
build on it, because everything about it says you may.

A terminal app cannot make that promise by accident. Nobody mistakes a Textual
prototype for a production service, so the artifact stops arguing with the
disclaimer and the tool gets to be honest without repeating itself.

## The loop closes, which is the real argument

This is the reason that survives even if you disagree with everything above.

A web target forces a context switch on every iteration: generate in the
terminal, alt-tab to a browser, look, come back, describe the change. The loop
crosses a surface boundary twice per turn, and "iterate to this idea" is a loop
you run ten times in an afternoon.

**If the artifact is a terminal app, the tool and the artifact live on the same
surface.** `proto` can run the prototype in a pane, next to the spec it came
from and the change box you type into. Describe, watch it build, look at it,
adjust — without leaving the thing you are already in. That is not a nicer
version of the current experience. It is a different product, and it is the one
the request describes.

## What gets better, concretely

**Verification gets cheaper and less flaky.** The current weakest stage is the
browser one — optional, Playwright-heavy, and it exists only because `/healthz`
returns 200 for a page that paints nothing. In a terminal app that check is a
screen-buffer comparison. Textual ships `App.run_test`, a pilot that presses
keys and clicks, and snapshot testing that diffs the rendered screen. No browser,
no headless Chrome, no flake. And the `/healthz`-waits-on-Postgres race the whole
verify loop is built around disappears with Postgres.

**The stack shrinks by a whole tier.** Textual plus SQLite is one process. No
compose file, no second service, no port allocation, no orphaned volumes — which
deletes the entire class of problem `proto gc`, `proto prune` and the Docker
resource labels exist to manage.

**Distribution stops being an ops problem.** An open-source tool is
`pipx install` and the user's own API key. That dissolves the cost problem
hosted.md spends its longest section on: **the user pays for their own tokens.**
No spend ceiling, no Turnstile, no IP quota, no abuse surface, no privacy
posture. And `--offline` is a genuine free tier rather than a rationed one —
somebody can run the whole pipeline, with no key at all, and see what it does.

Open source also changes what the corpus argument was ever going to be. Hosted,
the runs happen on our infrastructure and the corpus accrues to us by default.
Given away, they happen on other people's machines and it does not — anything
collected would have to be opt-in and said plainly. That is a real cost of this
route and it is worth naming rather than discovering later.

## What survives, and it is most of it

The five decisions in `README.md` are about *method*, not medium, and four
transfer unchanged:

- **The stack is fixed, not chosen.** Still true, just a different fixed stack.
- **The model may write only N paths.** `files.py` is unchanged in principle.
- **Tests are generated before the code they test.** `App.run_test` is the
  in-process client's analogue, so the `schema → smoke → …` order holds.
- **Nothing is handed back unobserved.** Cheaper and more deterministic, per above.

**Archetypes get more useful, not less.** The axis landed on 2026-09-01 with
`crud` and `turn_based_game`, and a terminal is where that vocabulary is native —
`DataTable`, `Tree`, `Tabs` and a board are layout shapes an archetype can own
much more concretely than "a `custom` screen with inline SVG." The plugin
contract (`MATCHES`, `EXTRA`, `screens()`, `brief()`, `offline()`) does not change.

**The offline baseline survives and stays load-bearing.** A deterministic Textual
CRUD app is well within reach, and without it the suite stops being runnable
without a key.

## What it costs

- **The web generation work is real investment**: five pass prompts, 24 skeleton
  files, the browser stage. Leaning into the terminal does not require deleting
  it — see the migration note below — but it does mean it stops being the default.
- **Model competence is the open risk.** There is far more FastAPI + Jinja in the
  pretraining set than Textual. Fewer examples means more repair attempts, and a
  bad generation already costs more than a good one. **This is the one thing that
  could invert the whole argument, and it is measurable before committing.**

  **Measured 2026-09-04, and it did not invert.** Six runs, three specs, both
  targets: mean repair attempts identical at 2.33, every run green. The scarcity
  is real but it shows up as *thinking time* — 1.69× wall clock, concentrated in
  the `smoke` and `screens` passes — rather than as failure. Time is spent once
  per generation; repair attempts compound. The risk this paragraph names was
  the right one to name and the answer was no.
  [The numbers](../reports/occasional/2026-09-04-terminal-target-go-no-go.md).
- **Medium mismatch is real.** Some ideas want to be a web page. The honest answer
  is that this tool stops serving those, which is the point of narrowing.

## The migration is an axis, not a rewrite

Add `target` as a second axis beside `archetype`, and build the terminal target as
the second one. The archetype work just proved this exact plugin shape on this
exact code, so the machinery exists.

It also turns the risk above into a measurement instead of a bet: generate one
spec both ways and compare repair counts, tokens and verify wall-clock. That is
the estimate hosted.md said should happen before anything is built — it just
turned out to be about the target rather than the audience.

The expectation was that the terminal target becomes the default and the web one
becomes legacy. **Half of that happened on 2026-09-04**: `targets.DEFAULT` is
`tui`, and the web target is *not* legacy — it keeps its five passes, its
skeleton, its verifier and its offline baseline green and generated in CI,
because it is the only control this repo has for telling a target regression
apart from a change regression. "Not the default" and "legacy" turned out to be
different states, and the second is still a later call that does not need making
now.

## What this settles from hosted.md

Tabling the hosted service does not throw away everything in that doc:

- **The corpus thesis survives in reduced form.** Its own tiers 1 and 2 — prompt
  work, and failure clusters that land in `skeleton/` — never needed strangers,
  only more runs than one person generates by hand. Synthesised ideas run
  overnight against the automatic oracle give exactly that, with no ops.
- **The automatic oracle was always the rare part**, and it belongs to the
  pipeline, not the service. It gets better in the terminal.
- **Tier 3, training a model on the corpus, is unchanged and still not this
  repo's job** — that is mind.head's, per the workspace seam.
- **What is genuinely given up** is the distribution of *real* intent: which
  ideas strangers actually want. That is one column of the row, and it is the
  column you can buy last.
- **The service ambition is detached, not killed** — and that distinction is
  somebody else's to resolve. The workspace's open research question R1 aims at
  "a public-facing skyrow.ai that turns an idea into a running app, as a
  service", and names this pipeline as the vehicle. Tabling the hosted page does
  not settle skyrow.ai: **a service could be built on the same models without
  being `proto`.** What it settles is that R1 can no longer assume proto.pilot
  is the front door. Read `docs/ideas/hosted.md`'s "Where it would live" section
  with that in mind — its conclusion (marketing page in `skyrowlabs.ai`, service
  as a deployment of this repo) is the half that is now withdrawn.

  (Raised by skyrow-workspace, who own R1 and have flagged the tension in place
  rather than resolving it.)

## Open questions

- **Does Docker survive?** Still open, and now open with the fact in hand: the
  terminal target ships with no container, so model-authored code from a default
  `proto new` already runs unsandboxed on the machine that asked for it. That is
  the trade this bullet describes, taken by default rather than decided. Their
  machine and their idea, knowingly running a code generator — the same argument
  that makes it fine locally today — but it should be a decision, not a drift.
  Probably: optional isolation rather than the stack. The web target keeps its
  container and is not the answer to this, because it is a medium rather than a
  sandbox.
- **Does a sketch need persistence at all?** A file-backed SQLite makes a
  prototype feel real; a JSON file might be enough. "Add a trip and it is still
  there" is most of what makes an idea testable, so probably yes, but small.
- ~~**What replaces the five passes?**~~ **Answered by measurement, and it is
  five.** `schema → smoke → seed → screens → ui`. All five did real work across
  six live runs; the expensive two are `smoke` (~6.4× its web twin) and `screens`
  (~4.3×), with the other three at parity. If the split is ever revisited, that
  is where the money is.
- **Does `proto` become a TUI itself, or does it host one?** These are separable.
  The tool having a TUI is useful today, independent of everything above.
- **Is "released tool" a v0.2.0 or a v1.0.0 promise?** Going public means other
  people's expectations attach to the CLI surface. The repo already has the
  licence, the tag and the `develop` branch; what it does not have is a decision
  about what it is promising not to break.
