from cairn.domain.store__ports import IVectorStore


class InMemoryVectorStore(IVectorStore):
    def __init__(self) -> None:
        self._items: dict[str, tuple[list[float], str, dict[str, object]]] = {}

    async def upsert(
        self,
        *,
        id: str,
        vector: list[float],
        text: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._items[id] = (vector, text, metadata or {})

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot: float = sum(x * y for x, y in zip(a, b, strict=False))
        na: float = sum(x * x for x in a) ** 0.5
        nb: float = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return float(dot / (na * nb))

    async def search(
        self, *, vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float, str, dict[str, object]]]:
        scored = [
            (item_id, self._cosine(vector, vec), text, meta)
            for item_id, (vec, text, meta) in self._items.items()
        ]
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored[:top_k]
