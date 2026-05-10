from typing import Any

from pydantic import BaseModel

from cairn.domain.llm__ports import ChatMessage, ChatResponse


class MockLLM:
    """Test double implementing the ``ILLMClient`` protocol.

    Matches canned responses by substring lookup against the prompt text.
    """

    def __init__(
        self,
        *,
        chat_responses: dict[str, str] | None = None,
        structured_responses: dict[str, Any] | None = None,
        default_chat: str = "",
    ) -> None:
        self._chat = chat_responses or {}
        self._structured = structured_responses or {}
        self._default_chat = default_chat
        self.calls: list[tuple[str, str]] = []

    def _lookup(self, haystack: str, store: dict[str, Any]) -> Any | None:
        for needle, response in store.items():
            if needle in haystack:
                return response
        return None

    async def achat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ChatResponse:
        text = " ".join(m.content for m in messages)
        self.calls.append(("achat", text))
        match = self._lookup(text, self._chat)
        if match is not None:
            return ChatResponse(content=match)
        return ChatResponse(content=self._default_chat)

    async def astructured_predict[T: BaseModel](
        self,
        output_cls: type[T],
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> T:
        self.calls.append(("astructured_predict", prompt))
        match = self._lookup(prompt, self._structured)
        if match is not None:
            if isinstance(match, output_cls):
                return match
            if isinstance(match, dict):
                return output_cls.model_validate(match)
        return output_cls.model_validate({})


__all__ = ["MockLLM"]
