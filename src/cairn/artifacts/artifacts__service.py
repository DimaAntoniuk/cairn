import json
import logging
from collections import defaultdict
from collections.abc import Iterable

from cairn.domain import (
    Artifact,
    ArtifactType,
    Confidence,
    Entity,
    ExtractedFact,
    ExtractionError,
)
from cairn.domain.llm__ports import ILLMClient

from .artifacts__prompts import COMPILER_SYSTEM
from .artifacts__types import CompiledArtifactResponse
from .artifacts__utils import _dedupe_refs

log = logging.getLogger(__name__)


class ArtifactCompiler:
    def __init__(self, llm: ILLMClient) -> None:
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

        prompt = f"{COMPILER_SYSTEM}\n\n{self._build_prompt(entity, fact_list)}"
        try:
            result = await self._llm.astructured_predict(
                CompiledArtifactResponse, prompt, max_tokens=2500,
            )
        except Exception as exc:
            raise ExtractionError(f"artifact compilation failed: {exc}") from exc

        merged_sources = _dedupe_refs(ref for f in fact_list for ref in [f.source_ref])
        merged_permissions = tuple(sorted({p for s in merged_sources for p in s.permissions}))
        confidence = max(0.0, min(1.0, result.confidence))

        return Artifact(
            artifact_type=artifact_type,
            title=result.title or entity.name,
            summary=result.summary or "",
            content={
                **result.content.model_dump(),
                "conflicts": [c.model_dump() for c in result.conflicts],
            },
            entity_refs=[entity.id],
            source_refs=merged_sources,
            permissions=merged_permissions,
            confidence=Confidence(score=confidence),
        )

    async def compile_grouped(
        self,
        facts: Iterable[ExtractedFact],
        *,
        entity_index: dict[str, Entity],
        artifact_type: ArtifactType,
    ) -> list[Artifact]:
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

    @staticmethod
    def _mentions(fact: ExtractedFact, entity: Entity) -> bool:
        names = {entity.name.lower(), *(a.lower() for a in entity.aliases)}
        if fact.fact_type == "entity":
            return (fact.payload.get("name") or "").lower() in names
        if fact.fact_type == "relationship":
            src = (fact.payload.get("source") or "").lower()
            tgt = (fact.payload.get("target") or "").lower()
            return src in names or tgt in names
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


__all__ = ["ArtifactCompiler"]
