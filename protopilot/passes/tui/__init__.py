"""The terminal target's passes: `schema -> smoke -> seed -> screens -> ui`.

One module per pass, shaped exactly like the modules in `protopilot/passes/`
next door -- `NAME`, `WRITES`, `SCHEMA`, `build(spec, ctx)`, `offline(spec,
ctx)` -- so `run_pass` drives either target with no branch in it.

**The split is five, and that is a measured answer rather than a symmetry.**
`docs/implementations/spec/terminal-target.md` Phase 4 asks whether a Textual app splits the
same way a FastAPI one does, and the Phase 1 go/no-go ran all five live against
three specs: every one of them did work, and the expensive two are `smoke`
(~6.4x the web pass) and `screens` (~4.3x), with `schema`, `seed` and `ui` at
parity. If the split is ever revisited, that is where the money is.

The two invariants are this package's as much as `build.py`'s, and they are the
reason the order is not negotiable:

- **smoke is generated before the code it tests**, from the spec, when no
  screen exists yet -- so it describes what was asked for rather than what got
  built, and `screens` is then handed it as its target;
- **each pass is handed the previous pass's real source**, never a description
  of it. `ui` goes last and receives `app/screens.py`, because a stylesheet
  selecting an id no screen defines is silently dead -- the terminal analogue
  of a template referencing a context key no route passes.

`tests/test_tui_passes.py` holds both, computed from these modules rather than
listed, so a sixth pass or a reordering is caught by existing rather than by
somebody remembering.

Prompt text lives in `_brief.py`; it is the material the Phase 1 measurement
actually ran, moved rather than rewritten.
"""

from __future__ import annotations
