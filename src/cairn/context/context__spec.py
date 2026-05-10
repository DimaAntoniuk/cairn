from cairn.context import AssemblyWeights, ContextAssembler, fragment_from_text
from cairn.domain import Artifact, ArtifactType, Confidence, RetrievalResult


async def test_assembler_respects_token_budget() -> None:
    assembler = ContextAssembler(weights=AssemblyWeights())
    artifacts = [
        Artifact(
            artifact_type=ArtifactType.GENERIC,
            title=f"A{i}",
            summary="x" * 200,
            confidence=Confidence(score=0.9),
        )
        for i in range(5)
    ]
    results = [RetrievalResult(artifact=a, score=0.9) for a in artifacts]
    ctx = await assembler.assemble(results=results, token_budget=120)
    assert ctx.total_tokens <= 120
    assert len(ctx.dropped_fragment_ids) > 0


async def test_assembler_dedupes_identical_text() -> None:
    assembler = ContextAssembler()
    f = fragment_from_text("Same content", priority=0.9)
    g = fragment_from_text("Same content", priority=0.5)
    ctx = await assembler.assemble(results=[], token_budget=1000, extra_fragments=[f, g])
    assert len(ctx.fragments) == 1
    assert ctx.fragments[0].priority == 0.9


async def test_assembler_bias_promotes_artifact() -> None:
    assembler = ContextAssembler()
    a = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="boring",
        summary="weak",
        confidence=Confidence(score=0.3),
    )
    b = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="biased",
        summary="weak too",
        confidence=Confidence(score=0.3),
    )
    results = [RetrievalResult(artifact=a, score=0.5), RetrievalResult(artifact=b, score=0.5)]
    ctx = await assembler.assemble(
        results=results, token_budget=1000, bias_artifact_ids=[b.artifact_id]
    )
    assert ctx.fragments[0].artifact_id == b.artifact_id
