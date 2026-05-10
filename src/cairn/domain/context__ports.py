from abc import ABC, abstractmethod


class ICompressor(ABC):
    @abstractmethod
    async def compress(self, text: str, *, target_tokens: int) -> str: ...


__all__ = ["ICompressor"]
