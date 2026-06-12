# cairn

**Agent Knowledge Layer** — persistent semantic memory, compiled operational artifacts, and runtime context assembly for LLM agents.

`cairn` sits between raw enterprise data sources (Gmail, Slack, Notion, Confluence, Jira, CRMs, transcripts, databases) and the agents that consume them. It transforms fragmented information into structured, queryable, version-tracked operational knowledge — and then assembles a token-budgeted runtime context for each agent call.

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
   Ingestion ──▶ Semantic Extraction (3-pass LLM)
                     │
              ┌──────┴───────┐
              ▼              ▼
        Entity & Rel       Artifact Compiler
        Graph                      │
              │                    ▼
              │              Operational Wiki
              │                    │
              ▼                    ▼
        ┌────────────────────────────────┐
        │       Knowledge Store          │
        │  (graph + vector + artifact)   │
        └─────────────┬──────────────────┘
                      ▼
        Retrieval Planner ──▶ Context Assembler ──▶ Agent Runtime
                      ▲                                  │
                      └──── Evaluation Loop ◀────────────┘
```

Each box is a real Python class with a documented interface. Backends (graph DB, vector DB, artifact store) are defined as `Protocol`s — the package ships in-memory reference implementations so it works out of the box; production users plug in Neo4j, Qdrant, Postgres, etc.

---

## Documentation

Comprehensive docs with Mermaid diagrams, sequence flows, and code examples:

| # | Topic | Description |
|---|-------|-------------|
| 1 | [Architecture](docs/01-architecture.md) | Hexagonal design, component overview, LLM tier routing |
| 2 | [Data Flow](docs/02-data-flow.md) | End-to-end sequence diagrams for write and read paths |
| 3 | [Ingestion](docs/03-ingestion.md) | Connectors, source systems, document buffering |
| 4 | [Extraction](docs/04-extraction.md) | 3-pass LLM pipeline: entities, relationships, claims |
| 5 | [Knowledge Graph](docs/05-knowledge-graph.md) | Entity resolution, relationships, graph traversal |
| 6 | [Artifacts](docs/06-artifacts.md) | Compilation, versioning, confidence scoring |
| 7 | [Retrieval & Context](docs/07-retrieval-and-context.md) | Vector + graph search, priority ranking, token budgeting |
| 8 | [Evaluation](docs/08-evaluation.md) | Staleness, contradictions, confidence, provenance checks |
| 9 | [Wiki Generation](docs/09-wiki-generation.md) | Auto-generated entity wiki pages |
| 10 | [REST API](docs/10-rest-api.md) | HTTP endpoints for ingest, query, evaluate, wiki |
| 11 | [Examples](docs/11-examples.md) | 3 end-to-end examples from simple to production-like |

Standalone [Mermaid diagrams](docs/diagrams/) are in `docs/diagrams/` — open in GitHub, VS Code, or [mermaid.live](https://mermaid.live).

---

## Install

```bash
pip install cairn                       # core only, in-memory backends
pip install 'cairn[anthropic]'          # Claude via LlamaIndex adapter
pip install 'cairn[api]'                # FastAPI REST surface
pip install 'cairn[llamaindex]'         # LlamaIndex retriever bridge
pip install 'cairn[all]'               # everything
```

Requires Python 3.12+.

---

## Quick start

```python
import asyncio
from cairn import KnowledgeLayer
from cairn.domain import ArtifactType
from cairn.infra.llm import LlamaIndexLLMAdapter
from cairn.ingestion import ManualConnector

async def main():
    from llama_index.llms.anthropic import Anthropic
    layer = KnowledgeLayer(llm=LlamaIndexLLMAdapter(Anthropic(model="claude-sonnet-4-20250514")))

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

Run without an API key using `MockLLM` — see [`examples/end_to_end.py`](examples/end_to_end.py).

---

## Terminal client (TUI)

A Claude-Code-style terminal UI drives the whole knowledge layer in-process —
ingest, compile, query, browse artifacts/entities, refresh the wiki, and run
evaluation, all from one screen with a live artifacts/entities sidebar.

```bash
pip install 'cairn[tui]'     # adds Textual
cairn-tui                    # or: python -m cairn.tui
cairn-tui --seed             # preload demo data to explore offline
```

It auto-selects the backend: **Anthropic** when `ANTHROPIC_API_KEY` is set,
otherwise the bundled offline `MockLLM` (`--llm mock|anthropic|auto` to force it).

Type a question to query, or use slash commands:

| Command | Action |
|---|---|
| `/ingest <text>` · `/load <path>` | buffer a document |
| `/process --type <type>` | extract & compile buffered docs into artifacts |
| `/query [--flags] <intent>` (or just type) | assemble token-budgeted runtime context |
| `/artifacts` · `/artifact <id>` · `/entities` | browse the knowledge store |
| `/wiki` · `/eval` | refresh wiki pages · run quality checks |
| `/seed` · `/help [command]` · `/clear` · `/quit` | demo data · help · clear · exit |

