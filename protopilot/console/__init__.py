"""The `proto console` front end.

Named `console` and not `tui` on purpose: `tui` is the terminal **target** --
what `proto` generates -- and it already means that in five modules. See
`protopilot/console/app.py`.
"""

from protopilot.console.app import ConsoleApp, run

__all__ = ["ConsoleApp", "run"]
