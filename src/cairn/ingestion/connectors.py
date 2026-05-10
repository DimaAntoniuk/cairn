"""Connector scaffolds for the source systems listed in the spec.

These are intentionally thin: each class wires up authentication and a
`_fetch_page` skeleton that delegates to the source-system SDK. They do *not*
ship the SDKs as required dependencies — install the relevant extras to use
them in production.

The point of including them in the package is to give users a uniform place
to plug in real credentials without having to invent the integration shape
themselves; each class documents the minimum it needs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..errors import ConfigError
from ..schemas import SourceDocument, SourceRef, SourceSystem
from . import BaseConnector


class GmailConnector(BaseConnector):
    """Pulls messages from a Gmail mailbox via the Google API.

    Requires `google-api-python-client` and OAuth credentials. The user must
    pass an authenticated `service` object; this keeps auth concerns out of
    the connector and lets enterprise users plug in service-account or
    delegated flows.
    """

    name = "gmail"
    system = SourceSystem.GMAIL

    def __init__(self, *, service: Any, query: str = "", page_size: int = 100) -> None:
        super().__init__()
        if service is None:
            raise ConfigError("GmailConnector requires an authenticated service object")
        self._service = service
        self._query = query
        self._page_size = page_size

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        # Skeleton: real implementation would call self._service.users().messages().list(...)
        # and translate each message into SourceDocument.
        raise NotImplementedError(
            "GmailConnector._fetch_page must be implemented against your Google client"
        )


class SlackConnector(BaseConnector):
    """Pulls messages and threads from Slack channels."""

    name = "slack"
    system = SourceSystem.SLACK

    def __init__(self, *, web_client: Any, channels: list[str]) -> None:
        super().__init__()
        self._client = web_client
        self._channels = channels

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("SlackConnector._fetch_page is integration-specific")


class NotionConnector(BaseConnector):
    """Pulls pages and databases from Notion."""

    name = "notion"
    system = SourceSystem.NOTION

    def __init__(self, *, client: Any, database_ids: list[str] | None = None) -> None:
        super().__init__()
        self._client = client
        self._database_ids = database_ids or []

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("NotionConnector._fetch_page is integration-specific")


class ConfluenceConnector(BaseConnector):
    name = "confluence"
    system = SourceSystem.CONFLUENCE

    def __init__(self, *, client: Any, space_keys: list[str]) -> None:
        super().__init__()
        self._client = client
        self._space_keys = space_keys

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("ConfluenceConnector._fetch_page is integration-specific")


class GoogleDriveConnector(BaseConnector):
    name = "gdrive"
    system = SourceSystem.GDRIVE

    def __init__(self, *, service: Any, folder_ids: list[str]) -> None:
        super().__init__()
        self._service = service
        self._folder_ids = folder_ids

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("GoogleDriveConnector._fetch_page is integration-specific")


class JiraConnector(BaseConnector):
    name = "jira"
    system = SourceSystem.JIRA

    def __init__(self, *, client: Any, jql: str = "") -> None:
        super().__init__()
        self._client = client
        self._jql = jql

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("JiraConnector._fetch_page is integration-specific")


class CRMConnector(BaseConnector):
    """Generic CRM connector. Expects a callable that returns raw records."""

    name = "crm"
    system = SourceSystem.CRM

    def __init__(self, *, fetcher: Any) -> None:
        super().__init__()
        self._fetcher = fetcher

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("CRMConnector._fetch_page is integration-specific")


class TranscriptConnector(BaseConnector):
    """Ingests call transcripts from a directory or a meeting platform."""

    name = "transcripts"
    system = SourceSystem.TRANSCRIPT

    def __init__(self, *, source: Any) -> None:
        super().__init__()
        self._source = source

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("TranscriptConnector._fetch_page is integration-specific")


class DatabaseConnector(BaseConnector):
    """Reads rows from a SQL source. Caller supplies an async query callable."""

    name = "database"
    system = SourceSystem.DATABASE

    def __init__(self, *, query_fn: Any, rows_to_doc: Any) -> None:
        super().__init__()
        self._query_fn = query_fn
        self._rows_to_doc = rows_to_doc

    async def _fetch_page(
        self, *, cursor: str | None, since: datetime | None
    ) -> tuple[list[SourceDocument], str | None]:  # pragma: no cover - integration
        raise NotImplementedError("DatabaseConnector._fetch_page is integration-specific")


def make_source_doc(
    *,
    system: SourceSystem,
    external_id: str,
    content: str,
    title: str | None = None,
    uri: str | None = None,
    permissions: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> SourceDocument:
    """Helper for connector authors to construct a SourceDocument tersely."""
    return SourceDocument(
        ref=SourceRef(
            system=system,
            external_id=external_id,
            uri=uri,
            permissions=permissions,
        ),
        title=title,
        content=content,
        metadata=metadata or {},
    )


__all__ = [
    "CRMConnector",
    "ConfluenceConnector",
    "DatabaseConnector",
    "GmailConnector",
    "GoogleDriveConnector",
    "JiraConnector",
    "NotionConnector",
    "SlackConnector",
    "TranscriptConnector",
    "make_source_doc",
]
