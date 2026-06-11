import argparse
import sys

from cairn.tui.session import LLMChoice, SessionConfig, has_module
from cairn.tui.session.session__consts import DEFAULT_LLM_MODEL, DEFAULT_TOKEN_BUDGET

# The Textual app pulls in `textual`; import it only when the extra is present so
# `cairn-tui` degrades to a friendly message instead of an ImportError traceback.
_HAS_TEXTUAL = has_module("textual")
if _HAS_TEXTUAL:
    from cairn.tui.app.app__service import CairnApp


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value!r}")
    return n


def _parse_args(argv: list[str] | None) -> SessionConfig:
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
    args = parser.parse_args(argv)
    return SessionConfig(
        llm=LLMChoice(args.llm),
        model=args.model,
        token_budget=args.token_budget,
        seed=args.seed,
    )


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(argv)
    if not _HAS_TEXTUAL:
        sys.stderr.write(
            "cairn TUI requires the optional 'tui' extra:\n  pip install 'cairn[tui]'\n"
        )
        return 1
    CairnApp(config).run()
    return 0


__all__ = ["main"]
