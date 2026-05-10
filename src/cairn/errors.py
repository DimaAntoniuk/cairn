"""Exception hierarchy for cairn.

A single root (`CairnError`) makes it trivial for callers to wrap the entire
library in one except clause when needed, while subclasses allow precise
handling of common failure modes.
"""

from __future__ import annotations


class CairnError(Exception):
    """Base class for all errors raised by cairn."""


class ConfigError(CairnError):
    """Misconfiguration of the layer or one of its components."""


class IngestionError(CairnError):
    """A connector failed to fetch or normalize source data."""


class ExtractionError(CairnError):
    """The semantic extraction pipeline failed or produced invalid output."""


class StoreError(CairnError):
    """A backing store (graph / vector / relational / object) failed."""


class RetrievalError(CairnError):
    """A retrieval planner or executor failed."""


class ContextBudgetError(CairnError):
    """Context assembly could not fit any fragments within the token budget."""


class LLMError(CairnError):
    """The underlying LLM provider returned an error or invalid response."""


__all__ = [
    "CairnError",
    "ConfigError",
    "ContextBudgetError",
    "ExtractionError",
    "IngestionError",
    "LLMError",
    "RetrievalError",
    "StoreError",
]
