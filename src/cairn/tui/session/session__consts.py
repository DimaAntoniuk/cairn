from cairn.infra.llm import DEFAULT_MODEL

# Default Anthropic model used when an API key is available.
DEFAULT_LLM_MODEL = DEFAULT_MODEL

# Runtime context budget for `/query` (tokens).
DEFAULT_TOKEN_BUDGET = 2000

# Width of the right-hand artifacts/entities sidebar (cells).
SIDEBAR_WIDTH = 34

APP_TITLE = "cairn"
APP_SUBTITLE = "agent knowledge layer"

MOCK_LABEL = "mock · offline"

__all__ = [
    "APP_SUBTITLE",
    "APP_TITLE",
    "DEFAULT_LLM_MODEL",
    "DEFAULT_TOKEN_BUDGET",
    "MOCK_LABEL",
    "SIDEBAR_WIDTH",
]
