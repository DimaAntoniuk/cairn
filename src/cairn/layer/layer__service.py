import logging
from collections.abc import Iterable, Sequence
from datetime import datetime

from cairn.artifacts import ArtifactCompiler
from cairn.context import ContextAssembler, LLMCompressor
from cairn.domain import (
    Artifact,
    ArtifactType,
    AssembledContext,
    ContextFragment,
    Entity,
    EvalIssue,
    ExtractedFact,
    SourceDocument,
)
from cairn.domain.context__ports import ICompressor
from cairn.domain.llm__ports import ILLMClient
from cairn.domain.retrieval__types import Query
from cairn.domain.store__ports import IArtifactStore, IEmbedder, IGraphStore, IVectorStore
from cairn.evaluation import EvaluationLoop
from cairn.extraction import LLMExtractor
from cairn.graph import GraphBuilder
from cairn.infra.store import (
    HashEmbedder,
    InMemoryArtifactStore,
    InMemoryGraphStore,
    InMemoryVectorStore,
)
from cairn.ingestion import IConnector, IngestionOrchestrator
from cairn.retrieval import RetrievalPlanner
from cairn.wiki import WikiGenerator

log = logging.getLogger(__name__)


class KnowledgeLayer:
    def __init__(
        self,
        *,
        llm: ILLMClient,
        light_llm: ILLMClient | None = None,
        heavy_llm: ILLMClient | None = None,
        artifact_store: IArtifactStore | None = None,
        graph_store: IGraphStore | None = None,
        vector_store: IVectorStore | None = None,
        embedder: IEmbedder | None = None,
        compressor: ICompressor | None = None,
    ) -> None:
        _light = light_llm or llm
        _heavy = heavy_llm or llm

        self.llm = llm
        self.artifact_store: IArtifactStore = artifact_store or InMemoryArtifactStore()
        self.graph_store: IGraphStore = graph_store or InMemoryGraphStore()
        self.vector_store: IVectorStore = vector_store or InMemoryVectorStore()
        self.embedder: IEmbedder = embedder or HashEmbedder()

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
        self.assembler = ContextAssembler(
            compressor=compressor or LLMCompressor(_light),
        )
        self.evaluator = EvaluationLoop(artifact_store=self.artifact_store, llm=_heavy)

        self._doc_buffer: list[SourceDocument] = []

    async def ingest_from(
        self,
        connectors: Iterable[IConnector],
        *,
        since: datetime | None = None,
    ) -> int:
        async def sink(doc: SourceDocument) -> None:
            self._doc_buffer.append(doc)

        orchestrator = IngestionOrchestrator(connectors, sink=sink)
        return await orchestrator.run(since=since)

    async def ingest_documents(self, documents: Iterable[SourceDocument]) -> int:
        n = 0
        for doc in documents:
            self._doc_buffer.append(doc)
            n += 1
        return n

    async def process_buffer(
        self,
        *,
        artifact_type: ArtifactType = ArtifactType.ACCOUNT_INTELLIGENCE,
        index_artifacts: bool = True,
    ) -> "ProcessResult":
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
