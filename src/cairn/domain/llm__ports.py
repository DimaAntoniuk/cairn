from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResponse:
    content: str


class ILLMClient(Protocol):
    async def achat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ChatResponse: ...

    async def astructured_predict[T: BaseModel](
        self,
        output_cls: type[T],
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> T: ...


__all__ = ["ChatMessage", "ChatResponse", "ILLMClient"]
