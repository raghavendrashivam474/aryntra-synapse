# ARYNTRA SYNAPSE — S20 INTEGRATION GUIDE
## Upstream Integration & Production Operations

- **Sprint:** S20
- **Theme:** Unified Evidence Intelligence / End-to-End Decision Pipeline
- **Target Audience:** Integration Engineers, RAG Developers, Production System Operators

---

## 1. System Positioning

`UnifiedEvidenceEngine` is designed as the definitive post-retrieval intelligence layer in enterprise search and RAG architectures:

```text
[User Query]
     │
     ▼
[Hybrid Retrieval / Vector Search / BM25]
     │
     ▼ (Raw Candidate Pool: 10–50 chunks)
┌─────────────────────────────────────────────────────────┐
│              ARYNTRA SYNAPSE (S20 Engine)               │
│                                                         │
│  - Temporal Enrichment & Intent Filtering               │
│  - Relationship Graph & Supersession Pruning            │
│  - Conflict & Contradiction Resolution                  │
│  - Multi-Signal Sufficiency Control (MSE)               │
│  - Selective Bounded Semantic Adjudication              │
│  - Deterministic Safety Veto Enforcement                │
│  - Decision Archaeology Trace Recording                 │
└────────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
     [SUFFICIENT]                   [UNCERTAIN / INSUFFICIENT]
            │                                 │
            ▼                                 ▼
   [Forward Defensible              [Trigger Clarification /
   Context to LLM Generator]        Escalate / Safe Fallback]
   ```
## 2. Ingestion Data Contract

The engine accepts a query string and a list of dictionary candidates.

### Candidate Schema

| Field Name | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `chunk_id` / `id` | `str` | **Required** | Unique identifier for the chunk. |
| `text` / `content` | `str` | **Required** | Raw text content of the candidate chunk. |
| `relevance_score` / `score` | `float` | Optional | Initial retrieval score `[0.0, 1.0]`. Default: `0.0`. |
| `document_id` | `str` | Optional | Identifier of the parent document (used for S17 graph links). |
| `version` | `str` | Optional | Version identifier (e.g., `"1.0"`, `"2.1.0"`). |
| `effective_date` | `str` | Optional | Date string in ISO format (`"YYYY-MM-DD"` or `"YYYY-MM"`). |
| `superseded` | `bool` | Optional | Explicit flag if document is known to be obsolete. |

### Minimal Python Candidate Example

```python
candidate = {
    "chunk_id": "kb_policy_sec4",
    "text": "Employees are permitted up to $75 for breakfast during official travel.",
    "relevance_score": 0.88,
    "document_id": "travel_handbook_2026",
    "version": "2.4",
    "effective_date": "2026-01-15",
}
```
## 3. Basic Production Integration

Initialize the engine once during application startup (e.g., in a FastAPI lifespan or service container) and reuse the instance across requests:

```python
from typing import List, Dict, Any
from app.evidence import (
    UnifiedEvidenceEngine,
    UnifiedEvidenceConfig,
    UnifiedEvidenceResult,
)


# 1. Initialize engine singleton
engine = UnifiedEvidenceEngine(
    config=UnifiedEvidenceConfig(
        max_candidates=40,
        temporal_enabled=True,
        relationship_enabled=True,
        sufficiency_enabled=True,
        adjudication_enabled=True,
        provenance_enabled=True,
    )
)

def handle_user_query(query: str, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # 2. Execute unified intelligence pipeline
    result: UnifiedEvidenceResult = engine.process(
        query=query,
        candidates=retrieved_docs,
    )
    
    # 3. Route based on authoritative decision
    if result.decision == "SUFFICIENT":
        clean_context = "\n\n".join(
            f"[{c.get('chunk_id')}]: {c.get('text')}"
            for c in result.selected_evidence
        )
        return {
            "status": "ready",
            "context": clean_context,
            "confidence": result.confidence,
            "trace_id": result.provenance.decision_id if result.provenance else None,
        }
    
    elif result.decision == "INSUFFICIENT":
        return {
            "status": "insufficient_evidence",
            "message": "Not enough verified documentation exists to answer this query safely.",
            "trace_id": result.provenance.decision_id if result.provenance else None,
        }
    
    else:  # UNCERTAIN
        return {
            "status": "ambiguous",
            "message": "Conflicting policies or dates were detected.",
            "conflicts": result.conflicts,
            "trace_id": result.provenance.decision_id if result.provenance else None,
        }

```

## 4. Connecting a Live LLM Adjudicator

By default, the engine uses `MockAdjudicator`. To connect real LLMs (OpenAI, Anthropic, Ollama, or vLLM), implement the `LLMProvider` protocol:

```python
import openai
from app.evidence.adjudication import LLMAdjudicator, LLMProvider
from app.evidence import UnifiedEvidenceEngine

class OpenAIProvider(LLMProvider):
    def __init__(self, client: openai.OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def complete(self, prompt: str, timeout: float) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=timeout,
            temperature=0.0,
        )
        return response.choices[0].message.content or "{}"

# Initialize production engine with live LLM adjudicator
client = openai.OpenAI(api_key="sk-...")
provider = OpenAIProvider(client=client, model="gpt-4o-mini")
adjudicator = LLMAdjudicator(provider=provider, timeout=5.0)

engine = UnifiedEvidenceEngine(adjudicator=adjudicator)

```
## 5. Decision Archaeology & Auditing

Every execution produces a serialized `DecisionRecord` that can be stored for compliance, regulatory auditing, and debugging without re-executing computations:

```python
result = engine.process(query="What is the meal allowance?", candidates=candidates)

if result.provenance:
    record = result.provenance
    
    # 1. Plaintext explanation summary
    print(record.explain())
    
    # 2. Stage-by-stage event filtering
    temporal_events = record.temporal_events()
    conflict_events = record.conflict_events()
    veto_events = record.safety_overrides()
    
    # 3. Export to JSON for persistent storage (e.g. S3 / OpenSearch)
    audit_json = record.to_json(indent=2)

```

## 6. Configuration Profiles

| Profile | Configuration Settings | Best Used For |
| :--- | :--- | :--- |
| **Strict Compliance / Safety** | `adjudication_enabled=True`<br>`sufficiency_enabled=True`<br>`max_candidates=30` | Financial / Legal / Medical policies where incorrect answers are catastrophic. |
| **Ultra-Low Latency (<3ms)** | `adjudication_enabled=False`<br>`temporal_enabled=True`<br>`relationship_enabled=True` | High-throughput internal search APIs requiring sub-5ms SLA. |
| **Historical Archive Querying** | `temporal_enabled=True`<br>`relationship_enabled=True`<br>`max_candidates=50` | Investigating version changes and retroactive policy validity over time. |

## 7. Production Operations Checklist

- [x] **Enforce Candidate Limits:** Keep `max_candidates <= 50` to maintain deterministic evaluation latency under 5 ms.
- [x] **Set LLM Adjudication Timeouts:** Ensure adjudicator `timeout_seconds` is configured to $\le 5.0\text{ s}$ so external API latency cannot block retrieval threads.
- [x] **Safe Fallback Handling:** Treat `decision == "UNCERTAIN"` as a first-class branch in your UI/agent to prompt user clarification.
- [x] **Store Decision Archaeology:** Persist `result.provenance.to_json()` alongside generated answers to provide 100% auditability for regulatory compliance.
