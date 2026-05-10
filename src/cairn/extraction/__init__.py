"""Semantic extraction pipeline.

Turns `SourceDocument`s into structured `ExtractedFact`s via a multi-pass LLM
prompt strategy. The default `LLMExtractor` runs three passes per document:

  1. Entity pass        -- who/what is mentioned, with type and aliases
  2. Relationship pass  -- how those entities relate
  3. Attribute pass     -- atomic state/decision/constraint claims

Each pass uses the `STANDARD` model tier by default. Lightweight tagging or
routing tasks can call `LLMExtractor.tag` which uses the `LIGHT` tier.

Every extracted fact carries:
  * the `SourceRef` of its originating document  (provenance)
  * a `Confidence` returned by the model         (downstream prioritization)
  * an optional `quote` field in payload         (citation tracking)

Conflict detection (same entity, contradictory attributes) is handled later
by the artifact compiler; this stage is intentionally additive.
"""

from __future__ import annotations

import logging
from typing import Any

from ..errors import ExtractionError
from ..llm import LLMClient, LLMTask
from ..schemas import (
    Confidence,
    Entity,
    EntityType,
    ExtractedFact,
    Relationship,
    RelationshipType,
    SourceDocument,
)

log = logging.getLogger(__name__)


# Prompts are kept in module-level constants so they can be A/B tested or
# overridden via subclassing without code changes deep inside the extractor.

ENTITY_SYSTEM = """You are an expert information extractor for a B2B operating system.
Identify the entities mentioned in the document.
For each entity return:
  - name (canonical form)
  - entity_type (one of: person, organization, product, project, region,
    industry, campaign, policy, decision, task, event, risk, strategy,
    constraint, signal, summary, generic)
  - aliases (other ways the entity is referred to, may be empty)
  - confidence (float 0..1; rationale optional)
  - quote (short verbatim snippet supporting the extraction; <= 200 chars)
Return JSON: {"entities": [...]}"""

RELATIONSHIP_SYSTEM = """You are an expert relationship extractor.
Given the document and the list of entities already identified,
return relationships between them.
For each relationship return:
  - source (entity name)
  - target (entity name)
  - relationship_type (one of: owns, depends_on, blocks, part_of, targets,
    authored_by, approved_by, applies_to, supersedes, mentions, related_to)
  - confidence (float 0..1)
  - quote (short verbatim snippet supporting the relationship)
Return JSON: {"relationships": [...]}"""

ATTRIBUTE_SYSTEM = """You are an expert state/decision/constraint extractor.
For each operational claim in the document, return:
  - subject (entity name the claim is about)
  - kind (one of: state, decision, constraint, risk, plan, policy)
  - statement (one-sentence factual rendering of the claim)
  - reason (optional cause or justification)
  - confidence (float 0..1)
  - quote (short verbatim snippet supporting the claim)
Return JSON: {"claims": [...]}"""


def _normalize_entity_type(raw: str) -> EntityType:
    try:
        return EntityType(raw.lower())
    except ValueError:
        return EntityType.GENERIC


def _normalize_relationship_type(raw: str) -> RelationshipType:
    try:
        return RelationshipType(raw.lower())
    except ValueError:
        return RelationshipType.RELATED_TO


def _confidence_from(payload: dict[str, Any]) -> Confidence:
    score = float(payload.get("confidence", 0.7))
    score = max(0.0, min(1.0, score))
    rationale = payload.get("confidence_rationale")
    return Confidence(score=score, rationale=rationale)


class LLMExtractor:
    """LLM-driven semantic extraction over `SourceDocument`s."""

    def __init__(self, llm: LLMClient, *, max_chars_per_pass: int = 8000) -> None:
        self._llm = llm
        self._max_chars = max_chars_per_pass

    # ---- public API ---------------------------------------------------------

    async def extract(self, document: SourceDocument) -> list[ExtractedFact]:
        """Run all three passes; return a flat list of facts."""
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
        """Lightweight multi-label tagging using the `LIGHT` model tier."""
        system = (
            "Return a JSON array of zero or more tags from this fixed set:\n"
            f"{tags}\nDo not invent new tags."
        )
        result = await self._llm.complete_json(
            task=LLMTask.LIGHT, system=system, user=text, max_tokens=200
        )
        if not isinstance(result, list):
            return []
        allowed = set(tags)
        return [t for t in result if isinstance(t, str) and t in allowed]

    def to_entities(self, facts: list[ExtractedFact]) -> list[Entity]:
        """Project entity-typed facts into `Entity` objects."""
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
        """Project relationship facts to `Relationship` using a name->Entity index."""
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

    # ---- pass implementations -----------------------------------------------

    async def _extract_entities(self, body: str) -> list[dict[str, Any]]:
        try:
            result = await self._llm.complete_json(
                task=LLMTask.STANDARD, system=ENTITY_SYSTEM, user=body, max_tokens=2000
            )
        except Exception as exc:
            raise ExtractionError(f"entity pass failed: {exc}") from exc
        if not isinstance(result, dict):
            return []
        items = result.get("entities") or []
        return [item for item in items if isinstance(item, dict) and item.get("name")]

    async def _extract_relationships(
        self, body: str, entities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not entities:
            return []
        names = [e["name"] for e in entities]
        prompt = f"Document:\n{body}\n\nEntities:\n{names}"
        try:
            result = await self._llm.complete_json(
                task=LLMTask.STANDARD,
                system=RELATIONSHIP_SYSTEM,
                user=prompt,
                max_tokens=1500,
            )
        except Exception as exc:
            raise ExtractionError(f"relationship pass failed: {exc}") from exc
        if not isinstance(result, dict):
            return []
        items = result.get("relationships") or []
        return [
            r
            for r in items
            if isinstance(r, dict) and r.get("source") in names and r.get("target") in names
        ]

    async def _extract_claims(self, body: str) -> list[dict[str, Any]]:
        try:
            result = await self._llm.complete_json(
                task=LLMTask.STANDARD, system=ATTRIBUTE_SYSTEM, user=body, max_tokens=2000
            )
        except Exception as exc:
            raise ExtractionError(f"attribute pass failed: {exc}") from exc
        if not isinstance(result, dict):
            return []
        items = result.get("claims") or []
        return [c for c in items if isinstance(c, dict) and c.get("subject")]

    # ---- helpers ------------------------------------------------------------

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_chars:
            return text
        # Keep beginning and end; the middle is usually the least information-dense.
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
        # Map kind onto our fact_type literal.
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
