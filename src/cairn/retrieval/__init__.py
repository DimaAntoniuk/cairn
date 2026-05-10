"""Retrieval & query planning.

Moves beyond pure embedding similarity. A `Query` declares what the caller
wants (intent, entity hints, region/industry policy filters, time bounds);
the `RetrievalPlanner` decides which signals to combine:

  * vector search over artifact summaries
  * direct graph lookup by entity name + multi-hop neighborhood expansion
  * policy filtering (artifact permissions, freshness, confidence floor)

Results are ranked into `RetrievalResult`s the context assembler can budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..errors import RetrievalError
from ..schemas import Artifact, ArtifactType, Entity
from ..store import ArtifactStore, Embedder, GraphStore, VectorStore, iter_active_artifacts

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Query:
    """Declarative description of what the agent wants to retrieve."""

    intent: str
    entity_hints: tuple[str, ...] = ()
    artifact_types: tuple[ArtifactType, ...] = ()
    permissions: tuple[str, ...] = ()
    min_confidence: float = 0.0
    max_age_days: int | None = None
    top_k: int = 10
    graph_depth: int = 1


@dataclass
class RetrievalResult:
    """Ranked piece of evidence returned by the planner."""

    artifact: Artifact
    score: float
    reasons: list[str] = field(default_factory=list)


class RetrievalPlanner:
    """Plans and executes retrieval over the knowledge layer."""

    def __init__(
        self,
        *,
        artifact_store: ArtifactStore,
        graph_store: GraphStore,
        vector_store: VectorStore,
        embedder: Embedder,
    ) -> None:
        self._artifacts = artifact_store
        self._graph = graph_store
        self._vectors = vector_store
        self._embedder = embedder

    async def index_artifact(self, artifact: Artifact) -> None:
        """Index an artifact in the vector store. Idempotent."""
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
        """Execute the query plan; return ranked results."""
        candidates: dict[str, RetrievalResult] = {}

        # Signal 1: vector similarity over artifact summaries.
        await self._add_vector_candidates(query, candidates)

        # Signal 2: graph-anchored lookup for hinted entities.
        if query.entity_hints:
            await self._add_graph_candidates(query, candidates)

        # Filter by policy / freshness / confidence / type.
        filtered = [r for r in candidates.values() if self._passes_policy(query, r.artifact)]

        filtered.sort(key=lambda r: r.score, reverse=True)
        return filtered[: query.top_k]

    # ------------------------------------------------------------------------

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

        # Gather seed + multi-hop neighborhood.
        all_entity_ids: set[str] = {e.id for e in seed_entities}
        for seed in seed_entities:
            neighbors = await self._graph.neighbors(seed.id, depth=query.graph_depth)
            all_entity_ids.update(n.id for n in neighbors)

        # Pull artifacts referencing any of those entities; boost their score.
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
            cutoff = datetime.now(timezone.utc) - timedelta(days=query.max_age_days)
            if artifact.updated_at < cutoff:
                return False
        if query.permissions and artifact.permissions:
            allowed = set(query.permissions)
            required = set(artifact.permissions)
            if not required.issubset(allowed):
                return False
        return True

    @staticmethod
    def _embed_text_for(artifact: Artifact) -> str:
        return f"{artifact.title}\n{artifact.summary}"


__all__ = ["Query", "RetrievalPlanner", "RetrievalResult"]
