# The three specs

The measurement is about **code generation**, not intake. So the spec is an
input to both halves of the comparison and is never regenerated between them:
the same file drives the web run and the terminal run, and any difference in
the result is a difference in the target.

They were assembled offline — no live intake call — and every one of them was
put through `Spec.model_validate` and `archetypes.screens_for()`, so the screen
list is the tool's own rule rather than a guess. `tests/test_terminal_spike.py`
re-checks that on every run: a spec whose screens drifted from the archetype's
rule would silently measure a spec the tool would never have produced.

| Spec | Archetype | Why it is here |
| --- | --- | --- |
| `kitten_chess` | `turn-based-game` | The only real `spec.json` on disk, from an actual generation. The board is the app. |
| `field_notes` | `crud` | The ordinary case — a two-entity tracker with a parent/child. If a target cannot do this, it cannot do anything. |
| `seating_plan` | `crud` | The deliberately awkward one. |

## What is awkward about `seating_plan`, and why that shape

It is awkward in the same way for both targets, which is the point — a shape
that is hard for the terminal and easy for the web would measure the shape, not
the target. It has:

- **three entities and a two-deep parent chain** (Guest → Table → Room), so the
  detail screens have to show children of children;
- **every field type the spec language has** — `str`, `text`, `int`, `float`,
  `bool`, `date`, `datetime` — which is where the two mediums diverge most
  mechanically: the web has an `<input type="datetime-local">` and the terminal
  has a text box and a parser;
- **a `custom` screen that is a picture.** `/rooms/{row_id}/plan` is a top-down
  sketch of the room. On the web that is inline SVG, which the UI pass has a
  page of prompt about. In a terminal it is a grid of characters and there is
  no equivalent prompt, because there is no equivalent capability;
- **a `direction` that asks for the picture explicitly** — "I want to look at
  the room, not read a table of names" — so a target that quietly produces a
  list instead has visibly not built what was asked for.

## `kitten_chess` is not byte-identical to the tree it came from

`prototypes/kitten_chess/.protopilot/spec.json` was written before the archetype
axis existed, so it loads as `crud` and carries the CRUD screen spread. Three
changes were made, all recorded here rather than in the file:

1. `archetype: "turn-based-game"`, with the `theme`, `answers` and `extra`
   (an 8×8 board) that a spec written today would carry.
2. The entity `Game` was renamed to `Match`, and `Move.belongs_to` with it.
   This is **forced**, and it is a finding: `turn_based_game.screens()`
   hard-codes an entity named `Match`, so any turn-based spec whose entity is
   called anything else gets screens pointing at an entity it does not have —
   and `checkable_paths` then hands the browser stage a `/matches` that no route
   serves. Left as it was, the web half of this comparison would have failed for
   a reason that has nothing to do with the web target.
3. The screens were re-resolved through `archetypes.screens_for()`, which is
   what the rename requires and what the tool does today anyway.

4. Three `limits` sentences were made medium-neutral. The originals said the
   players "take turns at the same browser" and the pieces are "drawn shapes",
   because `limits` is intake's record of *what the fixed stack cannot do* —
   and the fixed stack is precisely what a target axis changes. Handing that
   text to a Textual pass tells the model it is building a web page. The
   meaning is unchanged; only the medium words are gone. This is the second
   place the plan's four-thing table comes up short: after the archetype brief,
   `limits` is target-coupled too.
