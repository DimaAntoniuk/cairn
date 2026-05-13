# Data Flow

This document traces data through Cairn's two primary paths: the **write path** (ingest → process) and the **read path** (query → context assembly).

---

## High-Level Pipeline

```mermaid
graph LR
    A[Source Documents] -->|ingest| B[Document Buffer]
    B -->|process| C[LLM Extraction]
    C -->|3-pass| D[ExtractedFacts]
    D --> E[Graph Builder]
    D --> F[Artifact Compiler]
    E --> G[(Knowledge Graph)]
    F --> H[(Artifact Store)]
    F --> I[(Vector Store)]

    J[User Query] --> K[Retrieval Planner]
    K -->|vector search| I
    K -->|graph walk| G
    K -->|fetch| H
    K --> L[Retrieval Results]
    L --> M[Context Assembler]
    M --> N[AssembledContext]

    style A fill:#F5A623,color:#333
    style J fill:#4A90D9,color:#fff
    style N fill:#7BC67E,color:#333
    style G fill:#E8D44D,color:#333
    style H fill:#E8D44D,color:#333
    style I fill:#E8D44D,color:#333
```

---

## Write Path: Ingest → Process

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant KL as KnowledgeLayer
    participant IO as IngestionOrchestrator
    participant Conn as Connector
    participant Ext as LLMExtractor
    participant LLM as ILLMClient
    participant GB as GraphBuilder
    participant GS as GraphStore
    participant AC as ArtifactCompiler
    participant AS as ArtifactStore
    participant VS as VectorStore

    User->>KL: ingest_from([connectors])
    activate KL
    KL->>IO: run(since)
    activate IO

    loop Each connector (concurrent)
        IO->>Conn: fetch(since)
        Conn-->>IO: AsyncIterator[SourceDocument]
        IO->>KL: sink(doc) → buffer.append()
    end
    IO-->>KL: document_count
    deactivate IO
    KL-->>User: count

    User->>KL: process_buffer()
    activate KL

    rect rgb(240, 248, 255)
        Note over KL,LLM: Extraction Phase
        loop Each buffered document
            KL->>Ext: extract(document)
            activate Ext
            Ext->>LLM: astructured_predict(EntitiesResponse)
            LLM-->>Ext: entities[]
            Ext->>LLM: astructured_predict(RelationshipsResponse)
            LLM-->>Ext: relationships[]
            Ext->>LLM: astructured_predict(ClaimsResponse)
            LLM-->>Ext: claims[]
            Ext-->>KL: ExtractedFact[]
            deactivate Ext
        end
    end

    rect rgb(255, 248, 240)
        Note over KL,GS: Graph Building Phase
        KL->>GB: absorb(all_facts)
        activate GB
        GB->>GS: find_entities(name) — match existing
        GS-->>GB: existing or null
        GB->>GS: upsert_entity(merged)
        GB->>GS: upsert_relationship(rel)
        GB-->>KL: (entities[], rel_count)
        deactivate GB
    end

    rect rgb(240, 255, 240)
        Note over KL,VS: Compilation Phase
        KL->>AC: compile_grouped(facts, entity_index)
        activate AC
        AC->>LLM: astructured_predict(CompiledArtifactResponse)
        LLM-->>AC: artifact data
        AC-->>KL: Artifact[]
        deactivate AC
        loop Each artifact
            KL->>AS: put(artifact)
            KL->>VS: upsert(id, vector, text)
        end
    end

    KL-->>User: ProcessResult
    deactivate KL
