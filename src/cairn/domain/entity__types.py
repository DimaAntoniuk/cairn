from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .shared__utils import _new_id, _utcnow
from .source__types import SourceRef


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    PROJECT = "project"
    REGION = "region"
    INDUSTRY = "industry"
    CAMPAIGN = "campaign"
    POLICY = "policy"
    DECISION = "decision"
    TASK = "task"
    EVENT = "event"
    RISK = "risk"
    STRATEGY = "strategy"
    CONSTRAINT = "constraint"
    SIGNAL = "signal"
    SUMMARY = "summary"
    GENERIC = "generic"


class Confidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("ent"))
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def merge(self, other: "Entity") -> "Entity":
        if self.entity_type != other.entity_type:
            raise ValueError("cannot merge entities of different types")
        winner, loser = (self, other) if self.updated_at >= other.updated_at else (other, self)
        merged_attrs = dict(loser.attributes) | dict(winner.attributes)
        merged_aliases = list(dict.fromkeys([*self.aliases, *other.aliases, loser.name]))
        merged_aliases = [a for a in merged_aliases if a != winner.name]
        return winner.model_copy(
            update={
                "aliases": merged_aliases,
                "attributes": merged_attrs,
                "source_refs": [*self.source_refs, *other.source_refs],
                "updated_at": _utcnow(),
            }
        )


__all__ = [
    "Confidence",
    "Entity",
    "EntityType",
]
