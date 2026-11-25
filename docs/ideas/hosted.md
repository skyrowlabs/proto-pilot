# Hosted proto.pilot

> **`proto new`, which this would have hosted, left the tree on 2026-11-11**; it
> is readable at the tag `prototyping-final`. The argument below stays as written.
>
> **Status: TABLED 2026-09-03.** Superseded by
> [sketches-not-scaffolds.md](sketches-not-scaffolds.md), which takes the
> opposite route: proto.pilot ships as a tool other developers run, not as a
> service we host.
>
> Kept, not deleted. Most of the analysis below survives the decision — the
> automatic oracle, the cache-prefix argument, the three meanings of
> "self-improving", and the reason model creation is not this repo's job — because
> those are properties of the pipeline rather than of the service. What is
> tabled is the public front door and the corpus-from-strangers thesis it was
> built to serve. The successor doc says which parts it inherits.
>
> Read this one for the reasoning; read the successor for the decision.
>
> *Originally written 2026-08-28 as an idea, captured — not a plan, not
> scheduled, not costed.*

## The thesis

Put `proto new` behind a public web page, free, rate-limited, no login. Let
anyone describe an app and watch it get built and boot.

**The product is not the service. The product is the corpus.**

Every public run produces a row that is otherwise very expensive to buy: a
natural-language idea from someone who actually wanted it, the typed `spec.json`
it was reduced to, the five passes of generated source, and — the part that
matters — a machine-checked verdict on whether the result actually ran. The
long-term use of that corpus is training a model of our own that is good at this
specific task. Public access is how the corpus gets built. Free is the price of
collection, not a growth tactic.

That reframes the whole thing. If this were a business, the questions would be
conversion and retention. Because it is a data-acquisition programme, the
questions are coverage, signal quality, and cost per labelled example.

## What it would cost us, structurally

It reclassifies proto.pilot **from an internal instrument to a minor product.**
That is the real price, and it is not paid in dollars. A public endpoint means
uptime, abuse handling, a privacy posture, and a support surface, all attached to
a repo whose current job is to be useful to one operator on one machine. The
project's brief recorded
"whether proto.pilot is ever a released product or stays an internal instrument"
as the open question. This is one answer to it — and answering it costs the
freedom to change the tool without warning anyone.

## What already exists

More than you would expect, all on `feat/subscription-backend-and-front-end`,
unmerged.

`protopilot/web/app.py` is a FastAPI front end over the pipeline, written as a
*second caller* of `build`/`verify` rather than a second implementation — the CLI
stays the reference. `protopilot/jobs.py` already models a generation as a
background job you poll, because a generation takes minutes and HTTP will not
wait. `registry.py` tracks prototypes and knows how to delete one including its
Docker volumes.

Two assumptions in that code are load-bearing and are exactly what a hosted
version breaks:

- `jobs.py` says in its own docstring that the store is "in-process and
  in-memory on purpose … a single-user tool driving a local Docker daemon."
- `run_generation` hands back `http://localhost:{port}`.

Neither is wrong. Both are single-tenant.

## The four problems, in the order they bite

### 1. Isolation is the blocker, not the model

The five-path write guard in `files.py` constrains what the model may **write**.
It says nothing about what the written code **does at runtime**. Hosted, that
means unreviewed model-authored Python executing on our infrastructure, against a
live Postgres, on a URL a stranger can reach — not because anyone is attacking
us, but because someone asked for "an app that fetches a URL" and the model
obliged.

Locally this is fine; it is your machine and your idea. Publicly it is the entire
engineering problem, and it is chosen before anything else, because it sets
latency, cost and architecture. The shape required is per-session isolation with
egress blocked by default and hard CPU, memory and wall-clock caps —
Firecracker/gVisor-class, or a platform that already provides it (Fly Machines,
Cloud Run). "A bigger box running Docker Compose" is not a candidate.

### 2. Tokens are the bill; minutes are not

A session cap of ten minutes is a capacity limit, not a cost control. One
generation is intake + clarify + five passes + up to three repair attempts, on
Opus 5 at `effort: high` with adaptive thinking, each pass reading the previous
pass's real source. Cost per idea is measured in dollars, and the repair loop
means a *bad* idea costs more than a good one.

Two things already in the repo cut this, and both should be protected:

- **The stack brief is byte-identical across passes and repair attempts,
  specifically so it stays a cache prefix.** Hosted, every visitor on earth
  shares that prefix. This is a genuine structural advantage of a fixed stack and
  a reason the brief must not drift per-request.
- **`--offline` is a real free tier.** The deterministic baseline produces a
  running CRUD app with no key and no API call at all. The honest design is:
  anonymous visitors get the offline path unmetered, and the model path is what a
  quota and a human check protect.

A per-visitor quota without logins can only be enforced by IP, which is a speed
bump. The actual control is a hard daily spend ceiling on the funding account,
set so that the worst case is a page that says "come back tomorrow."

