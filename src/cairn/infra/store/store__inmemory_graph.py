from collections import defaultdict
from collections.abc import Sequence

from cairn.domain import (
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
    StoreError,
)
from cairn.domain.store__ports import IGraphStore


class InMemoryGraphStore(IGraphStore):
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
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
