from dataclasses import dataclass
from enum import StrEnum

from .session__consts import DEFAULT_LLM_MODEL, DEFAULT_TOKEN_BUDGET


class LLMChoice(StrEnum):
    """Which LLM backend the session should drive ``KnowledgeLayer`` with."""

    AUTO = "auto"  # anthropic when ANTHROPIC_API_KEY is set, else mock
    MOCK = "mock"  # always the bundled offline MockLLM
    ANTHROPIC = "anthropic"  # always Anthropic via the LlamaIndex adapter


@dataclass(frozen=True, slots=True)
class SessionConfig:
    llm: LLMChoice = LLMChoice.AUTO
    model: str = DEFAULT_LLM_MODEL
    token_budget: int = DEFAULT_TOKEN_BUDGET
    seed: bool = False  # preload demo artifacts/entities so the UI is explorable offline


__all__ = ["LLMChoice", "SessionConfig"]
