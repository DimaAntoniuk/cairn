"""Tests for the in-memory reference stores."""

from __future__ import annotations

import pytest

from cairn.errors import StoreError
from cairn.schemas import (
    Artifact,
    ArtifactType,
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
)
from cairn.store import (
    HashEmbedder,
    InMemoryArtifactStore,
    InMemoryGraphStore,
    InMemoryVectorStore,
)

# ------------------------------------------------------------------ graph ---


async def test_graph_upsert_and_find_by_alias() -> None:
    store = InMemoryGraphStore()
    e = Entity(entity_type=EntityType.ORGANIZATION, name="Acme", aliases=["Acme Inc"])
    await store.upsert_entity(e)
    found = await store.find_entities(name="acme inc", entity_type=EntityType.ORGANIZATION)
    assert len(found) == 1
    assert found[0].id == e.id


async def test_graph_neighbors_multi_hop() -> None:
    store = InMemoryGraphStore()
    a = Entity(entity_type=EntityType.PROJECT, name="A")
    b = Entity(entity_type=EntityType.PROJECT, name="B")
    c = Entity(entity_type=EntityType.PROJECT, name="C")
    for ent in (a, b, c):
        await store.upsert_entity(ent)
    await store.upsert_relationship(
        Relationship(
            source_entity_id=a.id,
            target_entity_id=b.id,
            relationship_type=RelationshipType.DEPENDS_ON,
        )
    )
    await store.upsert_relationship(
        Relationship(
            source_entity_id=b.id,
            target_entity_id=c.id,
            relationship_type=RelationshipType.DEPENDS_ON,
        )
    )
    one_hop = {n.id for n in await store.neighbors(a.id, depth=1)}
    two_hop = {n.id for n in await store.neighbors(a.id, depth=2)}
    assert one_hop == {b.id}
    assert two_hop == {b.id, c.id}


async def test_graph_relationship_to_unknown_entity_errors() -> None:
    store = InMemoryGraphStore()
    a = Entity(entity_type=EntityType.PROJECT, name="A")
    await store.upsert_entity(a)
    with pytest.raises(StoreError):
        await store.upsert_relationship(
            Relationship(
                source_entity_id=a.id,
                target_entity_id="missing",
                relationship_type=RelationshipType.RELATED_TO,
            )
        )


async def test_graph_relationships_direction_filter() -> None:
    store = InMemoryGraphStore()
    a = Entity(entity_type=EntityType.PROJECT, name="A")
    b = Entity(entity_type=EntityType.PROJECT, name="B")
    await store.upsert_entity(a)
    await store.upsert_entity(b)
    await store.upsert_relationship(
        Relationship(
            source_entity_id=a.id,
            target_entity_id=b.id,
            relationship_type=RelationshipType.OWNS,
        )
    )
    out = await store.relationships_of(a.id, direction="out")
    inbound = await store.relationships_of(a.id, direction="in")
    assert len(out) == 1 and len(inbound) == 0


# ----------------------------------------------------------------- vector ---


async def test_vector_search_returns_self_first() -> None:
    embedder = HashEmbedder(dim=64)
    store = InMemoryVectorStore()
    texts = {"a": "Acme paused outbound", "b": "weather report", "c": "outbound paused Acme"}
    for k, v in texts.items():
        vec = await embedder.embed(v)
        await store.upsert(id=k, vector=vec, text=v)

    qvec = await embedder.embed("Acme paused outbound")
    results = await store.search(vector=qvec, top_k=3)
    assert results[0][0] == "a"
    # 'c' shares all tokens with 'a', so it should be near 1.0 too
    assert results[1][0] == "c"


# --------------------------------------------------------------- artifact ---


async def test_artifact_supersede_chains_versions() -> None:
    store = InMemoryArtifactStore()
    v1 = Artifact(artifact_type=ArtifactType.GENERIC, title="t", summary="v1")
    await store.put(v1)
    v2 = Artifact(artifact_type=ArtifactType.GENERIC, title="t", summary="v2")
    bumped = await store.supersede(v1.artifact_id, v2)
    assert bumped.version == 2
    refetched_old = await store.get(v1.artifact_id)
    assert refetched_old is not None
    assert refetched_old.superseded_by == bumped.artifact_id


async def test_artifact_list_filters() -> None:
    store = InMemoryArtifactStore()
    a = Artifact(
        artifact_type=ArtifactType.PRICING_POLICY,
        title="P",
        summary="",
        entity_refs=["e1"],
    )
    b = Artifact(
        artifact_type=ArtifactType.RISK_ASSESSMENT,
        title="R",
        summary="",
        entity_refs=["e1", "e2"],
    )
    await store.put(a)
    await store.put(b)
    only_p = await store.list(artifact_type=ArtifactType.PRICING_POLICY)
    assert {x.artifact_id for x in only_p} == {a.artifact_id}
    only_e2 = await store.list(entity_ref="e2")
    assert {x.artifact_id for x in only_e2} == {b.artifact_id}
