"""Tests for the evaluation loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cairn.evaluation import EvaluationLoop, IssueKind
from cairn.schemas import Artifact, ArtifactType, Confidence, SourceRef, SourceSystem
from cairn.store import InMemoryArtifactStore


async def test_eval_detects_stale_artifact() -> None:
    store = InMemoryArtifactStore()
    fresh = Artifact(artifact_type=ArtifactType.GENERIC, title="fresh", summary="")
    stale = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="stale",
        summary="",
        updated_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    await store.put(fresh)
    await store.put(stale)
    loop = EvaluationLoop(artifact_store=store, stale_after_days=30)
    issues = await loop.run(check_contradictions=False)
    kinds = {i.kind for i in issues if stale.artifact_id in i.artifact_ids}
    assert IssueKind.STALE in kinds


async def test_eval_detects_low_confidence() -> None:
    store = InMemoryArtifactStore()
    weak = Artifact(
        artifact_type=ArtifactType.GENERIC,
        title="weak",
        summary="",
        confidence=Confidence(score=0.1),
        source_refs=[SourceRef(system=SourceSystem.MANUAL, external_id="a")],
    )
    await store.put(weak)
    loop = EvaluationLoop(artifact_store=store, low_confidence_threshold=0.5)
    issues = await loop.run(check_contradictions=False)
    assert any(i.kind == IssueKind.LOW_CONFIDENCE for i in issues)


async def test_eval_detects_unreferenced() -> None:
    store = InMemoryArtifactStore()
    homeless = Artifact(artifact_type=ArtifactType.GENERIC, title="orphan", summary="")
    await store.put(homeless)
    loop = EvaluationLoop(artifact_store=store)
    issues = await loop.run(check_contradictions=False)
    assert any(i.kind == IssueKind.UNREFERENCED for i in issues)
