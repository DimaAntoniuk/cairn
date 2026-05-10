from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .shared__utils import _new_id, _utcnow


class SourceSystem(StrEnum):
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    CONFLUENCE = "confluence"
    GDRIVE = "gdrive"
    JIRA = "jira"
    CRM = "crm"
    TRANSCRIPT = "transcript"
    DATABASE = "database"
    MANUAL = "manual"
    OTHER = "other"


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    system: SourceSystem
    external_id: str
    uri: str | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)
    permissions: tuple[str, ...] = Field(default_factory=tuple)


class SourceDocument(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("doc"))
    ref: SourceRef
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "SourceDocument",
    "SourceRef",
    "SourceSystem",
]