```

### Step-by-Step

1. **Ingestion** — Connectors fetch documents from external systems (Slack, Confluence, CRM, etc.) concurrently. Documents are buffered in memory.

2. **Extraction** — Each document runs through 3 LLM passes:
   - **Pass 1: Entities** — people, organizations, products, projects, policies
   - **Pass 2: Relationships** — ownership, dependencies, approvals between entities
   - **Pass 3: Claims** — attributes, decisions, constraints about entities

3. **Graph Building** — Extracted entities are resolved against existing ones (by name or alias). New entities are created; existing ones are merged. Relationships are persisted.

4. **Compilation** — Facts are grouped by subject entity. For each group, an LLM synthesizes a structured artifact with title, summary, content fields, and confidence score.

5. **Indexing** — Each artifact is stored and its text is embedded into the vector store for semantic search.

---

## Read Path: Query → Context

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant KL as KnowledgeLayer
    participant RP as RetrievalPlanner
    participant EB as Embedder
    participant VS as VectorStore
    participant GS as GraphStore
    participant AS as ArtifactStore
    participant CA as ContextAssembler
    participant CP as LLMCompressor

    User->>KL: query(intent, entity_hints, token_budget)
    activate KL

    KL->>RP: plan(Query)
    activate RP

    rect rgb(240, 240, 255)
        Note over RP,VS: Vector Retrieval
        RP->>EB: embed(intent)
        EB-->>RP: vector
        RP->>VS: search(vector, top_k)
        VS-->>RP: [(artifact_id, score, text)]
        RP->>AS: get(artifact_id)
        AS-->>RP: Artifact
    end

    rect rgb(255, 240, 255)
        Note over RP,GS: Graph Retrieval (if entity_hints)
        loop Each entity_hint
            RP->>GS: find_entities(name=hint)
            GS-->>RP: Entity
            RP->>GS: neighbors(entity_id, depth)
            GS-->>RP: neighbor entities
            RP->>AS: list(entity_ref=id)
            AS-->>RP: Artifact[]
        end
    end

    Note over RP: Filter by permissions, confidence, age, type
    Note over RP: Merge scores, sort, take top_k
    RP-->>KL: RetrievalResult[]
    deactivate RP

    KL->>CA: assemble(results, token_budget)
    activate CA
    Note over CA: Render artifacts → ContextFragment[]
    Note over CA: Calculate priority scores
    Note over CA: Deduplicate by SHA1
    Note over CA: Sort by priority descending

    loop Fit fragments to budget
        alt Fits within budget
            Note over CA: Include fragment
        else Doesn't fit, priority >= 0.5
            CA->>CP: compress(text, remaining_tokens)
            CP-->>CA: compressed text
            Note over CA: Include if fits after compression
        else Low priority or no space
            Note over CA: Drop fragment
        end
    end

    CA-->>KL: AssembledContext
    deactivate CA

    KL-->>User: AssembledContext
    deactivate KL
```

### Priority Scoring Formula

Each fragment's priority determines its inclusion order:

```
priority = w_relevance × relevance_score
         + w_confidence × confidence_score
         + w_recency × recency_score
         + w_bias × bias_flag
```

| Weight | Default | Description |
|--------|---------|-------------|
| `w_relevance` | 0.4 | Vector/graph similarity score (0–1) |
| `w_confidence` | 0.3 | Source confidence rating (0–1) |
| `w_recency` | 0.2 | Linear decay over 90-day horizon |
| `w_bias` | 0.1 | Explicit boost for specified artifact IDs |

---

## Data Transformation Summary

```
SourceDocument                    # Raw text from external system
    │
    ▼ (LLMExtractor.extract)
ExtractedFact[]                   # Typed facts with provenance
    │
    ├──▶ (GraphBuilder.absorb)
    │    Entity[]                  # Resolved, merged entities
    │    Relationship[]            # Typed edges between entities
    │
    └──▶ (ArtifactCompiler.compile_grouped)
         Artifact[]               # Synthesized knowledge documents
              │
              ▼ (RetrievalPlanner.plan + ContextAssembler.assemble)
         AssembledContext          # Token-budgeted, ranked context
              │
              ▼ (.render())
         str                      # Ready for LLM prompt injection
```

Each transformation preserves **source provenance** — you can always trace an assembled context fragment back to the original document and external system it came from.
