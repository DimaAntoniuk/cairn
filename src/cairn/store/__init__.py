"""Storage protocols and in-memory reference implementations.

The Knowledge Layer needs three logically distinct storage planes:

  * Graph layer    -- entities, relationships, dependencies
  * Vector layer   -- embeddings for semantic retrieval
  * Artifact layer -- compiled operational artifacts and snapshots

Each plane is defined as a `Protocol`. Concrete adapters live alongside
(`InMemoryGraphStore`, etc.) and exist for two reasons: (1) they make the
package usable out of the box without provisioning Neo4j/Qdrant/Postgres, and
(2) they double as test fixtures with predictable semantics.

Production users are expected to install the relevant extras and supply their
own adapters that satisfy the same protocols.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from ..errors import StoreError
from ..schemas import Artifact, ArtifactType, Entity, EntityType, Relationship, RelationshipType

# ---------------------------------------------------------------------------
# Graph store
# ---------------------------------------------------------------------------


@runtime_checkable
class GraphStore(Protocol):
    """Persistent home of entities and the relationships between them."""

    async def upsert_entity(self, entity: Entity) -> Entity: ...
    async def get_entity(self, entity_id: str) -> Entity | None: ...
    async def find_entities(
        self, *, name: str | None = None, entity_type: EntityType | None = None
    ) -> list[Entity]: ...
    async def upsert_relationship(self, rel: Relationship) -> Relationship: ...
    async def neighbors(
        self,
        entity_id: str,
        *,
        relationship_types: Sequence[RelationshipType] | None = None,
        depth: int = 1,
    ) -> list[Entity]: ...
    async def relationships_of(
        self, entity_id: str, *, direction: str = "both"
    ) -> list[Relationship]: ...


class InMemoryGraphStore:
    """Reference implementation of `GraphStore` backed by Python dicts.

    Multi-hop traversal performs a BFS up to `depth` hops. Entity lookup by
    name is case-insensitive and matches either canonical name or any alias.
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        # Adjacency: entity_id -> set of (other_id, relationship_id, direction)
        self._adjacency: dict[str, set[tuple[str, str, str]]] = defaultdict(set)

    async def upsert_entity(self, entity: Entity) -> Entity:
        existing = self._entities.get(entity.id)
        if existing is not None and existing.entity_type == entity.entity_type:
            merged = existing.merge(entity)
            self._entities[entity.id] = merged
            return merged
        self._entities[entity.id] = entity
        return entity

    async def get_entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    async def find_entities(
        self, *, name: str | None = None, entity_type: EntityType | None = None
    ) -> list[Entity]:
        results: list[Entity] = []
        needle = name.lower() if name else None
        for ent in self._entities.values():
            if entity_type is not None and ent.entity_type != entity_type:
                continue
            if needle is not None:
                pool = [ent.name.lower(), *(a.lower() for a in ent.aliases)]
                if not any(needle in n for n in pool):
                    continue
            results.append(ent)
        return results

    async def upsert_relationship(self, rel: Relationship) -> Relationship:
        if rel.source_entity_id not in self._entities:
            raise StoreError(f"unknown source entity {rel.source_entity_id}")
        if rel.target_entity_id not in self._entities:
            raise StoreError(f"unknown target entity {rel.target_entity_id}")
        self._relationships[rel.id] = rel
        self._adjacency[rel.source_entity_id].add((rel.target_entity_id, rel.id, "out"))
        self._adjacency[rel.target_entity_id].add((rel.source_entity_id, rel.id, "in"))
        return rel

    async def neighbors(
        self,
        entity_id: str,
        *,
        relationship_types: Sequence[RelationshipType] | None = None,
        depth: int = 1,
    ) -> list[Entity]:
        if depth < 1:
            return []
        type_filter = set(relationship_types) if relationship_types else None
        visited: set[str] = {entity_id}
        frontier: set[str] = {entity_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for other_id, rel_id, _direction in self._adjacency.get(node, ()):
                    if type_filter is not None:
                        rel = self._relationships[rel_id]
                        if rel.relationship_type not in type_filter:
                            continue
                    if other_id not in visited:
                        next_frontier.add(other_id)
                        visited.add(other_id)
            frontier = next_frontier
            if not frontier:
                break
        visited.discard(entity_id)
        return [self._entities[i] for i in visited if i in self._entities]

    async def relationships_of(
        self, entity_id: str, *, direction: str = "both"
    ) -> list[Relationship]:
        if direction not in {"both", "in", "out"}:
            raise ValueError("direction must be 'both', 'in', or 'out'")
        out: list[Relationship] = []
        for _other, rel_id, dir_ in self._adjacency.get(entity_id, ()):
            if direction == "both" or direction == dir_:
                out.append(self._relationships[rel_id])
        return out


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------


@runtime_checkable
class Embedder(Protocol):
    """Computes a vector for a piece of text."""

    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic, dependency-free embedder for tests and demos.

    Uses a simple bag-of-tokens hash projection. Not suitable for production
    semantic quality — swap in a real embedder via the `Embedder` protocol.
    """

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for token in text.lower().split():
            h = hash(token) % self.dim
            v[h] += 1.0
        norm = sum(x * x for x in v) ** 0.5
        if norm == 0:
            return v
        return [x / norm for x in v]

    async def embed(self, text: str) -> list[float]:
        return self._vec(text)

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(
        self,
        *,
        id: str,
        vector: list[float],
        text: str,
        metadata: dict[str, object] | None = None,
    ) -> None: ...

    async def search(
        self, *, vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float, str, dict[str, object]]]: ...


class InMemoryVectorStore:
    """Cosine-similarity vector store with no external dependencies."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[list[float], str, dict[str, object]]] = {}

    async def upsert(
        self,
        *,
        id: str,
        vector: list[float],
        text: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._items[id] = (vector, text, metadata or {})

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot: float = sum(x * y for x, y in zip(a, b, strict=False))
        na: float = sum(x * x for x in a) ** 0.5
        nb: float = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return float(dot / (na * nb))

    async def search(
        self, *, vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float, str, dict[str, object]]]:
        scored = [
            (item_id, self._cosine(vector, vec), text, meta)
            for item_id, (vec, text, meta) in self._items.items()
        ]
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Artifact store
# ---------------------------------------------------------------------------


@runtime_checkable
class ArtifactStore(Protocol):
    async def put(self, artifact: Artifact) -> Artifact: ...
    async def get(self, artifact_id: str) -> Artifact | None: ...
    async def list(
        self,
        *,
        artifact_type: ArtifactType | None = None,
        entity_ref: str | None = None,
    ) -> list[Artifact]: ...
    async def supersede(self, old_id: str, new_artifact: Artifact) -> Artifact: ...


class InMemoryArtifactStore:
    """Reference `ArtifactStore` with full version history."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    async def put(self, artifact: Artifact) -> Artifact:
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def list(
        self,
        *,
        artifact_type: ArtifactType | None = None,
        entity_ref: str | None = None,
    ) -> list[Artifact]:
        def keep(a: Artifact) -> bool:
            if artifact_type is not None and a.artifact_type != artifact_type:
                return False
            if entity_ref is not None and entity_ref not in a.entity_refs:  # noqa: SIM103
                return False
            return True

        return [a for a in self._artifacts.values() if keep(a)]

    async def supersede(self, old_id: str, new_artifact: Artifact) -> Artifact:
        old = self._artifacts.get(old_id)
        if old is None:
            raise StoreError(f"cannot supersede unknown artifact {old_id}")
        bumped = new_artifact.model_copy(
            update={
                "version": old.version + 1,
                "superseded_by": None,
            }
        )
        self._artifacts[bumped.artifact_id] = bumped
        self._artifacts[old_id] = old.model_copy(update={"superseded_by": bumped.artifact_id})
        return bumped


def iter_active_artifacts(artifacts: Iterable[Artifact]) -> list[Artifact]:
    """Return only artifacts that have not been superseded."""
    return [a for a in artifacts if a.superseded_by is None]


__all__ = [
    "ArtifactStore",
    "Embedder",
    "GraphStore",
    "HashEmbedder",
    "InMemoryArtifactStore",
    "InMemoryGraphStore",
    "InMemoryVectorStore",
    "VectorStore",
    "iter_active_artifacts",
]
