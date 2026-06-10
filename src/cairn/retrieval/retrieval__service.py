import logging
from datetime import UTC, datetime, timedelta

from cairn.domain import (
    Artifact,
    Entity,
    RetrievalError,
    iter_active_artifacts,
)
from cairn.domain.retrieval__types import Query, RetrievalResult
from cairn.domain.store__ports import IArtifactStore, IEmbedder, IGraphStore, IVectorStore

log = logging.getLogger(__name__)


class RetrievalPlanner:
    def __init__(
        self,
        *,
        artifact_store: IArtifactStore,
        graph_store: IGraphStore,
        vector_store: IVectorStore,
        embedder: IEmbedder,
    ) -> None:
        self._artifacts = artifact_store
        self._graph = graph_store
        self._vectors = vector_store
        self._embedder = embedder

    async def index_artifact(self, artifact: Artifact) -> None:
        text = self._embed_text_for(artifact)
        try:
            vector = await self._embedder.embed(text)
            await self._vectors.upsert(
                id=artifact.artifact_id,
                vector=vector,
                text=text,
                metadata={
                    "artifact_type": artifact.artifact_type.value,
                    "entity_refs": list(artifact.entity_refs),
                    "permissions": list(artifact.permissions),
                    "updated_at": artifact.updated_at.isoformat(),
                    "confidence": artifact.confidence.score,
                },
            )
        except Exception as exc:
            raise RetrievalError(f"failed to index artifact: {exc}") from exc

    async def plan(self, query: Query) -> list[RetrievalResult]:
        candidates: dict[str, RetrievalResult] = {}
        await self._add_vector_candidates(query, candidates)
        if query.entity_hints:
            await self._add_graph_candidates(query, candidates)
        filtered = [r for r in candidates.values() if self._passes_policy(query, r.artifact)]
        filtered.sort(key=lambda r: r.score, reverse=True)
        return filtered[: query.top_k]

    async def _add_vector_candidates(
        self, query: Query, candidates: dict[str, RetrievalResult]
    ) -> None:
        try:
            qvec = await self._embedder.embed(query.intent)
            hits = await self._vectors.search(vector=qvec, top_k=max(query.top_k * 3, 10))
        except Exception as exc:
            log.warning("vector search failed: %s", exc)
            return

        for artifact_id, score, _text, _meta in hits:
            artifact = await self._artifacts.get(artifact_id)
            if artifact is None or artifact.superseded_by is not None:
                continue
            res = candidates.get(artifact_id)
            if res is None:
                candidates[artifact_id] = RetrievalResult(
                    artifact=artifact,
                    score=score,
                    reasons=[f"vector:{score:.3f}"],
                )
            else:
                res.score = max(res.score, score)
                res.reasons.append(f"vector:{score:.3f}")

    async def _add_graph_candidates(
        self, query: Query, candidates: dict[str, RetrievalResult]
    ) -> None:
        seed_entities: list[Entity] = []
        for hint in query.entity_hints:
            seed_entities.extend(await self._graph.find_entities(name=hint))
        if not seed_entities:
            return

        all_entity_ids: set[str] = {e.id for e in seed_entities}
        for seed in seed_entities:
            neighbors = await self._graph.neighbors(seed.id, depth=query.graph_depth)
            all_entity_ids.update(n.id for n in neighbors)

        for ent_id in all_entity_ids:
            artifacts = await self._artifacts.list(entity_ref=ent_id)
            for artifact in iter_active_artifacts(artifacts):
                bonus = 0.4 if ent_id in {e.id for e in seed_entities} else 0.2
                res = candidates.get(artifact.artifact_id)
                if res is None:
                    candidates[artifact.artifact_id] = RetrievalResult(
                        artifact=artifact,
                        score=bonus,
                        reasons=[f"graph:{ent_id}"],
                    )
                else:
                    res.score += bonus
                    res.reasons.append(f"graph:{ent_id}")

    def _passes_policy(self, query: Query, artifact: Artifact) -> bool:
        if query.artifact_types and artifact.artifact_type not in query.artifact_types:
            return False
        if artifact.confidence.score < query.min_confidence:
            return False
        if query.max_age_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=query.max_age_days)
            if artifact.updated_at < cutoff:
                return False
        if artifact.permissions:
            if not query.permissions:
                return False
            allowed = set(query.permissions)
            required = set(artifact.permissions)
            if not required.issubset(allowed):
                return False
        return True

    @staticmethod
    def _embed_text_for(artifact: Artifact) -> str:
        return f"{artifact.title}\n{artifact.summary}"


__all__ = ["RetrievalPlanner"]
