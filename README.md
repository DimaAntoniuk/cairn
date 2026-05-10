# cairn

**Agent Knowledge Layer** — persistent semantic memory, compiled operational artifacts, and runtime context assembly for LLM agents.

`cairn` sits between raw enterprise data sources (Gmail, Slack, Notion, Confluence, Jira, CRMs, transcripts, databases) and the agents that consume them. It transforms fragmented information into structured, queryable, version-tracked operational knowledge — and then assembles a token-budgeted runtime context for each agent call.

> Inspired by the Pinecone Nexus architecture and Karpathy's LLM-Wiki pattern.

---

## Why not just RAG?

Naive vector retrieval returns chunks that are semantically similar to a query. That is rarely what an agent actually needs. Agents need:

- **Operational structure** — "what is the current state of X" rather than "five paragraphs that mention X"
- **Entity awareness** — knowing that Acme Corp, Acme Corporation, and ACME are the same thing
- **Relationship reasoning** — "what depends on this decision" requires graph traversal, not cosine similarity
- **Provenance** — every claim must be traceable back to a source document
- **Freshness & confidence** — stale or weakly supported facts must be filtered or flagged
- **Token budgeting** — runtime context has hard limits; prioritization matters

`cairn` provides all of this as a composable Python library.

---

## Architecture

```
Enterprise Sources
        │
        ▼
   Ingestion ──▶ Semantic Extraction (Haiku/Sonnet)
                     │
              ┌──────┴───────┐
              ▼              ▼
        Entity & Rel       Artifact Compiler (Sonnet)
        Graph                      │
              │                    ▼
              │              Operational Wiki (Sonnet)
              │                    │
              ▼                    ▼
        ┌────────────────────────────────┐
        │       Knowledge Store          │
        │  (graph + vector + artifact)   │
        └─────────────┬──────────────────┘
                      ▼
        Retrieval Planner ──▶ Context Assembler ──▶ Agent Runtime
                      ▲                                  │
                      └──── Evaluation Loop (Opus) ◀─────┘
```

Each box is a real Python class with a documented interface. Backends (graph DB, vector DB, relational DB) are defined as `Protocol`s — the package ships in-memory reference implementations so it works out of the box and is fully testable; production users plug in Neo4j, Qdrant, Postgres, etc. via optional extras.

---

## Install

```bash
pip install cairn                       # core only, in-memory backends
pip install 'cairn[anthropic]'          # production LLM client
pip install 'cairn[neo4j,qdrant,postgres,nats]'  # production backends
pip install 'cairn[api]'                # FastAPI surface
pip install 'cairn[llamaindex]'         # LlamaIndex retriever bridge
pip install 'cairn[all]'                # everything
```

Requires Python 3.10+.

---

## Quick start

```python
import asyncio
from cairn import KnowledgeLayer
from cairn.llm import AnthropicClient
from cairn.ingestion import ManualConnector
from cairn.schemas import ArtifactType

async def main():
    layer = KnowledgeLayer(llm=AnthropicClient())

    docs = [
        "We should pause healthcare outbound in Germany until legal "
        "approves updated compliance messaging.",
    ]
    await layer.ingest_from([ManualConnector.from_texts(docs)])
    await layer.process_buffer(artifact_type=ArtifactType.CAMPAIGN_STATE)

    ctx = await layer.query(
        "What is the current state of Germany healthcare outbound?",
        entity_hints=["Germany"],
        token_budget=2000,
    )
    print(ctx.render())

asyncio.run(main())
```

Run without an API key by substituting `StubLLMClient` from `cairn.llm` — see `examples/end_to_end.py`.

---

## Public API surface

