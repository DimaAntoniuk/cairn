"""End-to-end tests using the StubLLMClient.

These exercise extraction, graph building, artifact compilation, retrieval,
and context assembly without requiring an Anthropic API key.
"""

from __future__ import annotations

import pytest

from cairn import KnowledgeLayer
from cairn.extraction import LLMExtractor
from cairn.graph import GraphBuilder
from cairn.ingestion import ManualConnector
from cairn.llm import LLMTask, StubLLMClient
from cairn.schemas import (
    ArtifactType,
    SourceDocument,
    SourceRef,
    SourceSystem,
)
from cairn.store import InMemoryGraphStore


@pytest.fixture
def germany_doc() -> SourceDocument:
    return SourceDocument(
        ref=SourceRef(system=SourceSystem.MANUAL, external_id="germany-1"),
        title="Germany healthcare update",
        content=(
            "We should pause healthcare outbound in Germany until legal "
            "approves updated compliance messaging."
        ),
    )


@pytest.fixture
def stub_llm() -> StubLLMClient:
    """Stub returning realistic extraction outputs keyed by document content."""
    entities = {
        "entities": [
            {
                "name": "Germany Healthcare Outbound",
                "entity_type": "campaign",
                "aliases": [],
                "confidence": 0.9,
                "quote": "pause healthcare outbound in Germany",
            },
            {
                "name": "Legal",
                "entity_type": "organization",
                "aliases": [],
                "confidence": 0.8,
            },
        ]
    }
    relationships = {
        "relationships": [
            {
                "source": "Germany Healthcare Outbound",
                "target": "Legal",
                "relationship_type": "depends_on",
                "confidence": 0.85,
            }
        ]
    }
    claims = {
        "claims": [
            {
                "subject": "Germany Healthcare Outbound",
                "kind": "decision",
                "statement": "Pause healthcare outbound in Germany pending legal approval.",
                "reason": "compliance messaging not yet approved",
                "confidence": 0.9,
            }
        ]
    }
    artifact = {
        "title": "Germany Healthcare Outbound — Status",
        "summary": "Healthcare outbound in Germany is paused pending legal approval.",
        "content": {
            "current_state": "paused",
            "decisions": ["Pause outbound until legal approval"],
            "constraints": ["compliance messaging not approved"],
            "risks": [],
            "open_questions": [],
        },
        "confidence": 0.88,
        "conflicts": [],
    }
    return StubLLMClient(
        responses={
            (LLMTask.STANDARD, "You are an expert information extractor"): entities,
            (LLMTask.STANDARD, "relationship extractor"): relationships,
            (LLMTask.STANDARD, "state/decision/constraint extractor"): claims,
            (LLMTask.STANDARD, "knowledge artifact compiler"): artifact,
        },
        default_json={},
    )


# ---------------------------------------------------------------- extraction


async def test_extractor_three_passes(stub_llm: StubLLMClient, germany_doc: SourceDocument) -> None:
    extractor = LLMExtractor(stub_llm)
    facts = await extractor.extract(germany_doc)
    kinds = {f.fact_type for f in facts}
    assert "entity" in kinds
    assert "relationship" in kinds
    assert "decision" in kinds
    # Provenance preserved.
    assert all(f.source_ref == germany_doc.ref for f in facts)


# ---------------------------------------------------------------- graph build


async def test_graph_builder_resolves_relationships(
    stub_llm: StubLLMClient, germany_doc: SourceDocument
) -> None:
    extractor = LLMExtractor(stub_llm)
    facts = await extractor.extract(germany_doc)
    store = InMemoryGraphStore()
    builder = GraphBuilder(store, extractor=extractor)
    entities, n_rels = await builder.absorb(facts)
    assert len(entities) == 2
    assert n_rels == 1
    # Relationship should connect the two stored entities.
    by_name = {e.name: e for e in entities}
    rels = await store.relationships_of(by_name["Germany Healthcare Outbound"].id, direction="out")
    assert len(rels) == 1
    assert rels[0].target_entity_id == by_name["Legal"].id


# ----------------------------------------------------------- end-to-end layer


async def test_layer_full_pipeline(stub_llm: StubLLMClient) -> None:
    layer = KnowledgeLayer(llm=stub_llm)
    connector = ManualConnector.from_texts(
        [
            "We should pause healthcare outbound in Germany until legal "
            "approves updated compliance messaging."
        ]
    )
    await layer.ingest_from([connector])
    result = await layer.process_buffer(artifact_type=ArtifactType.CAMPAIGN_STATE)

    assert result.documents == 1
    assert len(result.entities) == 2
    assert len(result.artifacts) >= 1
    assert any("paused" in a.summary.lower() for a in result.artifacts)


async def test_layer_query_returns_relevant_context(stub_llm: StubLLMClient) -> None:
    layer = KnowledgeLayer(llm=stub_llm)
    connector = ManualConnector.from_texts(
        [
            "We should pause healthcare outbound in Germany until legal "
            "approves updated compliance messaging."
        ]
    )
    await layer.ingest_from([connector])
    await layer.process_buffer(artifact_type=ArtifactType.CAMPAIGN_STATE)

    ctx = await layer.query(
        "What is the current state of Germany healthcare outbound?",
        entity_hints=["Germany Healthcare Outbound"],
        token_budget=2000,
    )
    assert len(ctx.fragments) > 0
    rendered = ctx.render()
    assert "paused" in rendered.lower() or "Germany" in rendered
