"""cairn terminal client — a Claude-Code-style TUI over the knowledge layer.

Launch with the ``cairn-tui`` console script or ``python -m cairn.tui``. Requires
the optional ``tui`` extra::

    pip install 'cairn[tui]'
"""

from .cli.cli__service import main

__all__ = ["main"]
