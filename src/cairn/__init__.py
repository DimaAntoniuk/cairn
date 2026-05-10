"""cairn — Agent Knowledge Layer.

Persistent semantic memory, compiled operational artifacts, and runtime
context assembly for LLM agents.

Quick start:

    from cairn import KnowledgeLayer
    from cairn.llm import AnthropicClient
    from cairn.ingestion import ManualConnector

    layer = KnowledgeLayer(llm=AnthropicClient())
    await layer.ingest_from([ManualConnector.from_texts(["..."])])
    await layer.process_buffer()
    context = await layer.query("Pricing policy for Acme in EMEA Healthcare")
    prompt = context.render()

See `examples/` for end-to-end usage including a stubbed LLM for testing.
"""

from .errors import (
    CairnError,
    ConfigError,
    ContextBudgetError,
    ExtractionError,
    IngestionError,
    LLMError,
    RetrievalError,
    StoreError,
)
from .layer import KnowledgeLayer, ProcessResult
from .schemas import (
    Artifact,
    ArtifactType,
    AssembledContext,
    Confidence,
    ContextFragment,
    Entity,
    EntityType,
    ExtractedFact,
    PricingPolicyArtifact,
    Relationship,
    RelationshipType,
    SourceDocument,
    SourceRef,
    SourceSystem,
)

__version__ = "0.1.0"

__all__ = [
    "Artifact",
    "ArtifactType",
    "AssembledContext",
    "CairnError",
    "Confidence",
    "ConfigError",
    "ContextBudgetError",
    "ContextFragment",
    "Entity",
    "EntityType",
    "ExtractedFact",
    "ExtractionError",
    "IngestionError",
    "KnowledgeLayer",
    "LLMError",
    "PricingPolicyArtifact",
    "ProcessResult",
    "Relationship",
    "RelationshipType",
    "RetrievalError",
    "SourceDocument",
    "SourceRef",
    "SourceSystem",
    "StoreError",
    "__version__",
]
