import logging
from collections.abc import Iterable

from cairn.domain import Entity, ExtractedFact
from cairn.domain.store__ports import IGraphStore
from cairn.extraction import LLMExtractor

log = logging.getLogger(__name__)


class GraphBuilder:
    def __init__(self, store: IGraphStore, *, extractor: LLMExtractor) -> None:
        self._store = store
        self._extractor = extractor

    async def absorb(self, facts: Iterable[ExtractedFact]) -> tuple[list[Entity], int]:
        fact_list = list(facts)
        new_entities = self._extractor.to_entities(fact_list)
        resolved_index = await self._resolve_and_persist_entities(new_entities)
        relationships = self._extractor.to_relationships(fact_list, resolved_index)
        for rel in relationships:
            await self._store.upsert_relationship(rel)
        return list(resolved_index.values()), len(relationships)

    async def _resolve_and_persist_entities(self, entities: list[Entity]) -> dict[str, Entity]:
        index: dict[str, Entity] = {}
        for ent in entities:
            existing = await self._find_existing(ent)
            if existing is None:
                stored = await self._store.upsert_entity(ent)
            else:
                merged = existing.merge(ent.model_copy(update={"id": existing.id}))
                stored = await self._store.upsert_entity(merged)
            index[stored.name] = stored
            for alias in stored.aliases:
                index.setdefault(alias, stored)
        return index

    async def _find_existing(self, candidate: Entity) -> Entity | None:
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
