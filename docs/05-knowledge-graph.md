# Knowledge Graph

The `GraphBuilder` turns extracted facts into a queryable knowledge graph with resolved entities and typed relationships. Entity resolution ensures that "Acme Corp", "Acme Corporation", and "Acme" all map to the same entity.

---

## Graph Model

```mermaid
erDiagram
    Entity {
        string id PK "ent_*"
        string name "canonical name"
        EntityType entity_type "person, org, product..."
        list aliases "alternative names"
        dict attributes "key-value properties"
        float confidence "0.0 - 1.0"
        datetime created_at
        datetime updated_at
    }

    Relationship {
        string id PK "rel_*"
        string source_entity_id FK
        string target_entity_id FK
        RelationshipType relationship_type
        dict attributes
        float confidence
        datetime valid_from
        datetime valid_until
    }

    SourceRef {
        string system "slack, confluence..."
        string external_id
        string uri
        tuple permissions
    }

    Entity ||--o{ Relationship : "source"
    Entity ||--o{ Relationship : "target"
    Entity ||--o{ SourceRef : "provenance"
    Relationship ||--o{ SourceRef : "provenance"
```

---

## Entity Resolution

When new entities are extracted, the `GraphBuilder` resolves them against existing entities before creating new nodes:

```mermaid
flowchart TD
    NEW[New extracted entity] --> FIND{Find by name/type<br/>or alias match?}
    FIND -->|Match found| MERGE[Merge into existing entity]
    FIND -->|No match| CREATE[Create new entity]

    MERGE --> UPSERT[Upsert to GraphStore]
    CREATE --> UPSERT

    MERGE --> DETAILS["merge() combines:<br/>• union of aliases<br/>• union of source_refs<br/>• merge attributes (new wins)<br/>• keep newer updated_at<br/>• average confidence"]

    style NEW fill:#F5A623,color:#333
    style UPSERT fill:#7BC67E,color:#333
```

### Merge Rules

```python
entity_a.merge(entity_b)
```

| Field | Strategy |
|-------|----------|
| `aliases` | Union of both alias sets |
| `attributes` | Shallow merge, `entity_b` values win on conflict |
| `source_refs` | Union (deduplicated) |
| `confidence` | Averaged |
| `updated_at` | Most recent |
| `entity_type` | Must match — `TypeError` if different |

---

## Graph Example

After ingesting documents about a product launch:

```mermaid
graph LR
    A["Alice Chen<br/><small>person</small>"] -->|approved_by| D
    PT["Platform Team<br/><small>organization</small>"] -->|owns| ATH["Athena<br/><small>product</small>"]
    PM["Project Mercury<br/><small>project</small>"] -->|part_of| ATH
    DRP["Data Residency Policy<br/><small>policy</small>"] -->|applies_to| PM
    SOC["SOC-2 Audit<br/><small>event</small>"] -->|applies_to| ATH
    A -->|authored_by| DRP
    D["Launch Decision<br/><small>decision</small>"] -->|blocks| PM

    style PT fill:#4A90D9,color:#fff
    style ATH fill:#7BC67E,color:#333
    style PM fill:#7BC67E,color:#333
    style DRP fill:#E8D44D,color:#333
    style SOC fill:#F5A623,color:#333
    style A fill:#D94A4A,color:#fff
    style D fill:#D94A4A,color:#fff
```

---

## Graph Traversal

The `IGraphStore` interface supports depth-limited neighborhood expansion:

```python
# Find an entity by name
entities = await graph_store.find_entities(name="Athena")
athena = entities[0]

# Get 1-hop neighbors
neighbors = await graph_store.neighbors(athena.id, depth=1)
# → [Platform Team, Project Mercury, SOC-2 Audit]

# Get 2-hop neighbors (includes neighbors-of-neighbors)
neighbors_2 = await graph_store.neighbors(athena.id, depth=2)
# → [Platform Team, Project Mercury, SOC-2 Audit, Data Residency Policy, Alice Chen, ...]

# Get relationships with direction filtering
rels = await graph_store.relationships_of(athena.id, direction="incoming")
# → [Relationship(source=Platform Team, type=owns)]

rels = await graph_store.relationships_of(athena.id, direction="outgoing")
# → [] (Athena has no outgoing edges in this example)

rels = await graph_store.relationships_of(athena.id, direction="both")
# → all relationships where Athena is source or target
```

---

## How Graph Powers Retrieval

During query time, entity hints trigger graph-based retrieval that complements vector search:

```mermaid
flowchart LR
    Q["query(entity_hints=['Athena'])"] --> FIND[Find Entity 'Athena']
    FIND --> SEED["Seed entity:<br/>Athena (product)"]
    SEED --> EXPAND["neighbors(depth=1)"]
    EXPAND --> N1["Platform Team"]
    EXPAND --> N2["Project Mercury"]
    EXPAND --> N3["SOC-2 Audit"]

    SEED --> FETCH_S["Artifacts for Athena"]
    N1 --> FETCH_1["Artifacts for Platform Team"]
    N2 --> FETCH_2["Artifacts for Mercury"]
    N3 --> FETCH_3["Artifacts for SOC-2"]

    FETCH_S --> RESULTS["Retrieval Results<br/>(score boost: 0.4 for seed, 0.2 for neighbors)"]
    FETCH_1 --> RESULTS
    FETCH_2 --> RESULTS
    FETCH_3 --> RESULTS

    style Q fill:#4A90D9,color:#fff
    style RESULTS fill:#7BC67E,color:#333
```

This means a query about "Athena" automatically surfaces knowledge about related entities — even if the query text doesn't mention them directly.

---

## Graph Store Interface

```python
class IGraphStore(Protocol):
    async def upsert_entity(self, entity: Entity) -> Entity: ...
    async def get_entity(self, entity_id: str) -> Entity | None: ...
    async def find_entities(
        self, *, name: str | None = None, entity_type: EntityType | None = None
    ) -> list[Entity]: ...
    async def upsert_relationship(self, rel: Relationship) -> Relationship: ...
    async def neighbors(
        self,
        entity_id: str,
        *,
        relationship_types: Sequence[RelationshipType] | None = None,
        depth: int = 1,
    ) -> list[Entity]: ...
    async def relationships_of(
        self, entity_id: str, *, direction: str = "both"
    ) -> list[Relationship]: ...
```

The built-in `InMemoryGraphStore` implements this with dict-based storage. For production, implement this protocol against Neo4j, Neptune, or any graph database.