### Agent-friendly commands

Every command takes `--format rich|plain|json` (JSON is a compact single-line
envelope with a stable `"ok"` key) plus filters and selectors that map straight
onto the layer's query parameters — flags first, free text after:

```text
/artifacts --type pricing_policy --min-conf 0.7 --limit 5 --format json
/artifact --fields title,summary art_3f2a        # id prefix is enough
/entities --type person --name acme --format json
/query --budget 2000 --types pricing_policy --top-k 3 germany risks
/eval --contradictions --min-severity 0.5 --format json
/help --format json                              # full machine-readable command schema
```

`--exec` runs commands without the Textual UI (and without the `tui` extra) —
results print to stdout, the exit code reflects failures:

```bash
cairn-tui --llm mock --seed \
  --exec '/artifacts --format json' \
  --exec '/query --top-k 3 --format json germany risks'
```

The TUI lives in `src/cairn/tui/`, split into `session/` (LLM + `KnowledgeLayer`
wiring), `render/` (Rich formatting), `serialize/` (JSON envelopes), `commands/`
(the router), `app/` (the Textual widget), and `cli/` (entry point) — each with
`__types`/`__consts`/`__service`/`__spec`.

---

## Public API surface

| Module | What's there |
|---|---|
| `cairn` | `KnowledgeLayer`, all domain types, all errors |
| `cairn.domain` | `Entity`, `Relationship`, `ExtractedFact`, `Artifact`, `ContextFragment`, `AssembledContext`, `ChatMessage`, `ChatResponse`, `ILLMClient` |
| `cairn.infra.llm` | `LlamaIndexLLMAdapter`, `MockLLM`, model constants (`DEFAULT_MODEL`, `LIGHT_MODEL`, `HEAVY_MODEL`) |
| `cairn.ingestion` | `IConnector` protocol, `ManualConnector`, `IngestionOrchestrator`, connector scaffolds for Gmail/Slack/Notion/Confluence |
| `cairn.extraction` | `LLMExtractor` (3-pass: entities → relationships → claims) |
| `cairn.graph` | `GraphBuilder` (entity resolution + relationship persistence) |
| `cairn.artifacts` | `ArtifactCompiler` (with conflict detection) |
| `cairn.wiki` | `WikiGenerator` (auto-refresh entity wiki pages) |
| `cairn.infra.store` | `InMemoryGraphStore`, `InMemoryArtifactStore`, `InMemoryVectorStore`, `HashEmbedder` |
| `cairn.retrieval` | `RetrievalPlanner`, `Query`, `RetrievalResult` |
| `cairn.context` | `ContextAssembler`, `AssemblyWeights`, `LLMCompressor` |
| `cairn.evaluation` | `EvaluationLoop`, `EvalIssue`, `IssueKind` |
| `cairn.api` | `build_app(layer)` — FastAPI REST surface |

---

## Design principles

1. **Protocols over inheritance.** Every backend (graph, vector, artifact, embedder, LLM) is a `Protocol`. Tests use in-memory implementations; production swaps in real backends.

2. **Structured output via schema forcing.** All LLM calls that need structured data use `astructured_predict` with Pydantic models — no prompt-based JSON parsing.

3. **Provenance is mandatory.** Every `Entity`, `Relationship`, and `Artifact` carries `source_refs`. The artifact compiler refuses to fabricate facts; conflicts are surfaced.

4. **Confidence is a first-class signal.** It propagates from extraction → artifacts → retrieval ranking → assembly priority → evaluation. Low-confidence claims don't silently win.

5. **Async-first.** Built on `anyio`/`asyncio`. The orchestrator runs connectors concurrently; the FastAPI surface slots in naturally.

6. **Tiered model routing.** `KnowledgeLayer(llm=, light_llm=, heavy_llm=)` — configure once at construction. Light for compression, heavy for contradiction detection, default for everything else.

7. **Token budgets are real.** The `ContextAssembler` deduplicates, prioritizes, optionally compresses, and reports what it dropped. Nothing silently overflows.

8. **Permission-aware retrieval.** Artifacts inherit permissions from source documents. Queries filter by the caller's access rights.

---

## Development

```bash
git clone https://github.com/DimaAntoniuk/cairn.git
cd cairn
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest src/cairn/              # full suite, no API keys required
ruff check src/
mypy src/
```

The full test suite runs entirely against `MockLLM` and the in-memory stores — CI requires no secrets.

---

## Status

Beta — APIs may evolve before 1.0. Production users should pin to a minor version.

## License

Apache 2.0
