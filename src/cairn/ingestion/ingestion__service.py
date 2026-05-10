import logging
from collections.abc import Iterable
from datetime import datetime

import anyio

from cairn.domain.ingestion__ports import DocumentSink, IConnector

log = logging.getLogger(__name__)


class IngestionOrchestrator:
    def __init__(
        self,
        connectors: Iterable[IConnector],
        *,
        sink: DocumentSink,
        concurrent_connectors: int = 4,
    ) -> None:
        self._connectors = list(connectors)
        self._sink = sink
        self._concurrent = concurrent_connectors

    async def run(self, *, since: datetime | None = None) -> int:
        counter = {"n": 0}
        limiter = anyio.CapacityLimiter(self._concurrent)

        async def drive(connector: IConnector) -> None:
            async with limiter:
                async for doc in connector.fetch(since=since):
                    await self._sink(doc)
                    counter["n"] += 1

        async with anyio.create_task_group() as tg:
            for c in self._connectors:
                tg.start_soon(drive, c)
        return counter["n"]


__all__ = ["IngestionOrchestrator"]
