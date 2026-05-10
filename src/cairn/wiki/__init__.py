"""Operational wiki generator (Karpathy's LLM-Wiki pattern).

Produces continuously refreshed, human-readable wiki pages from the artifact
store and graph. Pages are themselves stored as `Artifact`s with type
`WIKI_PAGE` so the same versioning, supersede semantics, and source tracking
apply uniformly.

The page structure is intentionally simple Markdown so it can be rendered in
any wiki front-end (Notion mirror, Confluence sync, MkDocs, raw GitHub) or
piped to an agent as context.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ..llm import LLMClient, LLMTask
from ..schemas import Artifact, ArtifactType, Confidence, Entity, SourceRef
from ..store import ArtifactStore, GraphStore, iter_active_artifacts

log = logging.getLogger(__name__)


WIKI_SYSTEM = """You write internal operational wiki pages for an enterprise.
You are given:
  - a topic name and type
  - related artifacts (each with title, summary, and structured content)
  - related entities from the knowledge graph

Produce a Markdown page with these sections, in order:
  ## Overview
  ## Current State
  ## Decisions & Constraints
  ## Risks
  ## Related Entities
  ## Open Questions
  ## Sources

Rules:
- Be concise. Use bullet lists where natural.
- Cite sources by their system + id where you reference specific facts.
- If a section has no content, write "_None recorded._"
- Do not invent information not present in the inputs.

Return ONLY the Markdown text. No JSON, no code fences."""


class WikiGenerator:
    """Produces wiki pages from the artifact store and graph."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        artifact_store: ArtifactStore,
        graph_store: GraphStore,
    ) -> None:
        self._llm = llm
        self._artifacts = artifact_store
        self._graph = graph_store

    async def generate_page_for_entity(self, entity: Entity) -> Artifact:
        """Build (or refresh) a wiki page for one entity."""
        related_artifacts = await self._artifacts.list(entity_ref=entity.id)
        active = iter_active_artifacts(related_artifacts)
        neighbors = await self._graph.neighbors(entity.id, depth=1)

        prompt = self._build_prompt(entity, active, neighbors)
        try:
            markdown = await self._llm.complete(
                task=LLMTask.STANDARD, system=WIKI_SYSTEM, user=prompt, max_tokens=2000
            )
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
        """Refresh wiki pages for every entity referenced by any artifact."""
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

    # ------------------------------------------------------------------------

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
        """Deterministic fallback when the LLM call fails."""
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


def _first_paragraph(markdown: str) -> str:
    chunks = markdown.strip().split("\n\n", 1)
    head = chunks[0] if chunks else ""
    # Strip leading markdown heading hashes and whitespace.
    head = head.lstrip("#").strip()
    return head[:500]


def _avg_confidence(artifacts: list[Artifact]) -> float:
    if not artifacts:
        return 0.0
    return sum(a.confidence.score for a in artifacts) / len(artifacts)


def _dedupe_refs(refs: Iterable[SourceRef]) -> list[SourceRef]:
    seen: dict[tuple[str, str], SourceRef] = {}
    for ref in refs:
        seen.setdefault((ref.system.value, ref.external_id), ref)
    return list(seen.values())


__all__ = ["WikiGenerator"]
