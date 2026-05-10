"""LLM abstraction with task-based model routing.

The spec maps task complexity to Claude tiers:

    Haiku   -> lightweight extraction, tagging, summarization, routing
    Sonnet  -> main semantic extraction, artifact generation, runtime shaping
    Opus    -> deep reasoning, strategy synthesis, conflict resolution

The router exposes those tiers as `LLMTask` values so callers never hard-code
a model id; the underlying Anthropic model strings can be upgraded centrally.

`LLMClient` is a `Protocol` so tests and offline pipelines can substitute a
deterministic stub. `AnthropicClient` is the production implementation; it
imports `anthropic` lazily so the package remains installable without it.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from ..errors import ConfigError, LLMError


class LLMTask(str, Enum):
    """Categories of work, used by the router to pick a model tier."""

    LIGHT = "light"  # tagging, routing, brief summaries
    STANDARD = "standard"  # main extraction, artifact compilation
    HEAVY = "heavy"  # synthesis, conflict resolution, evaluation


# Default mapping. Update here to roll out new model versions globally.
DEFAULT_MODEL_MAP: dict[LLMTask, str] = {
    LLMTask.LIGHT: "claude-haiku-4-5",
    LLMTask.STANDARD: "claude-sonnet-4-6",
    LLMTask.HEAVY: "claude-opus-4-7",
}


@runtime_checkable
class LLMClient(Protocol):
    """Minimal LLM interface used by the rest of the package."""

    async def complete(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        """Return the text completion for a single user turn."""
        ...

    async def complete_json(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        """Return a parsed JSON value. Implementations must validate parseability."""
        ...


class AnthropicClient:
    """Production `LLMClient` backed by the Anthropic SDK.

    The SDK is imported lazily so `cairn` can be installed without the
    `anthropic` extra (useful in test/CI environments that stub the LLM).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_map: dict[LLMTask, str] | None = None,
    ) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised when extra missing
            raise ConfigError(
                "anthropic extra not installed; pip install 'cairn[anthropic]'"
            ) from exc

        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
        self._model_map = model_map or DEFAULT_MODEL_MAP

    def _resolve_model(self, task: LLMTask) -> str:
        try:
            return self._model_map[task]
        except KeyError as exc:
            raise ConfigError(f"no model configured for task {task}") from exc

    async def complete(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        model = self._resolve_model(task)
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            raise LLMError(f"anthropic call failed: {exc}") from exc

        # Concatenate text blocks; ignore tool_use / other block types here.
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "".join(parts)

    async def complete_json(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        # Nudge the model toward valid JSON; still defensive on the parse.
        system_with_json = (
            f"{system}\n\nRespond with a single JSON value only. No prose, no fences."
        )
        raw = await self.complete(
            task=task,
            system=system_with_json,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # strip ```json ... ``` fences if the model added them anyway
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"model returned invalid JSON: {exc}\n---\n{raw[:400]}") from exc


class StubLLMClient:
    """Deterministic in-memory stub for tests and offline development.

    Constructor takes a mapping of (task, prompt-substring) tuples to canned
    responses, plus a default. Responses can be `str` or `dict` (the latter is
    returned by `complete_json`).
    """

    def __init__(
        self,
        responses: dict[tuple[LLMTask, str], Any] | None = None,
        default_text: str = "",
        default_json: Any = None,
    ) -> None:
        self._responses = responses or {}
        self._default_text = default_text
        self._default_json = default_json if default_json is not None else {}
        self.calls: list[tuple[LLMTask, str, str]] = []

    def _lookup(self, task: LLMTask, system: str, user: str) -> Any | None:
        haystack = f"{system}\n{user}"
        for (t, needle), value in self._responses.items():
            if t == task and needle in haystack:
                return value
        return None

    async def complete(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append((task, system, user))
        match = self._lookup(task, system, user)
        if isinstance(match, str):
            return match
        if match is not None:
            return json.dumps(match)
        return self._default_text

    async def complete_json(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        self.calls.append((task, system, user))
        match = self._lookup(task, system, user)
        if match is not None:
            if isinstance(match, str):
                return json.loads(match)
            return match
        return self._default_json


__all__ = [
    "DEFAULT_MODEL_MAP",
    "AnthropicClient",
    "LLMClient",
    "LLMTask",
    "StubLLMClient",
]
