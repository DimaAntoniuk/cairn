"""Artifact compiler.

Aggregates `ExtractedFact`s about a subject (an entity, region, campaign,
etc.) into a structured, versioned `Artifact`. The compiler is responsible
for:

  * grouping facts by subject/scope
  * detecting contradictory claims and flagging them in `content`
  * delegating final summarization/structuring to the LLM (Sonnet tier)
  * producing a stable `Artifact` envelope with full provenance

The compiler is opinionated about one thing: an artifact is valuable only if
it is *queryable*. Every artifact therefore carries:
  * `artifact_type` for filtering
  * `entity_refs` for graph-aware lookup
  * `source_refs` for audit
  * a `summary` (one-paragraph) and a `content` dict (structured)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterable

from ..errors import ExtractionError
from ..llm import LLMClient, LLMTask
from ..schemas import (
    Artifact,
    ArtifactType,
    Confidence,
    Entity,
    ExtractedFact,
    SourceRef,
)

log = logging.getLogger(__name__)


COMPILER_SYSTEM = """You are a knowledge artifact compiler.
Given a subject and a list of facts (each with a statement, kind, source, and
confidence), produce a structured operational artifact.

Return JSON with this exact shape:
{
  "title": "<short title>",
  "summary": "<one-paragraph executive summary>",
  "content": {
    "current_state": "...",
    "decisions": [...],
    "constraints": [...],
    "risks": [...],
    "open_questions": [...]
  },
  "confidence": <float 0..1>,
  "conflicts": [
    {"description": "...", "fact_ids": ["...", "..."]}
  ]
}

Rules:
- Be faithful to the facts. Do not invent claims.
- If two facts contradict, list them in 'conflicts' rather than picking one.
- Confidence should reflect both the agreement and the source quality of the inputs."""


class ArtifactCompiler:
    """Compile facts into operational artifacts."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def compile_for_entity(
        self,
        entity: Entity,
        facts: Iterable[ExtractedFact],
        *,
        artifact_type: ArtifactType,
    ) -> Artifact:
        fact_list = [f for f in facts if self._mentions(f, entity)]
        if not fact_list:
            return self._empty_artifact(entity, artifact_type)

        prompt = self._build_prompt(entity, fact_list)
        try:
            structured = await self._llm.complete_json(
                task=LLMTask.STANDARD,
                system=COMPILER_SYSTEM,
                user=prompt,
                max_tokens=2500,
            )
        except Exception as exc:
            raise ExtractionError(f"artifact compilation failed: {exc}") from exc

        if not isinstance(structured, dict):
            raise ExtractionError(f"compiler returned non-object: {type(structured)}")

        merged_sources = _dedupe_refs(ref for f in fact_list for ref in [f.source_ref])
        confidence = float(structured.get("confidence", 0.7))
        confidence = max(0.0, min(1.0, confidence))

        return Artifact(
            artifact_type=artifact_type,
            title=structured.get("title") or entity.name,
            summary=structured.get("summary") or "",
            content={
                **(structured.get("content") or {}),
                "conflicts": structured.get("conflicts") or [],
            },
            entity_refs=[entity.id],
            source_refs=merged_sources,
            confidence=Confidence(score=confidence),
        )

    async def compile_grouped(
        self,
        facts: Iterable[ExtractedFact],
        *,
        entity_index: dict[str, Entity],
        artifact_type: ArtifactType,
    ) -> list[Artifact]:
        """Group facts by their subject entity, then compile one artifact each."""
        grouped: dict[str, list[ExtractedFact]] = defaultdict(list)
        for f in facts:
            subject = self._subject_of(f)
            if subject and subject in entity_index:
                grouped[subject].append(f)

        artifacts: list[Artifact] = []
        for subject, subject_facts in grouped.items():
            entity = entity_index[subject]
            artifact = await self.compile_for_entity(
                entity, subject_facts, artifact_type=artifact_type
            )
            artifacts.append(artifact)
        return artifacts

    # ------------------------------------------------------------------------

    @staticmethod
    def _mentions(fact: ExtractedFact, entity: Entity) -> bool:
        names = {entity.name.lower(), *(a.lower() for a in entity.aliases)}
        if fact.fact_type == "entity":
            return (fact.payload.get("name") or "").lower() in names
        if fact.fact_type == "relationship":
            src = (fact.payload.get("source") or "").lower()
            tgt = (fact.payload.get("target") or "").lower()
            return src in names or tgt in names
        # attribute / decision / constraint
        return (fact.payload.get("subject") or "").lower() in names

    @staticmethod
    def _subject_of(fact: ExtractedFact) -> str | None:
        if fact.fact_type == "entity":
            return fact.payload.get("name")
        if fact.fact_type == "relationship":
            return fact.payload.get("source")
        return fact.payload.get("subject")

    def _build_prompt(self, entity: Entity, facts: list[ExtractedFact]) -> str:
        rendered = [
            {
                "id": f.id,
                "kind": f.payload.get("kind") or f.fact_type,
                "statement": f.payload.get("statement") or json.dumps(f.payload),
                "quote": f.payload.get("quote"),
                "source": f"{f.source_ref.system.value}:{f.source_ref.external_id}",
                "confidence": f.confidence.score,
            }
            for f in facts
        ]
        return json.dumps(
            {
                "subject": {
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "aliases": entity.aliases,
                },
                "facts": rendered,
            },
            indent=2,
        )

    def _empty_artifact(self, entity: Entity, artifact_type: ArtifactType) -> Artifact:
        return Artifact(
            artifact_type=artifact_type,
            title=entity.name,
            summary=f"No supporting facts found for {entity.name}.",
            content={},
            entity_refs=[entity.id],
            source_refs=[],
            confidence=Confidence(score=0.0, rationale="no facts"),
        )


def _dedupe_refs(refs: Iterable[SourceRef]) -> list[SourceRef]:
    seen: dict[tuple[str, str], SourceRef] = {}
    for ref in refs:
        key = (ref.system.value, ref.external_id)
        seen.setdefault(key, ref)
    return list(seen.values())


__all__ = ["ArtifactCompiler"]
