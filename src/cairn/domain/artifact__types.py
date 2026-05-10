from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .entity__types import Confidence
from .shared__utils import _new_id, _utcnow
from .source__types import SourceRef


class ArtifactType(StrEnum):
    CUSTOMER_PROFILE = "customer_profile"
    EXPANSION_STRATEGY = "expansion_strategy"
    CAMPAIGN_STATE = "campaign_state"
    PRICING_POLICY = "pricing_policy"
    ACCOUNT_INTELLIGENCE = "account_intelligence"
    RISK_ASSESSMENT = "risk_assessment"
    EXECUTION_PLAN = "execution_plan"
    ORG_SUMMARY = "org_summary"
    WIKI_PAGE = "wiki_page"
    GENERIC = "generic"


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: _new_id("art"))
    artifact_type: ArtifactType
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    entity_refs: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    permissions: tuple[str, ...] = Field(default_factory=tuple)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    version: int = 1
    superseded_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PricingPolicyArtifact(BaseModel):
    region: str
    industry: str
    status: str
    constraints: list[str]
    updated_at: datetime = Field(default_factory=_utcnow)
    sources: list[str] = Field(default_factory=list)


def iter_active_artifacts(artifacts: Iterable[Artifact]) -> list[Artifact]:
    return [a for a in artifacts if a.superseded_by is None]


__all__ = [
    "Artifact",
    "ArtifactType",
    "PricingPolicyArtifact",
    "iter_active_artifacts",
]
