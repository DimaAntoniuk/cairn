from typing import Any

from pydantic import BaseModel

from cairn.domain import ConfigError
from cairn.domain.llm__ports import ChatMessage, ChatResponse


class LlamaIndexLLMAdapter:
    """Adapts any ``llama_index.core.llms.LLM`` to the cairn ``ILLMClient`` protocol."""

    def __init__(self, llm: Any) -> None:
        try:
            from llama_index.core import PromptTemplate
            from llama_index.core.llms import LLM as LlamaLLM  # noqa: N811
            from llama_index.core.llms import ChatMessage as LIChatMessage
        except ImportError as exc:
            raise ConfigError(
                "llamaindex extra not installed; pip install 'cairn[llamaindex]'"
            ) from exc
        if not isinstance(llm, LlamaLLM):
            raise TypeError(f"expected a LlamaIndex LLM, got {type(llm).__name__}")
        self._llm = llm
        self._LIChatMessage = LIChatMessage
        self._PromptTemplate = PromptTemplate

    async def achat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ChatResponse:
        li_messages = [
            self._LIChatMessage(role=m.role, content=m.content) for m in messages
        ]
        response = await self._llm.achat(li_messages, max_tokens=max_tokens, temperature=temperature)
        return ChatResponse(content=response.message.content or "")

    async def astructured_predict[T: BaseModel](
        self,
        output_cls: type[T],
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> T:
        # Escape braces so PromptTemplate treats them as literal text,
        # preventing KeyError/injection from user content containing {}.
        safe_prompt = prompt.replace("{", "{{").replace("}", "}}")
        pt = self._PromptTemplate(safe_prompt)
        return await self._llm.astructured_predict(
            output_cls, pt, llm_kwargs={"max_tokens": max_tokens, "temperature": temperature}
        )


__all__ = ["LlamaIndexLLMAdapter"]
