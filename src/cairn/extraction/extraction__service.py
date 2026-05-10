import logging
from typing import Any

from cairn.domain import (
    Entity,
    ExtractedFact,
    ExtractionError,
    Relationship,
    SourceDocument,
)
from cairn.domain.llm__ports import ILLMClient

from .extraction__prompts import ATTRIBUTE_SYSTEM, ENTITY_SYSTEM, RELATIONSHIP_SYSTEM
from .extraction__types import (
    ClaimsResponse,
    EntitiesResponse,
    RelationshipsResponse,
    TagsResponse,
)
from .extraction__utils import (
    _confidence_from,
    _normalize_entity_type,
    _normalize_relationship_type,
)

log = logging.getLogger(__name__)


class LLMExtractor:
    def __init__(self, llm: ILLMClient, *, max_chars_per_pass: int = 8000) -> None:
        self._llm = llm
        self._max_chars = max_chars_per_pass

    async def extract(self, document: SourceDocument) -> list[ExtractedFact]:
        body = self._truncate(document.content)
        entities_raw = await self._extract_entities(body)
        relationships_raw = await self._extract_relationships(body, entities_raw)
        claims_raw = await self._extract_claims(body)

        facts: list[ExtractedFact] = []
        for ent in entities_raw:
            facts.append(self._fact_from_entity(ent, document))
        for rel in relationships_raw:
            facts.append(self._fact_from_relationship(rel, document))
        for claim in claims_raw:
            facts.append(self._fact_from_claim(claim, document))
        return facts

    async def tag(self, text: str, *, tags: list[str]) -> list[str]:
        prompt = (
            f"Select zero or more tags from this fixed set that apply:\n"
            f"{tags}\nDo not invent new tags.\n\n{text}"
        )
        try:
            result = await self._llm.astructured_predict(
                TagsResponse, prompt, max_tokens=200,
            )
        except Exception:
            return []
        allowed = set(tags)
        return [t for t in result.tags if t in allowed]

    def to_entities(self, facts: list[ExtractedFact]) -> list[Entity]:
        out: list[Entity] = []
        for f in facts:
            if f.fact_type != "entity":
                continue
            p = f.payload
            out.append(
                Entity(
                    entity_type=_normalize_entity_type(p["entity_type"]),
                    name=p["name"],
                    aliases=list(p.get("aliases") or []),
                    attributes=p.get("attributes") or {},
                    source_refs=[f.source_ref],
                    confidence=f.confidence,
                )
            )
        return out

    def to_relationships(
        self, facts: list[ExtractedFact], entity_index: dict[str, Entity]
    ) -> list[Relationship]:
        out: list[Relationship] = []
        for f in facts:
            if f.fact_type != "relationship":
                continue
            p = f.payload
            src = entity_index.get(p["source"])
            tgt = entity_index.get(p["target"])
            if src is None or tgt is None:
                log.debug("dropping relationship; unknown endpoint: %s", p)
                continue
            out.append(
                Relationship(
                    source_entity_id=src.id,
                    target_entity_id=tgt.id,
                    relationship_type=_normalize_relationship_type(p["relationship_type"]),
                    source_refs=[f.source_ref],
                    confidence=f.confidence,
                )
            )
        return out

    async def _extract_entities(self, body: str) -> list[dict[str, Any]]:
        prompt = f"{ENTITY_SYSTEM}\n\nDocument:\n{body}"
        try:
            result = await self._llm.astructured_predict(
                EntitiesResponse, prompt, max_tokens=2000,
            )
        except Exception as exc:
            raise ExtractionError(f"entity pass failed: {exc}") from exc
        return [item.model_dump() for item in result.entities if item.name]

    async def _extract_relationships(
        self, body: str, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not entities:
            return []
        names = [e["name"] for e in entities]
        prompt = f"{RELATIONSHIP_SYSTEM}\n\nDocument:\n{body}\n\nEntities:\n{names}"
        try:
            result = await self._llm.astructured_predict(
                RelationshipsResponse, prompt, max_tokens=1500,
            )
        except Exception as exc:
            raise ExtractionError(f"relationship pass failed: {exc}") from exc
        return [
            r.model_dump()
            for r in result.relationships
            if r.source in names and r.target in names
        ]

    async def _extract_claims(self, body: str) -> list[dict[str, Any]]:
        prompt = f"{ATTRIBUTE_SYSTEM}\n\nDocument:\n{body}"
        try:
            result = await self._llm.astructured_predict(
                ClaimsResponse, prompt, max_tokens=2000,
            )
        except Exception as exc:
            raise ExtractionError(f"attribute pass failed: {exc}") from exc
        return [c.model_dump() for c in result.claims if c.subject]

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_chars:
            return text
        head = self._max_chars // 2
        tail = self._max_chars - head
        return text[:head] + "\n...[truncated]...\n" + text[-tail:]

    def _fact_from_entity(self, payload: dict[str, Any], doc: SourceDocument) -> ExtractedFact:
        return ExtractedFact(
            fact_type="entity",
            payload={
                "name": payload["name"],
                "entity_type": payload.get("entity_type", "generic"),
                "aliases": payload.get("aliases") or [],
                "attributes": payload.get("attributes") or {},
                "quote": payload.get("quote"),
            },
            source_ref=doc.ref,
            confidence=_confidence_from(payload),
        )

    def _fact_from_relationship(
        self, payload: dict[str, Any], doc: SourceDocument
    ) -> ExtractedFact:
        return ExtractedFact(
            fact_type="relationship",
            payload={
                "source": payload["source"],
                "target": payload["target"],
                "relationship_type": payload.get("relationship_type", "related_to"),
                "quote": payload.get("quote"),
            },
            source_ref=doc.ref,
            confidence=_confidence_from(payload),
        )

    def _fact_from_claim(self, payload: dict[str, Any], doc: SourceDocument) -> ExtractedFact:
        kind = payload.get("kind", "attribute")
        if kind == "decision":
            fact_type = "decision"
        elif kind == "constraint":
            fact_type = "constraint"
        else:
            fact_type = "attribute"
        return ExtractedFact(
            fact_type=fact_type,  # type: ignore[arg-type]
            payload={
                "subject": payload["subject"],
                "kind": kind,
                "statement": payload.get("statement", ""),
                "reason": payload.get("reason"),
                "quote": payload.get("quote"),
            },
            source_ref=doc.ref,
            confidence=_confidence_from(payload),
        )


__all__ = ["LLMExtractor"]
