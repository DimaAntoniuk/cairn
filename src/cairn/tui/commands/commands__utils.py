import re
from enum import StrEnum

from cairn.tui.serialize import dumps

from .commands__types import (
    CommandSpec,
    CommandUsageError,
    FlagSpec,
    FlagType,
    OutputFormat,
    ParsedArgs,
)

# Appended to every command by the parser so it never needs repeating in COMMANDS.
FORMAT_FLAG = FlagSpec(
    "format",
    FlagType.STR,
    "output format (json is compact single-line, for agents)",
    default=None,
    choices=tuple(f.value for f in OutputFormat),
)

# One token: a quoted span or a bare run of non-whitespace, with leading
# whitespace consumed. Offsets matter (shlex hides them): when flag parsing
# ends, the positional is the RAW remainder of the line, sliced from the
# token's start, so /ingest payloads keep their exact whitespace.
_TOKEN_RE = re.compile(r"""\s*(?:"([^"]*)"|'([^']*)'|(\S+))""")
_FORMAT_PEEK_RE = re.compile(r"--format\s+(\S+)")


def default_values(spec: CommandSpec) -> dict[str, object]:
    return {flag.key: flag.default for flag in spec.flags}


def coerce_enum[E: StrEnum](enum_cls: type[E], raw: str) -> E:
    """Parse an enum value case-insensitively, with a helpful error."""
    try:
        return enum_cls(raw.lower())
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        raise CommandUsageError(f"unknown value {raw!r} (one of: {allowed})") from None


def peek_format(arg: str, default: OutputFormat) -> OutputFormat:
    """Best-effort --format detection, used to render parse errors in the
    format the caller asked for even when the full parse fails."""
    match = _FORMAT_PEEK_RE.search(arg)
    if match:
        try:
            return OutputFormat(match.group(1).lower())
        except ValueError:
            pass
    return default


def _coerce(flag: FlagSpec, raw: str) -> object:
    if flag.type is FlagType.INT:
        try:
            return int(raw)
        except ValueError:
            raise CommandUsageError(f"--{flag.name} expects an integer, got {raw!r}") from None
    if flag.type is FlagType.FLOAT:
        try:
            return float(raw)
        except ValueError:
            raise CommandUsageError(f"--{flag.name} expects a number, got {raw!r}") from None
    if flag.type is FlagType.CSV:
        items = tuple(part.strip() for part in raw.split(",") if part.strip())
        if flag.choices:
            items = tuple(_check_choice(flag, item) for item in items)
        return items
    return _check_choice(flag, raw) if flag.choices else raw


def _check_choice(flag: FlagSpec, raw: str) -> str:
    value = raw.lower()
    if value not in flag.choices:
        allowed = ", ".join(flag.choices)
        raise CommandUsageError(f"invalid value {raw!r} for --{flag.name} (one of: {allowed})")
    return value


def parse_args(spec: CommandSpec, arg: str, *, default_format: OutputFormat) -> ParsedArgs:
    """Parse ``--flag [value]`` pairs from the front of ``arg``.

    The first token that is not a flag (or an explicit ``--`` separator) ends
    flag mode; the raw remainder of the string becomes the positional text.
    """
    flags = {f.name: f for f in (*spec.flags, FORMAT_FLAG)}
    values = default_values(spec)
    fmt = default_format
    positional = ""
    pos = 0
    while pos < len(arg):
        match = _TOKEN_RE.match(arg, pos)
        if match is None:
            break
        token, token_start, quoted = _token_of(match)
        if quoted or not token.startswith("--"):
            positional = arg[token_start:]
            break
        if token == "--":
            tail = _TOKEN_RE.match(arg, match.end())
            positional = arg[_token_of(tail)[1] :] if tail else ""
            break
        name = token[2:]
        flag = flags.get(name)
        if flag is None:
            known = ", ".join(f"--{f}" for f in flags)
            raise CommandUsageError(f"unknown flag --{name} for /{spec.name} (flags: {known})")
        if flag.type is FlagType.BOOL:
            values[flag.key] = True
            pos = match.end()
            continue
        value_match = _TOKEN_RE.match(arg, match.end())
        if value_match is None:
            raise CommandUsageError(f"--{name} requires a value")
        raw_value = _token_of(value_match)[0]
        coerced = _coerce(flag, raw_value)
        if flag is FORMAT_FLAG:
            fmt = OutputFormat(str(coerced))
        else:
            values[flag.key] = coerced
        pos = value_match.end()
    if positional and not spec.arg:
        raise CommandUsageError(
            f"/{spec.name} takes no positional text (got {positional!r}) — did you mean a --flag?"
        )
    return ParsedArgs(positional=positional, format=fmt, values=values)


def _token_of(match: re.Match[str]) -> tuple[str, int, bool]:
    """Return (token text, raw start offset incl. quote, was quoted)."""
    for group in (1, 2):
        if match.group(group) is not None:
            return match.group(group), match.start(group) - 1, True
    return match.group(3), match.start(3), False


def json_help(commands: tuple[CommandSpec, ...]) -> str:
    """Machine-readable schema of the command surface, --format included."""
    payload = [
        {
            "name": spec.name,
            "arg": spec.arg,
            "help": spec.help,
            "flags": [
                {
                    "name": flag.name,
                    "type": flag.type.value,
                    "default": flag.default,
                    "choices": list(flag.choices),
                    "help": flag.help,
                }
                for flag in (*spec.flags, FORMAT_FLAG)
            ],
        }
        for spec in commands
    ]
    return dumps({"ok": True, "commands": payload})


__all__ = [
    "FORMAT_FLAG",
    "coerce_enum",
    "default_values",
    "json_help",
    "parse_args",
    "peek_format",
]