There is a third lever that removes the bill rather than capping it: **run the
model ourselves.** A local-model backend on our own GPU node — Qwen or
whatever else measures up — turns a generation into electricity instead of API
credit, which is the only version of this where "free and unmetered" is
honest at any volume. It is tracked in [NOTES](../NOTES.md) as its own idea
because it is worth doing whether or not this page ever exists, and the catch is
recorded there: every pass depends on schema-constrained output, so the serving
runtime has to provide it.

### 3. The learning signal is already in the pipeline

The instinct is to build a feedback widget. proto.pilot does not need one first,
because it has something rarer: **an automatic oracle on every single run.** Did
the stack boot, did `/healthz` go green (it checks the DB, so it stays red while
Postgres comes up), did the smoke suite pass, how many repair attempts were
needed, and if it hit the floor, which stage was red. That is a dense label on
100% of runs with nobody clicking anything, and it is the thing the corpus is
actually made of.

Explicit feedback from anonymous visitors is sparse and biased toward the
frustrated. Collect at most a one-click reaction on the finished result, and
treat it as a weak supplement to the verdict, never as the primary label.

The record worth keeping per run is: `idea → spec.json → per-pass output →
verify outcome → repair count → final stage`. Note that this makes the smoke
suite doubly interesting — it is generated *before* the code it tests, from the
spec, so it encodes what was *asked for* rather than what got built.

### 4. Ephemeral and "we learn from this" are both true, and must both be said

"No login, destroyed after the session" reads as private. "We learn from what you
described" means the description and the spec are kept indefinitely. Both are
defensible; holding both silently is not. The page states plainly, before the
box: the running app is destroyed, the description and what was built from it are
kept to improve the system.

Assume people paste real business ideas, because they will, and assume a
fraction paste something they should not have. That is an argument for keeping
the retained record narrow — the idea, the spec, the generated tree, the
verdict — rather than everything the process touched.

## What "self-improving" can concretely mean

Three different things, with different homes. They are frequently conflated and
should not be.

1. **Prompt and corpus work.** Mine the corpus for where specs come out wrong or
   passes come out red; improve the prompts. Available immediately, cheap, and
   the payoff is not speculative.
2. **Failure clusters into `skeleton/` and pass patches.** The loop that
   compounds. When the same failure recurs across many users, the fix almost
   always belongs in `skeleton/` — copied byte for byte into every app, so it is
   debugged once rather than once per prototype — or in a pass prompt. This is
   where an agentic loop is worth pointing, precisely because the artifact it
   produces is a diff that the offline baseline test suite can gate. A
   self-improving system whose output is a reviewable patch is tractable; one
   whose output is a weight update is not, at this stage.
3. **Training a model on the corpus.** The long-term thesis, and the reason for
   collecting at all. **This work does not land in this repo.** Model creation —
   datasets, fine-tuning, eval, adapters — belongs to a separate model project,
   and hosting the result to a separate hosting one.
   proto.pilot's role in that chain is *producer of a dataset* and, later,
   *consumer of an endpoint* through the existing `LLM` Protocol — which is
   already a one-method interface with three backends, so a fourth is not an
   architectural event.

Tier 3 is the goal. Tiers 1 and 2 are what pay for the wait, and neither of them
needs a hosted service at all — they only need the corpus to be bigger than one
operator can generate alone. That is the actual argument for going public.

## Where it would live

A separate website repo, named for the domain it serves, is the natural home
for the landing page. But the service is a stateful container orchestrator, not a
static site, and `skyrowlabs.com` has no build step by design.

So: the marketing page in that website repo, and the service as **a deployment of
this repo**. No service code in a website repo, and no new repo — a hosted
proto.pilot is proto.pilot with a different front door.

## Smaller pieces this implies

- **Download your prototype.** No export command exists today; `proto` covers
  `new`, `add`, `up`/`down`/`logs`/`test`, `spec`, `doctor`. A tarball of the
  tree with its compose file is small work. "Self-contained" still means the
  recipient needs Docker — say so on the page rather than implying a binary.
- **A human check.** Cloudflare Turnstile, since it needs no login and Cloudflare
  is already in use here.
- **Session teardown that cannot leak.** `registry.delete` already drops Docker
  volumes, and the known trap is that a tree removed any other way orphans one.
  Hosted, that trap becomes a slow storage leak with no operator watching it.

## Open questions

- Does the corpus reach useful size at a rate that justifies the ops burden, or
  does a few hundred runs a month take years to matter? This is the question that
  decides the whole idea, and it can be estimated before anything is built.
- Is the ephemeral, throw-it-away framing what draws people, given that v0,
  bolt.new, Lovable and Replit all promise the opposite? proto.pilot's honest
  pitch is the inverse of theirs — a fixed stack, verified before handback,
  explicitly not a production starting point.
- Does public exposure constrain the pipeline in ways that hurt the local tool?
  If hosted requirements start dictating what the CLI may do, the reference
  implementation has changed owner.
- Priority. Two other products come first, one of them pre-launch.
  This is a third thing with a recurring bill and an on-call surface.
