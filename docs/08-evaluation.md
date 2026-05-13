# Evaluation

The `EvaluationLoop` runs automated quality checks on the knowledge base, detecting stale knowledge, low-confidence artifacts, missing provenance, and contradictions between artifacts.

---

## Evaluation Overview

```mermaid
flowchart TD
    EV["EvaluationLoop.run()"] --> LIST["Load all active artifacts"]
    LIST --> C1["Check: Staleness"]
    LIST --> C2["Check: Low Confidence"]
    LIST --> C3["Check: Unreferenced"]
    LIST --> C4["Check: Contradictions<br/><small>(optional, uses heavy LLM)</small>"]

    C1 --> ISSUES["EvalIssue[]"]
    C2 --> ISSUES
    C3 --> ISSUES
    C4 --> ISSUES

    ISSUES --> SORT["Sort by severity DESC"]
    SORT --> OUT["Return issues to caller"]

    style EV fill:#4A90D9,color:#fff
    style OUT fill:#7BC67E,color:#333
    style C4 fill:#D94A4A,color:#fff
```

---

## Issue Types

### Staleness

Detects artifacts that haven't been refreshed within a configurable window (default: 30 days).

```
Severity = min(1.0, age_days / (stale_after_days × 4))
```

| Age | stale_after_days=30 | Severity |
|-----|---------------------|----------|
| 30 days | Just stale | 0.25 |
| 60 days | Moderately stale | 0.50 |
| 90 days | Very stale | 0.75 |
| 120+ days | Critical | 1.00 |

```mermaid
graph LR
    A["Artifact<br/>updated: 75 days ago"] --> CHECK{"age > 30 days?"}
    CHECK -->|Yes| ISSUE["STALE<br/>severity: 0.63<br/>'Not refreshed in 75 days'"]

    style ISSUE fill:#F5A623,color:#333
```

### Low Confidence

Flags artifacts with confidence below the threshold (default: 0.4).

```
Severity = 1.0 - confidence_score
```

| Confidence | Severity | Interpretation |
|------------|----------|----------------|
| 0.35 | 0.65 | Likely needs human review |
| 0.20 | 0.80 | Unreliable — may be wrong |
| 0.05 | 0.95 | Almost certainly needs replacement |

### Unreferenced

Detects artifacts with no source provenance — they can't be traced back to any original document.

```
Severity = 0.60 (fixed)
```

These artifacts may have been manually created or their source references lost during processing.

### Contradictions

The most sophisticated check — uses the **heavy LLM** to compare pairs of artifacts that reference the same entity:

```mermaid
sequenceDiagram
    participant EV as EvaluationLoop
    participant LLM as Heavy LLM

    Note over EV: Group artifacts by entity_id
    Note over EV: For each entity with 2+ artifacts

    loop Pairwise comparison
        EV->>LLM: astructured_predict(ContradictionResponse)
        Note right of EV: "Artifact A says X<br/>Artifact B says Y<br/>Do they contradict?"
        LLM-->>EV: {contradicts: true, explanation: "..."}
        Note over EV: Create EvalIssue if contradicts=true
    end
```

```python
class ContradictionResponse(BaseModel):
    contradicts: bool          # Are the artifacts contradictory?
    explanation: str = ""      # What specifically contradicts?
```

Contradiction severity is fixed at **0.85** — contradictions are always high-priority issues.

---

## EvalIssue Model

```python
class EvalIssue(BaseModel):
    kind: IssueKind           # STALE | LOW_CONFIDENCE | UNREFERENCED | CONTRADICTION
    artifact_ids: list[str]   # Which artifacts are affected
    description: str          # Human-readable explanation
    severity: float           # 0.0 (minor) to 1.0 (critical)
    metadata: dict            # Extra context (age_days, entity_id, etc.)
```

---

## Usage

```python
# Quick check (no LLM calls)
issues = await layer.evaluate()

# Full check including contradiction detection (uses heavy_llm)
issues = await layer.evaluate(check_contradictions=True)

# Process results
for issue in issues:
    print(f"[{issue.kind.value}] severity={issue.severity:.2f}")
    print(f"  Artifacts: {issue.artifact_ids}")
    print(f"  {issue.description}")
```

### Example Output

```
[contradiction]     severity=0.85
  Artifacts: ['art_042', 'art_067']
  Artifact A says EU-only storage; Artifact B mentions US-east replication.

[low_confidence]    severity=0.72
  Artifacts: ['art_013']
  Artifact 'Q3 Revenue Estimate' has confidence 0.28 (< 0.40).

[stale]             severity=0.63
  Artifacts: ['art_005']
  Artifact 'EMEA Pricing Policy' has not been refreshed in 75 days.

[unreferenced]      severity=0.60
  Artifacts: ['art_091']
  Artifact 'Manual Notes — Onboarding' has no source provenance.
```

---

## Configuration

```python
EvaluationLoop(
    artifact_store=store,
    llm=heavy_llm,                    # Only needed for contradiction checks
    stale_after_days=30,              # When to flag as stale
    low_confidence_threshold=0.4,     # Below this = flagged
)
```

---

## Evaluation Flow Diagram

```mermaid
graph TD
    START[All Active Artifacts] --> STALE{Updated > 30 days ago?}
    STALE -->|Yes| IS1["🔸 STALE issue"]
    STALE -->|No| OK1[Pass]

    START --> CONF{Confidence < 0.4?}
    CONF -->|Yes| IS2["🔸 LOW_CONFIDENCE issue"]
    CONF -->|No| OK2[Pass]

    START --> REF{source_refs empty?}
    REF -->|Yes| IS3["🔸 UNREFERENCED issue"]
    REF -->|No| OK3[Pass]

    START --> GROUP[Group by entity_id]
    GROUP --> PAIRS["Pairwise comparison<br/>(same entity, same type)"]
    PAIRS --> LLM{"LLM: contradicts?"}
    LLM -->|Yes| IS4["🔴 CONTRADICTION issue"]
    LLM -->|No| OK4[Pass]

    IS1 --> COLLECT[Collect all issues]
    IS2 --> COLLECT
    IS3 --> COLLECT
    IS4 --> COLLECT
    COLLECT --> SORT["Sort by severity DESC"]

    style IS4 fill:#D94A4A,color:#fff
    style IS1 fill:#F5A623,color:#333
    style IS2 fill:#F5A623,color:#333
    style IS3 fill:#F5A623,color:#333
```
