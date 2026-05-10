from .llm__consts import DEFAULT_MODEL, HEAVY_MODEL, LIGHT_MODEL
from .llm__mock import MockLLM

__all__ = [
    "DEFAULT_MODEL",
    "HEAVY_MODEL",
    "LIGHT_MODEL",
    "MockLLM",
]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name == "LlamaIndexLLMAdapter":
        from .llm__llamaindex import LlamaIndexLLMAdapter

        return LlamaIndexLLMAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
