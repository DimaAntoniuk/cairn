from cairn import KnowledgeLayer
from cairn.domain import ArtifactType
from cairn.infra.llm import MockLLM
from cairn.ingestion import ManualConnector


async def test_layer_full_pipeline(mock_llm: MockLLM) -> None:
    layer = KnowledgeLayer(llm=mock_llm)
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


async def test_layer_query_returns_relevant_context(mock_llm: MockLLM) -> None:
    layer = KnowledgeLayer(llm=mock_llm)
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
