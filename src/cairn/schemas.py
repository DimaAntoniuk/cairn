"""Core domain schemas for the Knowledge Layer.

These Pydantic models form the universal vocabulary spoken by every layer:
ingestion, extraction, graph, artifacts, retrieval, and context assembly.

Schemas are deliberately minimal at the field level and rely on a small set of
enums for typing categorical attributes. Backends (graph DB, vector DB,
relational DB) are responsible for persistence-specific shaping.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Sources & provenance
# ---------------------------------------------------------------------------


class SourceSystem(str, Enum):
    """Origin systems supported by the ingestion layer."""

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
    """Pointer back to the originating piece of content.

    Every extracted entity, relationship, and artifact carries one or more
    SourceRefs so downstream consumers can audit provenance.
    """

    model_config = ConfigDict(frozen=True)

    system: SourceSystem
    external_id: str
    uri: str | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)
    permissions: tuple[str, ...] = Field(default_factory=tuple)


class SourceDocument(BaseModel):
    """Normalized form of an ingested document, ready for extraction."""

    id: str = Field(default_factory=lambda: _new_id("doc"))
    ref: SourceRef
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Semantic primitives
# ---------------------------------------------------------------------------


class EntityType(str, Enum):
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
    """Confidence score with optional rationale.

    Scores are in [0, 1]. Use Confidence(score=...) liberally; the evaluation
    loop relies on this signal to detect stale or weakly-supported knowledge.
    """

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class Entity(BaseModel):
    """A semantically identified thing in the knowledge graph."""

    id: str = Field(default_factory=lambda: _new_id("ent"))
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def merge(self, other: Entity) -> Entity:
        """Return a merged copy combining attributes from another entity.

        Conflict policy: most recent updated_at wins for scalar attributes;
        list-valued attributes are unioned. Source refs always accumulate.
        """
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


class RelationshipType(str, Enum):
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


class ExtractedFact(BaseModel):
    """An atomic claim extracted from a SourceDocument by the extraction pipeline.

    Facts are intermediate: the artifact compiler aggregates many facts into
    structured artifacts, and the graph builder lifts entity/relationship facts
    into the graph layer.
    """

    id: str = Field(default_factory=lambda: _new_id("fact"))
    fact_type: Literal["entity", "relationship", "attribute", "decision", "constraint"]
    payload: dict[str, Any]
    source_ref: SourceRef
    confidence: Confidence
    extracted_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Operational artifacts
# ---------------------------------------------------------------------------


class ArtifactType(str, Enum):
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
    """A compiled, queryable, versioned operational knowledge object.

    Artifacts are the primary unit consumed by agent runtimes — they are the
    "compiled knowledge" referenced throughout the spec.
    """

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
    """Strongly-typed example artifact (matches the spec).

    Stored inside `Artifact.content` as a dict; this class is provided so
    callers can validate/compose pricing policies with full type safety before
    serializing into the generic Artifact envelope.
    """

    region: str
    industry: str
    status: str
    constraints: list[str]
    updated_at: datetime = Field(default_factory=_utcnow)
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Runtime context
# ---------------------------------------------------------------------------


class ContextFragment(BaseModel):
    """A single piece of evidence that can be assembled into runtime context.

    Fragments are the atomic unit the Context Assembly Engine reasons about
    when budgeting tokens. They carry a token estimate, priority, and the
    confidence inherited from their source artifact or fact.
    """

    id: str = Field(default_factory=lambda: _new_id("frag"))
    text: str
    token_estimate: int
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    source_refs: list[SourceRef] = Field(default_factory=list)
    artifact_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list)


class AssembledContext(BaseModel):
    """Final cognition context delivered to an agent runtime."""

    fragments: list[ContextFragment]
    total_tokens: int
    dropped_fragment_ids: list[str] = Field(default_factory=list)
    assembled_at: datetime = Field(default_factory=_utcnow)

    def render(self, separator: str = "\n\n---\n\n") -> str:
        """Render the fragments as a single string ready to pass to an LLM."""
        return separator.join(f.text for f in self.fragments)


__all__ = [
    "Artifact",
    "ArtifactType",
    "AssembledContext",
    "Confidence",
    "ContextFragment",
    "Entity",
    "EntityType",
    "ExtractedFact",
    "PricingPolicyArtifact",
    "Relationship",
    "RelationshipType",
    "SourceDocument",
    "SourceRef",
    "SourceSystem",
]
