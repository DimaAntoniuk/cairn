"""Graph builder.

Lifts batches of `ExtractedFact`s into a `GraphStore`, with simple but
effective entity resolution (case-insensitive name match plus alias overlap).
The builder is idempotent: running it twice on the same facts will produce
the same graph state, with confidence and source_refs accumulated rather than
duplicated.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ..extraction import LLMExtractor
from ..schemas import Entity, ExtractedFact
from ..store import GraphStore

log = logging.getLogger(__name__)


class GraphBuilder:
    """Resolves and persists entities/relationships into a graph store.

    Resolution policy:
      * Two facts refer to the same entity if their canonical names match
        case-insensitively, OR if either's alias list contains the other's
        canonical name (case-insensitive).
      * On match, `Entity.merge` decides which attributes win (most recent
        updated_at) and source_refs/aliases are unioned.
    """

    def __init__(self, store: GraphStore, *, extractor: LLMExtractor) -> None:
        self._store = store
        self._extractor = extractor

    async def absorb(self, facts: Iterable[ExtractedFact]) -> tuple[list[Entity], int]:
        """Persist entity and relationship facts. Returns (entities, n_relationships)."""
        fact_list = list(facts)

        # Step 1: project entity facts and resolve duplicates.
        new_entities = self._extractor.to_entities(fact_list)
        resolved_index = await self._resolve_and_persist_entities(new_entities)

        # Step 2: project relationships using the resolved index.
        relationships = self._extractor.to_relationships(fact_list, resolved_index)
        for rel in relationships:
            await self._store.upsert_relationship(rel)

        return list(resolved_index.values()), len(relationships)

    async def _resolve_and_persist_entities(self, entities: list[Entity]) -> dict[str, Entity]:
        """Resolve duplicates and persist; return name -> stored Entity."""
        index: dict[str, Entity] = {}
        for ent in entities:
            existing = await self._find_existing(ent)
            if existing is None:
                stored = await self._store.upsert_entity(ent)
            else:
                merged = existing.merge(ent.model_copy(update={"id": existing.id}))
                stored = await self._store.upsert_entity(merged)
            # Index by canonical name AND every alias so relationship resolution
            # can find the entity regardless of which surface form is used.
            index[stored.name] = stored
            for alias in stored.aliases:
                index.setdefault(alias, stored)
        return index

    async def _find_existing(self, candidate: Entity) -> Entity | None:
        # Search by canonical name first; fall back to alias-based search.
        matches = await self._store.find_entities(
            name=candidate.name, entity_type=candidate.entity_type
        )
        if matches:
            return matches[0]
        for alias in candidate.aliases:
            matches = await self._store.find_entities(name=alias, entity_type=candidate.entity_type)
            if matches:
                return matches[0]
        return None


__all__ = ["GraphBuilder"]
