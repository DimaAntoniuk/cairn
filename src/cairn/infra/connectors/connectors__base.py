import logging
from collections.abc import AsyncIterator
from datetime import datetime

import anyio

from cairn.domain import IngestionError, SourceDocument, SourceSystem
from cairn.domain.ingestion__ports import IConnector

log = logging.getLogger(__name__)


class ConnectorBase(IConnector):
    name: str
    system: SourceSystem

    def __init__(self, *, max_retries: int = 3, backoff_seconds: float = 1.0) -> None:
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:
        raise NotImplementedError

    async def fetch(self, *, since: datetime | None = None) -> AsyncIterator[SourceDocument]:
        cursor: str | None = None
        while True:
            page, cursor = await self._with_retry(cursor=cursor, since=since)
            for doc in page:
                yield doc
            if cursor is None:
                return

    async def _with_retry(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:
        attempt = 0
        while True:
            try:
                return await self._fetch_page(cursor=cursor, since=since)
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise IngestionError(
                        f"{self.name}: exhausted {self.max_retries} retries"
                    ) from exc
                log.warning("%s: attempt %s failed (%s), retrying", self.name, attempt, exc)
                await anyio.sleep(self.backoff_seconds * attempt)
