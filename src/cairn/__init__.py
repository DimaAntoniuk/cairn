"""cairn — Agent Knowledge Layer.

Persistent semantic memory, compiled operational artifacts, and runtime
context assembly for LLM agents.

Quick start:

    from cairn import KnowledgeLayer
    from cairn.infra.llm import LlamaIndexLLMAdapter

    layer = KnowledgeLayer(llm=LlamaIndexLLMAdapter(your_llm))
    await layer.ingest_from([ManualConnector.from_texts(["..."])])
    await layer.process_buffer()
    context = await layer.query("Pricing policy for Acme in EMEA Healthcare")
    prompt = context.render()

See ``examples/`` for end-to-end usage including a mock LLM for testing.
"""

from .domain import (
    Artifact,
    ArtifactType,
    AssembledContext,
    CairnError,
    ChatMessage,
    ChatResponse,
    Confidence,
    ConfigError,
    ContextBudgetError,
    ContextFragment,
    Entity,
    EntityType,
    ExtractedFact,
    ExtractionError,
    ILLMClient,
    IngestionError,
    LLMError,
    PricingPolicyArtifact,
    Relationship,
    RelationshipType,
    RetrievalError,
    SourceDocument,
    SourceRef,
    SourceSystem,
    StoreError,
)
from .layer import KnowledgeLayer, ProcessResult

__version__ = "0.1.0"

__all__ = [
    "Artifact",
    "ArtifactType",
    "AssembledContext",
    "CairnError",
    "ChatMessage",
    "ChatResponse",
    "Confidence",
    "ConfigError",
    "ContextBudgetError",
    "ContextFragment",
    "Entity",
    "EntityType",
    "ExtractedFact",
    "ExtractionError",
    "ILLMClient",
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
