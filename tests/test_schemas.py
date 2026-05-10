"""Tests for core schemas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from cairn.schemas import (
    Artifact,
    ArtifactType,
    Confidence,
    ContextFragment,
    Entity,
    EntityType,
    PricingPolicyArtifact,
    SourceRef,
    SourceSystem,
)


def test_confidence_bounds() -> None:
    Confidence(score=0.0)
    Confidence(score=1.0)
    with pytest.raises(ValidationError):
        Confidence(score=1.5)
    with pytest.raises(ValidationError):
        Confidence(score=-0.1)


def test_entity_merge_unions_aliases_and_sources() -> None:
    older = datetime.now(timezone.utc) - timedelta(days=1)
    newer = datetime.now(timezone.utc)
    a = Entity(
        entity_type=EntityType.ORGANIZATION,
        name="Acme",
        aliases=["Acme Inc"],
        attributes={"region": "EMEA"},
        source_refs=[SourceRef(system=SourceSystem.MANUAL, external_id="1")],
        updated_at=older,
    )
    b = Entity(
        id=a.id,
        entity_type=EntityType.ORGANIZATION,
        name="Acme",
        aliases=["Acme Corporation"],
        attributes={"region": "AMER", "tier": "enterprise"},
        source_refs=[SourceRef(system=SourceSystem.MANUAL, external_id="2")],
        updated_at=newer,
    )
    merged = a.merge(b)
    assert merged.attributes["region"] == "AMER"  # newer wins
    assert merged.attributes["tier"] == "enterprise"
    assert "Acme Inc" in merged.aliases
    assert "Acme Corporation" in merged.aliases
    assert len(merged.source_refs) == 2


def test_entity_merge_rejects_type_mismatch() -> None:
    a = Entity(entity_type=EntityType.ORGANIZATION, name="X")
    b = Entity(entity_type=EntityType.PERSON, name="X")
    with pytest.raises(ValueError):
        a.merge(b)


def test_pricing_policy_artifact_roundtrip() -> None:
    policy = PricingPolicyArtifact(
        region="EMEA",
        industry="Healthcare",
        status="paused",
        constraints=["legal approval pending"],
        sources=["gmail:abc"],
    )
    envelope = Artifact(
        artifact_type=ArtifactType.PRICING_POLICY,
        title="EMEA/Healthcare pricing",
        summary="paused pending legal",
        content=policy.model_dump(mode="json"),
    )
    assert envelope.content["status"] == "paused"
    assert envelope.version == 1


def test_assembled_context_renders() -> None:
    f1 = ContextFragment(text="Alpha", token_estimate=1)
    f2 = ContextFragment(text="Beta", token_estimate=1)
    from cairn.schemas import AssembledContext

    ctx = AssembledContext(fragments=[f1, f2], total_tokens=2)
    rendered = ctx.render()
    assert "Alpha" in rendered and "Beta" in rendered
    assert "---" in rendered
