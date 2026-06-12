import argparse
import asyncio
import sys

from cairn.domain import ConfigError
from cairn.tui.commands import ACTION_QUIT, CommandRouter, OutputFormat
from cairn.tui.render import strip_markup
from cairn.tui.session import LLMChoice, SessionConfig, build_session, has_module, seed_demo
from cairn.tui.session.session__consts import DEFAULT_LLM_MODEL, DEFAULT_TOKEN_BUDGET

# The Textual app pulls in `textual`; import it only when the extra is present so
# `cairn-tui` degrades to a friendly message instead of an ImportError traceback.
# Exec mode (--exec) deliberately avoids it, so it works without the extra.
_HAS_TEXTUAL = has_module("textual")
if _HAS_TEXTUAL:
    from cairn.tui.app.app__service import CairnApp


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value!r}")
    return n


def _parse_args(argv: list[str] | None) -> tuple[SessionConfig, list[str] | None]:
    parser = argparse.ArgumentParser(
        prog="cairn-tui",
        description="cairn — knowledge-layer terminal client (Claude-Code-style TUI)",
    )
    parser.add_argument(
        "--llm",
        choices=[choice.value for choice in LLMChoice],
        default=LLMChoice.AUTO.value,
        help="LLM backend (default: auto — anthropic if ANTHROPIC_API_KEY is set, else mock)",
    )
    parser.add_argument("--model", default=DEFAULT_LLM_MODEL, help="Anthropic model id")
    parser.add_argument(
        "--token-budget",
        type=_positive_int,
        default=DEFAULT_TOKEN_BUDGET,
        help="runtime context budget for /query (tokens)",
    )
    parser.add_argument(
        "--seed", action="store_true", help="preload demo artifacts/entities on launch"
    )
    parser.add_argument(
        "--exec",
        action="append",
        dest="exec_commands",
        metavar="CMD",
        default=None,
        help="run a slash command non-interactively and print the result "
        "(repeatable; skips the TUI — pair with --format json for agents)",
    )
    args = parser.parse_args(argv)
    config = SessionConfig(
        llm=LLMChoice(args.llm),
        model=args.model,
        token_budget=args.token_budget,
        seed=args.seed,
    )
    return config, args.exec_commands


async def _run_exec(config: SessionConfig, commands: list[str]) -> int:
    session = build_session(config)
    if config.seed:
        await seed_demo(session)
    # Plain by default so stdout is markup-free; commands opt into --format json.
    router = CommandRouter(session, default_format=OutputFormat.PLAIN)
    all_ok = True
    for command in commands:
        result = await router.dispatch(command)
        if result.body:
            # markup=True only when a command explicitly asked for --format rich.
            print(result.body if not result.markup else strip_markup(result.body))
        all_ok = all_ok and result.ok
        if result.action == ACTION_QUIT:
            break
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    config, exec_commands = _parse_args(argv)
    if exec_commands:
        try:
            return asyncio.run(_run_exec(config, exec_commands))
        except ConfigError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 1
    if not _HAS_TEXTUAL:
        sys.stderr.write(
            "cairn TUI requires the optional 'tui' extra:\n  pip install 'cairn[tui]'\n"
        )
        return 1
    CairnApp(config).run()
    return 0


__all__ = ["main"]
