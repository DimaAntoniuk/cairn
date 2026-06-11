from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of one command, consumed by the UI layer.

    ``body`` is Rich markup appended to the transcript; ``action`` requests a UI
    side effect the router itself cannot perform (clear / quit).
    """

    body: str = ""
    refresh_sidebar: bool = False
    action: str | None = None
    ok: bool = True


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    arg: str
    help: str


__all__ = ["CommandResult", "CommandSpec"]
