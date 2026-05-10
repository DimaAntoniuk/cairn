from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from .source__types import SourceDocument, SourceSystem


class IConnector(ABC):
    name: str
    system: SourceSystem

    @abstractmethod
    def fetch(self, *, since: datetime | None = None) -> AsyncIterator[SourceDocument]: ...


DocumentSink = Callable[[SourceDocument], Awaitable[None]]


__all__ = ["DocumentSink", "IConnector"]
