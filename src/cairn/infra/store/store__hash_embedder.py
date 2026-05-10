from collections.abc import Sequence

from cairn.domain.store__ports import IEmbedder


class HashEmbedder(IEmbedder):
    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for token in text.lower().split():
            h = hash(token) % self.dim
            v[h] += 1.0
        norm = sum(x * x for x in v) ** 0.5
        if norm == 0:
            return v
        return [x / norm for x in v]

    async def embed(self, text: str) -> list[float]:
        return self._vec(text)

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]
