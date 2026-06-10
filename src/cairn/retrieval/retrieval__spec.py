from datetime import UTC, datetime, timedelta

import pytest

from cairn.domain import Artifact, ArtifactType, Confidence, Entity, EntityType, Query
from cairn.infra.store import (
    HashEmbedder,
    InMemoryArtifactStore,
    InMemoryGraphStore,
    InMemoryVectorStore,
)
from cairn.retrieval import RetrievalPlanner


@pytest.fixture
async def planner() -> RetrievalPlanner:
    return RetrievalPlanner(
        artifact_store=InMemoryArtifactStore(),
        graph_store=InMemoryGraphStore(),
        vector_store=InMemoryVectorStore(),
        embedder=HashEmbedder(dim=128),
    )


async def test_retrieval_filters_by_artifact_type(planner: RetrievalPlanner) -> None:
    a = Artifact(artifact_type=ArtifactType.PRICING_POLICY, title="Pricing", summary="EMEA prices")
    b = Artifact(
        artifact_type=ArtifactType.RISK_ASSESSMENT, title="Risk", summary="EMEA pricing risk"
    )
    await planner._artifacts.put(a)
    await planner._artifacts.put(b)
    await planner.index_artifact(a)
    await planner.index_artifact(b)

    results = await planner.plan(
        Query(intent="EMEA pricing", artifact_types=(ArtifactType.PRICING_POLICY,))
    )
    types = {r.artifact.artifact_type for r in results}
    assert types == {ArtifactType.PRICING_POLICY}


async def test_retrieval_drops_low_confidence(planner: RetrievalPlanner) -> None:
    weak = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="Weak",
        summary="rumor",
        confidence=Confidence(score=0.2),
    )
    strong = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="Strong",
        summary="confirmed",
        confidence=Confidence(score=0.95),
    )
    for art in (weak, strong):
        await planner._artifacts.put(art)
        await planner.index_artifact(art)

    results = await planner.plan(Query(intent="rumor confirmed", min_confidence=0.5))
    titles = {r.artifact.title for r in results}
    assert "Weak" not in titles
    assert "Strong" in titles


async def test_retrieval_freshness_window(planner: RetrievalPlanner) -> None:
    old = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="Old",
        summary="archive material",
        updated_at=datetime.now(UTC) - timedelta(days=120),
    )
    new = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="New",
        summary="archive material",
    )
    for art in (old, new):
        await planner._artifacts.put(art)
        await planner.index_artifact(art)

    results = await planner.plan(Query(intent="archive material", max_age_days=30))
    titles = {r.artifact.title for r in results}
    assert "Old" not in titles
    assert "New" in titles


async def test_retrieval_permission_filter(planner: RetrievalPlanner) -> None:
    public = Artifact(artifact_type=ArtifactType.GENERIC, title="Public", summary="open")
    private = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="Private",
        summary="secret",
        permissions=("legal",),
    )
    for art in (public, private):
        await planner._artifacts.put(art)
        await planner.index_artifact(art)

    no_perms = await planner.plan(Query(intent="open secret", permissions=()))
    assert {r.artifact.title for r in no_perms} == {"Public"}
    with_other = await planner.plan(Query(intent="open secret", permissions=("eng",)))
    assert {r.artifact.title for r in with_other} == {"Public"}
    with_legal = await planner.plan(Query(intent="open secret", permissions=("legal",)))
    assert {r.artifact.title for r in with_legal} == {"Public", "Private"}


async def test_retrieval_graph_boost(planner: RetrievalPlanner) -> None:
    ent = Entity(entity_type=EntityType.ORGANIZATION, name="Acme")
    await planner._graph.upsert_entity(ent)
    art = Artifact(
        artifact_type=ArtifactType.ACCOUNT_INTELLIGENCE,
        title="Acme intel",
        summary="completely unrelated text",
        entity_refs=[ent.id],
    )
    await planner._artifacts.put(art)
    await planner.index_artifact(art)

    results = await planner.plan(
        Query(intent="quarterly forecasts", entity_hints=("Acme",), graph_depth=1)
    )
    assert any(r.artifact.artifact_id == art.artifact_id for r in results)
