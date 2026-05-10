"""Ingestion layer.

Connectors are responsible for pulling raw content out of a source system,
applying any source-specific normalization, and emitting `SourceDocument`s.

Real connectors (Gmail, Slack, Notion, Confluence, GDrive, Jira, CRM,
Transcripts, Databases) live in their own modules and are loaded on demand.
This module ships:

  * `Connector` protocol -- the contract every adapter satisfies
  * `BaseConnector`      -- helpers (pagination cursor, retry policy)
  * `ManualConnector`    -- accepts in-process documents, useful for testing
                            and for one-off ingestion scripts
  * `IngestionOrchestrator` -- pulls from many connectors concurrently and
                                hands documents to a sink callback
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from datetime import datetime
from typing import Protocol, runtime_checkable

import anyio

from ..errors import IngestionError
from ..schemas import SourceDocument, SourceRef, SourceSystem

log = logging.getLogger(__name__)


@runtime_checkable
class Connector(Protocol):
    """A source-system adapter."""

    name: str
    system: SourceSystem

    def fetch(self, *, since: datetime | None = None) -> AsyncIterator[SourceDocument]:
        """Yield normalized documents, optionally filtered by modification time."""
        ...


class BaseConnector:
    """Common scaffolding for real connectors.

    Subclasses implement `_fetch_page` and either return an empty list or
    raise `StopAsyncIteration` to signal completion. The base class handles
    retry on transient errors and emission of `SourceDocument`s.
    """

    name: str
    system: SourceSystem

    def __init__(self, *, max_retries: int = 3, backoff_seconds: float = 1.0) -> None:
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:
        """Return (documents, next_cursor). next_cursor=None ends the iteration."""
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


class ManualConnector:
    """Connector that yields a fixed in-memory list of documents.

    The primary use is testing pipelines without standing up a live data
    source. Also handy for batch-importing one-off content (e.g., a folder of
    transcripts) without writing a bespoke connector.
    """

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
    ) -> ManualConnector:
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


DocumentSink = Callable[[SourceDocument], Awaitable[None]]


class IngestionOrchestrator:
    """Drives multiple connectors concurrently and forwards docs to a sink.

    The sink is invoked sequentially per document to give downstream
    consumers a simple back-pressure model. Set `concurrent_connectors` to
    control how many connectors fetch in parallel.
    """

    def __init__(
        self,
        connectors: Iterable[Connector],
        *,
        sink: DocumentSink,
        concurrent_connectors: int = 4,
    ) -> None:
        self._connectors = list(connectors)
        self._sink = sink
        self._concurrent = concurrent_connectors

    async def run(self, *, since: datetime | None = None) -> int:
        """Pull from every connector once. Returns total documents forwarded."""
        counter = {"n": 0}
        limiter = anyio.CapacityLimiter(self._concurrent)

        async def drive(connector: Connector) -> None:
            async with limiter:
                async for doc in connector.fetch(since=since):
                    await self._sink(doc)
                    counter["n"] += 1

        async with anyio.create_task_group() as tg:
            for c in self._connectors:
                tg.start_soon(drive, c)
        return counter["n"]


__all__ = [
    "BaseConnector",
    "Connector",
    "DocumentSink",
    "IngestionOrchestrator",
    "ManualConnector",
]
