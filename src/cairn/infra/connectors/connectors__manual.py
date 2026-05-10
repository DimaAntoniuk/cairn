from collections.abc import AsyncIterator, Iterable
from datetime import datetime

from cairn.domain import SourceDocument, SourceRef, SourceSystem
from cairn.domain.ingestion__ports import IConnector


class ManualConnector(IConnector):
    def __init__(
        self,
        documents: Iterable[SourceDocument],
        *,
        name: str = "manual",
        system: SourceSystem = SourceSystem.MANUAL,
    ) -> None:
        self._docs = list(documents)
        self.name = name
        self.system = system

    @classmethod
    def from_texts(
        cls,
        texts: Iterable[str],
        *,
        system: SourceSystem = SourceSystem.MANUAL,
        title_prefix: str = "doc",
    ) -> "ManualConnector":
        docs = [
            SourceDocument(
                ref=SourceRef(system=system, external_id=f"{title_prefix}-{i}"),
                title=f"{title_prefix}-{i}",
                content=text,
            )
            for i, text in enumerate(texts)
        ]
        return cls(docs, system=system)

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[SourceDocument]:
        for doc in self._docs:
            if since is not None and doc.ingested_at < since:
                continue
            yield doc
