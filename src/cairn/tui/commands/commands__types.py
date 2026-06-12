from dataclasses import dataclass, field
from enum import StrEnum


class OutputFormat(StrEnum):
    """How a command result body is rendered.

    RICH is the human default in the TUI; PLAIN strips markup; JSON is a
    compact single-line machine envelope for agents.
    """

    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"


class FlagType(StrEnum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CSV = "csv"


class CommandUsageError(Exception):
    """A command line failed parsing or validation; the message is plain text."""


@dataclass(frozen=True, slots=True)
class FlagSpec:
    """One declarative ``--flag`` definition: drives parsing, /help, and the
    machine-readable schema from a single source."""

    name: str  # kebab-case as typed: "min-conf"
    type: FlagType
    help: str
    default: object = None
    choices: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        """Snake-case key used in ``ParsedArgs.values``."""
        return self.name.replace("-", "_")


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    arg: str
    help: str
    flags: tuple[FlagSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedArgs:
    """Result of parsing one command line: flags up front, raw tail as positional."""

    positional: str = ""
    format: OutputFormat = OutputFormat.RICH
    values: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of one command, consumed by the UI layer.

    ``body`` is Rich markup appended to the transcript when ``markup`` is True;
    plain/JSON bodies set ``markup=False`` so consumers escape or print them
    literally. ``action`` requests a UI side effect the router itself cannot
    perform (clear / quit).
    """

    body: str = ""
    refresh_sidebar: bool = False
    action: str | None = None
    ok: bool = True
    markup: bool = True


__all__ = [
    "CommandResult",
    "CommandSpec",
    "CommandUsageError",
    "FlagSpec",
    "FlagType",
    "OutputFormat",
    "ParsedArgs",
]
