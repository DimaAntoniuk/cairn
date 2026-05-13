# Cairn — Knowledge Layer Framework

> **Extract, structure, and retrieve organizational knowledge from unstructured sources using LLMs.**

Cairn is a Python framework that turns scattered documents — Slack threads, Confluence pages, emails, CRM notes — into a structured knowledge graph with versioned artifacts, semantic search, and auto-generated wiki pages. It's designed to power AI copilots, internal search, and decision-support tools.

---

## What Cairn Does

```
Raw Documents  ──▶  Structured Knowledge  ──▶  Intelligent Retrieval
    │                      │                         │
  Slack               Entity Graph              Context Assembly
  Confluence          Relationships             (token-budgeted,
  Email               Versioned Artifacts        ranked, compressed)
  CRM Notes           Source Provenance
```

**In one sentence:** Cairn reads your messy organizational data, extracts who/what/why with LLMs, builds a knowledge graph, and gives you back precisely the context you need — within a token budget — when you ask a question.

---

## Documentation

| # | Section | What You'll Learn |
|---|---------|-------------------|
| 1 | [Architecture](01-architecture.md) | System design, hexagonal architecture, component overview |
| 2 | [Data Flow](02-data-flow.md) | End-to-end sequence diagrams for ingest → process → query |
| 3 | [Ingestion](03-ingestion.md) | Connectors, source systems, document buffering |
| 4 | [Extraction](04-extraction.md) | 3-pass LLM extraction: entities, relationships, claims |
| 5 | [Knowledge Graph](05-knowledge-graph.md) | Entity resolution, relationships, graph traversal |
| 6 | [Artifacts](06-artifacts.md) | Compilation, versioning, confidence scoring |
| 7 | [Retrieval & Context](07-retrieval-and-context.md) | Vector + graph search, priority ranking, token budgeting |
| 8 | [Evaluation](08-evaluation.md) | Quality assurance: staleness, contradictions, confidence |
| 9 | [Wiki Generation](09-wiki-generation.md) | Auto-generated entity wiki pages |
| 10 | [REST API](10-rest-api.md) | HTTP endpoints for ingest, query, evaluate, wiki |
| 11 | [Examples](11-examples.md) | 3 end-to-end examples from simple to production-like |

## Mermaid Diagrams

Standalone diagram files are in the [`diagrams/`](diagrams/) folder — open them in any Mermaid-compatible viewer (GitHub, VS Code with Mermaid extension, mermaid.live).

| Diagram | File |
|---------|------|
| System Architecture | [`diagrams/architecture.mmd`](diagrams/architecture.mmd) |
| Ingest → Process Flow | [`diagrams/ingest-process-flow.mmd`](diagrams/ingest-process-flow.mmd) |
| Query → Context Flow | [`diagrams/query-flow.mmd`](diagrams/query-flow.mmd) |
| Extraction 3-Pass | [`diagrams/extraction-passes.mmd`](diagrams/extraction-passes.mmd) |
| Knowledge Graph Model | [`diagrams/knowledge-graph.mmd`](diagrams/knowledge-graph.mmd) |
| Evaluation Loop | [`diagrams/evaluation-loop.mmd`](diagrams/evaluation-loop.mmd) |
| LLM Tier Routing | [`diagrams/llm-tiers.mmd`](diagrams/llm-tiers.mmd) |
| Domain Model (Class) | [`diagrams/domain-model.mmd`](diagrams/domain-model.mmd) |

---

## Quick Start

```python
import asyncio
from cairn import KnowledgeLayer
from cairn.infra.llm import LlamaIndexLLMAdapter

# Use any LlamaIndex-compatible LLM
from llama_index.llms.anthropic import Anthropic

async def main():
    llm = LlamaIndexLLMAdapter(Anthropic(model="claude-sonnet-4-20250514"))
    layer = KnowledgeLayer(llm=llm)

    # Ingest a document
    await layer.ingest_documents([...])
    result = await layer.process_buffer()

    # Query the knowledge base
    ctx = await layer.query("What decisions were made about pricing?")
    print(ctx.render())

asyncio.run(main())
```

---

## Key Design Decisions

- **Protocol-based LLM abstraction** — no vendor lock-in; swap Claude, GPT, Llama, or any LlamaIndex LLM
- **Structured output via schema forcing** — Pydantic models enforce LLM response shape, not prompt text
- **Hexagonal architecture** — domain logic has zero external dependencies; adapters live in `infra/`
- **Token-budgeted context assembly** — never blow your LLM context window; priority-ranked fragments with optional compression
- **Source provenance on everything** — every artifact traces back to the document and system it came from
- **Permission-aware retrieval** — artifacts inherit source permissions; queries filter by access rights

---

## Requirements

- Python 3.12+
- Core: `pydantic`, `anyio`
- LLM (optional): `llama-index-llms-anthropic` or any `llama-index-core` LLM
- API (optional): `fastapi`, `uvicorn`

```bash
pip install cairn                        # core only
pip install 'cairn[anthropic]'           # + Claude via LlamaIndex
pip install 'cairn[api]'                 # + REST API
pip install 'cairn[all]'                 # everything
```
