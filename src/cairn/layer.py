"""Top-level facade.

`KnowledgeLayer` is the one object most callers need. It composes ingestion,
extraction, graph building, artifact compilation, retrieval, and context
assembly into a single coherent API.

For advanced use cases (custom retrieval planners, custom compressors,
swapping individual stores) the underlying components are still available
directly on the instance.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import datetime

from .artifacts import ArtifactCompiler
from .context import Compressor, ContextAssembler
from .evaluation import EvalIssue, EvaluationLoop
from .extraction import LLMExtractor
from .graph import GraphBuilder
from .ingestion import Connector, IngestionOrchestrator
from .llm import LLMClient
from .retrieval import Query, RetrievalPlanner
from .schemas import (
    Artifact,
    ArtifactType,
    AssembledContext,
    ContextFragment,
    Entity,
    ExtractedFact,
    SourceDocument,
)
from .store import (
    ArtifactStore,
    Embedder,
    GraphStore,
    HashEmbedder,
    InMemoryArtifactStore,
    InMemoryGraphStore,
    InMemoryVectorStore,
    VectorStore,
)
from .wiki import WikiGenerator

log = logging.getLogger(__name__)


class KnowledgeLayer:
    """Composed knowledge layer: ingest -> extract -> graph -> compile -> serve."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        artifact_store: ArtifactStore | None = None,
        graph_store: GraphStore | None = None,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
        compressor: Compressor | None = None,
    ) -> None:
        self.llm = llm
        self.artifact_store: ArtifactStore = artifact_store or InMemoryArtifactStore()
        self.graph_store: GraphStore = graph_store or InMemoryGraphStore()
        self.vector_store: VectorStore = vector_store or InMemoryVectorStore()
        self.embedder: Embedder = embedder or HashEmbedder()

        self.extractor = LLMExtractor(llm)
        self.graph_builder = GraphBuilder(self.graph_store, extractor=self.extractor)
        self.compiler = ArtifactCompiler(llm)
        self.wiki = WikiGenerator(
            llm=llm, artifact_store=self.artifact_store, graph_store=self.graph_store
        )
        self.retrieval = RetrievalPlanner(
            artifact_store=self.artifact_store,
            graph_store=self.graph_store,
            vector_store=self.vector_store,
            embedder=self.embedder,
        )
        self.assembler = ContextAssembler(compressor=compressor)
        self.evaluator = EvaluationLoop(artifact_store=self.artifact_store, llm=llm)

        # Document buffer used by ingest_from(); flushed on demand.
        self._doc_buffer: list[SourceDocument] = []

    # ---- ingestion ----------------------------------------------------------

    async def ingest_from(
        self,
        connectors: Iterable[Connector],
        *,
        since: datetime | None = None,
    ) -> int:
        """Pull from connectors and buffer documents for downstream processing."""

        async def sink(doc: SourceDocument) -> None:
            self._doc_buffer.append(doc)

        orchestrator = IngestionOrchestrator(connectors, sink=sink)
        return await orchestrator.run(since=since)

    async def ingest_documents(self, documents: Iterable[SourceDocument]) -> int:
        """Add already-prepared documents to the ingestion buffer."""
        n = 0
        for doc in documents:
            self._doc_buffer.append(doc)
            n += 1
        return n

    # ---- end-to-end pipeline ------------------------------------------------

    async def process_buffer(
        self,
        *,
        artifact_type: ArtifactType = ArtifactType.ACCOUNT_INTELLIGENCE,
        index_artifacts: bool = True,
    ) -> ProcessResult:
        """Run extract -> graph -> compile -> index over buffered documents.

        Returns a `ProcessResult` summarizing what was created. Calling this
        clears the buffer.
        """
        documents = list(self._doc_buffer)
        self._doc_buffer.clear()
        if not documents:
            return ProcessResult(documents=0, facts=[], entities=[], artifacts=[])

        all_facts: list[ExtractedFact] = []
        for doc in documents:
            try:
                facts = await self.extractor.extract(doc)
            except Exception as exc:
                log.warning("extraction failed for %s: %s", doc.id, exc)
                continue
            all_facts.extend(facts)

        entities, _n_rels = await self.graph_builder.absorb(all_facts)
        entity_index = {e.name: e for e in entities}
        artifacts = await self.compiler.compile_grouped(
            all_facts, entity_index=entity_index, artifact_type=artifact_type
        )
        for artifact in artifacts:
            await self.artifact_store.put(artifact)
            if index_artifacts:
                await self.retrieval.index_artifact(artifact)

        return ProcessResult(
            documents=len(documents),
            facts=all_facts,
            entities=entities,
            artifacts=artifacts,
        )

    # ---- runtime API --------------------------------------------------------

    async def query(
        self,
        intent: str,
        *,
        token_budget: int = 4000,
        entity_hints: Sequence[str] = (),
        artifact_types: Sequence[ArtifactType] = (),
        permissions: Sequence[str] = (),
        min_confidence: float = 0.0,
        max_age_days: int | None = None,
        top_k: int = 10,
        graph_depth: int = 1,
        bias_artifact_ids: Sequence[str] = (),
        extra_fragments: Iterable[ContextFragment] = (),
    ) -> AssembledContext:
        """One-shot retrieval + assembly. The primary runtime entry point."""
        q = Query(
            intent=intent,
            entity_hints=tuple(entity_hints),
            artifact_types=tuple(artifact_types),
            permissions=tuple(permissions),
            min_confidence=min_confidence,
            max_age_days=max_age_days,
            top_k=top_k,
            graph_depth=graph_depth,
        )
        results = await self.retrieval.plan(q)
        return await self.assembler.assemble(
            results=results,
            token_budget=token_budget,
            extra_fragments=extra_fragments,
            bias_artifact_ids=bias_artifact_ids,
        )

    async def refresh_wiki(self) -> list[Artifact]:
        return await self.wiki.refresh_all()

    async def evaluate(self, *, check_contradictions: bool = False) -> list[EvalIssue]:
        return await self.evaluator.run(check_contradictions=check_contradictions)


class ProcessResult:
    """Summary of one `process_buffer()` invocation."""

    __slots__ = ("artifacts", "documents", "entities", "facts")

    def __init__(
        self,
        *,
        documents: int,
        facts: list[ExtractedFact],
        entities: list[Entity],
        artifacts: list[Artifact],
    ) -> None:
        self.documents = documents
        self.facts = facts
        self.entities = entities
        self.artifacts = artifacts

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"ProcessResult(documents={self.documents}, "
            f"facts={len(self.facts)}, entities={len(self.entities)}, "
            f"artifacts={len(self.artifacts)})"
        )


__all__ = ["KnowledgeLayer", "ProcessResult"]
