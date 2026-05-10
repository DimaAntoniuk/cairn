from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .entity__types import Confidence
from .shared__utils import _new_id, _utcnow
from .source__types import SourceRef


class RelationshipType(StrEnum):
    OWNS = "owns"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    PART_OF = "part_of"
    TARGETS = "targets"
    AUTHORED_BY = "authored_by"
    APPROVED_BY = "approved_by"
    APPLIES_TO = "applies_to"
    SUPERSEDES = "supersedes"
    MENTIONS = "mentions"
    RELATED_TO = "related_to"


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("rel"))
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "Relationship",
    "RelationshipType",
]
