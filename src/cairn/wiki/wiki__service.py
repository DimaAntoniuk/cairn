import logging

from cairn.domain import (
    Artifact,
    ArtifactType,
    Confidence,
    Entity,
    iter_active_artifacts,
)
from cairn.domain.llm__ports import ChatMessage, ILLMClient
from cairn.domain.store__ports import IArtifactStore, IGraphStore

from .wiki__prompts import WIKI_SYSTEM
from .wiki__utils import _avg_confidence, _dedupe_refs, _first_paragraph

log = logging.getLogger(__name__)


class WikiGenerator:
    def __init__(
        self,
        *,
        llm: ILLMClient,
        artifact_store: IArtifactStore,
        graph_store: IGraphStore,
    ) -> None:
        self._llm = llm
        self._artifacts = artifact_store
        self._graph = graph_store

    async def generate_page_for_entity(self, entity: Entity) -> Artifact:
        related_artifacts = await self._artifacts.list(entity_ref=entity.id)
        active = iter_active_artifacts(related_artifacts)
        neighbors = await self._graph.neighbors(entity.id, depth=1)

        prompt = self._build_prompt(entity, active, neighbors)
        try:
            response = await self._llm.achat(
                [
                    ChatMessage(role="system", content=WIKI_SYSTEM),
                    ChatMessage(role="user", content=prompt),
                ],
                max_tokens=2000,
            )
            markdown = response.content
        except Exception as exc:
            log.warning("wiki generation failed for %s: %s", entity.name, exc)
            markdown = self._fallback_markdown(entity, active, neighbors)

        sources = _dedupe_refs(ref for a in active for ref in a.source_refs)
        page = Artifact(
            artifact_type=ArtifactType.WIKI_PAGE,
            title=f"Wiki: {entity.name}",
            summary=_first_paragraph(markdown),
            content={"markdown": markdown.strip()},
            entity_refs=[entity.id],
            source_refs=sources,
            confidence=Confidence(score=_avg_confidence(active)),
        )
        await self._artifacts.put(page)
        return page

    async def refresh_all(self) -> list[Artifact]:
        all_artifacts = await self._artifacts.list()
        seen_entities: set[str] = set()
        for a in all_artifacts:
            seen_entities.update(a.entity_refs)

        pages: list[Artifact] = []
        for ent_id in seen_entities:
            ent = await self._graph.get_entity(ent_id)
            if ent is None:
                continue
            pages.append(await self.generate_page_for_entity(ent))
        return pages

    def _build_prompt(
        self,
        entity: Entity,
        artifacts: list[Artifact],
        neighbors: list[Entity],
    ) -> str:
        artifact_block = (
            "\n\n".join(
                f"### {a.title} ({a.artifact_type.value})\n"
                f"summary: {a.summary}\n"
                f"content: {a.content}\n"
                f"sources: {[f'{r.system.value}:{r.external_id}' for r in a.source_refs]}"
                for a in artifacts
            )
            or "_No artifacts._"
        )

        neighbor_block = (
            "\n".join(f"- {n.name} ({n.entity_type.value})" for n in neighbors)
            or "_No graph neighbors._"
        )

        return (
            f"# Topic: {entity.name} ({entity.entity_type.value})\n\n"
            f"## Artifacts\n{artifact_block}\n\n"
            f"## Graph neighbors\n{neighbor_block}"
        )

    def _fallback_markdown(
        self,
        entity: Entity,
        artifacts: list[Artifact],
        neighbors: list[Entity],
    ) -> str:
        lines = [f"# {entity.name}", "", "## Overview", entity.name, "", "## Current State"]
        if not artifacts:
            lines.append("_None recorded._")
        else:
            for a in artifacts:
                lines.append(f"- **{a.title}**: {a.summary}")
        lines.extend(["", "## Related Entities"])
        if not neighbors:
            lines.append("_None recorded._")
        else:
            for n in neighbors:
                lines.append(f"- {n.name} ({n.entity_type.value})")
        return "\n".join(lines)


__all__ = ["WikiGenerator"]