| Module | What's there |
|---|---|
| `cairn` | `KnowledgeLayer`, all schemas, all errors |
| `cairn.schemas` | `Entity`, `Relationship`, `ExtractedFact`, `Artifact`, `ContextFragment`, `AssembledContext` |
| `cairn.llm` | `LLMClient` protocol, `AnthropicClient`, `StubLLMClient`, `LLMTask` (Haiku/Sonnet/Opus router) |
| `cairn.ingestion` | `Connector` protocol, `BaseConnector`, `ManualConnector`, `IngestionOrchestrator`, connector scaffolds for Gmail/Slack/Notion/Confluence/GDrive/Jira/CRM/Transcripts/Databases |
| `cairn.extraction` | `LLMExtractor` (3-pass: entities → relationships → claims) |
| `cairn.graph` | `GraphBuilder` (entity resolution + relationship persistence) |
| `cairn.artifacts` | `ArtifactCompiler` (with conflict detection) |
| `cairn.wiki` | `WikiGenerator` (auto-refresh hierarchical wiki pages) |
| `cairn.store` | `GraphStore`, `VectorStore`, `ArtifactStore`, `Embedder` protocols + in-memory reference implementations |
| `cairn.retrieval` | `RetrievalPlanner`, `Query`, `RetrievalResult` |
| `cairn.context` | `ContextAssembler`, `AssemblyWeights`, `LLMCompressor` |
| `cairn.evaluation` | `EvaluationLoop`, `EvalIssue`, `IssueKind` (stale / low-confidence / contradictions / unreferenced) |
| `cairn.api` | `build_app(layer)` — FastAPI surface |
| `cairn.llamaindex_bridge` | `build_retriever(layer)` — LlamaIndex `BaseRetriever` |

---

## Design principles

1. **Protocols over inheritance.** Every backend (graph, vector, artifact, embedder, LLM) is a `Protocol`. Tests use in-memory reference implementations; production swaps in real backends via extras. There is no abstract base class hierarchy to navigate.

2. **Pydantic everywhere.** Every public data structure is a Pydantic v2 model. Validation is enforced at boundaries; downstream code can rely on shape.

3. **Provenance is mandatory.** Every `Entity`, `Relationship`, and `Artifact` carries `source_refs`. The artifact compiler refuses to fabricate facts; conflicts are surfaced rather than papered over.

4. **Confidence is a first-class signal.** It propagates from extraction → artifacts → retrieval ranking → assembly priority → evaluation surface. Low-confidence claims don't silently win.

5. **Async-first.** Built on `anyio`/`asyncio`. The orchestrator runs connectors concurrently; the FastAPI surface and LlamaIndex bridge slot in naturally.

6. **Model routing is centralized.** `LLMTask.LIGHT/STANDARD/HEAVY` maps to Haiku/Sonnet/Opus in one place (`DEFAULT_MODEL_MAP`). Upgrade model versions without touching pipeline code.

7. **Token budgets are real.** The `ContextAssembler` deduplicates, prioritizes, optionally compresses (LLM-backed), and reports what it dropped. Nothing silently overflows.

---

## Phased adoption

The library maps directly onto the phased rollout in the original spec:

| Phase | What you turn on |
|---|---|
| 1 — Operational Wiki MVP | `KnowledgeLayer` + `ManualConnector` + `WikiGenerator` |
| 2 — Structured Artifacts | Add `ArtifactCompiler` for typed artifact production |
| 3 — Graph Cognition | Configure `entity_hints` + `graph_depth` in queries |
| 4 — Context Assembly | Tune `AssemblyWeights`, add `LLMCompressor` |
| 5 — Autonomous Optimization | Schedule `EvaluationLoop.run()` and act on `EvalIssue`s |

---

## Development

```bash
git clone https://github.com/cairn/cairn
cd cairn
pip install -e '.[dev]'
pytest                        # full suite, no API keys required
ruff check src tests
mypy src
```

The full test suite runs entirely against `StubLLMClient` and the in-memory stores, so CI requires no secrets.

---

## Status

Beta — APIs may evolve before 1.0. Production users should pin to a minor version.

## License

Apache 2.0
