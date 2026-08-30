# ARYNTRA SYNAPSE — S20 API REFERENCE
## Unified Evidence Intelligence Engine

- **Sprint:** S20
- **Module:** `app.evidence.unified`
- **Public Exports Available in:** `app.evidence`

---

## 1. Quickstart

```python
from app.evidence import (
    UnifiedEvidenceEngine,
    UnifiedEvidenceConfig,
    MockAdjudicator,
)

# 1. Initialize engine
engine = UnifiedEvidenceEngine()

# 2. Prepare candidates
candidates = [
    {
        "chunk_id": "doc_2026_v2",
        "text": "The travel allowance limit is $150 per day as of 2026.",
        "relevance_score": 0.92,
        "version": "2.0",
        "effective_date": "2026-01-01"
    },
    {
        "chunk_id": "doc_2024_v1",
        "text": "The travel allowance limit is $100 per day.",
        "relevance_score": 0.85,
        "version": "1.0",
        "effective_date": "2024-01-01"
    }
]

# 3. Execute unified decision pipeline
result = engine.process(
    query="What is the current travel allowance limit for 2026?",
    candidates=candidates
)

print(f"Decision: {result.decision}")
print(f"Confidence: {result.confidence}")
print(f"Selected: {[c['chunk_id'] for c in result.selected_evidence]}")
print(f"Rejected: {[c['chunk_id'] for c in result.rejected_evidence]}")

2. Classes & Data Structures
UnifiedEvidenceEngine
The central orchestrator for the S14–S19 evidence pipeline.

__init__(config: Optional[UnifiedEvidenceConfig] = None, adjudicator: Optional[EvidenceAdjudicator] = None)
config: Configuration dataclass controlling pipeline behavior. Defaults to UnifiedEvidenceConfig().
adjudicator: Custom implementation of EvidenceAdjudicator (e.g., MockAdjudicator or LLMAdjudicator). Defaults to MockAdjudicator().
process(query: str, candidates: List[Dict[str, Any]]) -> UnifiedEvidenceResult
Executes the full 8-layer unified evidence pipeline.

query: User query string.
candidates: List of raw retrieved candidate dicts (must contain chunk_id/id and text/content).
Returns: Fully populated UnifiedEvidenceResult.
UnifiedEvidenceConfig
Configuration dataclass controlling feature gates and layer parameters.

```PYTHON
@dataclass
class UnifiedEvidenceConfig:
    temporal_enabled: bool = True
    relationship_enabled: bool = True
    sufficiency_enabled: bool = True
    adjudication_enabled: bool = True
    provenance_enabled: bool = True
    max_candidates: int = 50

    s14_config: Optional[S14ResolutionConfig] = None
    s15_config: Optional[S15SufficiencyConfig] = None
    s16_config: Optional[S16TemporalConfig] = None
    s17_config: Optional[S17RelationshipConfig] = None
    adjudication_config: Optional[AdjudicationControllerConfig] = None
```

## Field Descriptions:

temporal_enabled (bool): Enables S16 temporal analysis, query intent extraction, and compatibility scoring. Default True.
relationship_enabled (bool): Enables S17 relationship graph generation (supersession, version chains, same-document links). Default True.
sufficiency_enabled (bool): Enables S15 multi-signal Minimum Sufficient Evidence (MSE) evaluation. Default True.
adjudication_enabled (bool): Enables S18 selective semantic adjudication for ambiguous cases. Default True.
provenance_enabled (bool): Enables S19 decision event recording and archaeological trace generation. Default True.
max_candidates (int): Hard upper bound on candidate chunks ingested per query. Default 50.

## UnifiedEvidenceResult

The unified inspection object returned by engine.process().

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `query` | `str` | The original evaluated query string. |
| `selected_evidence` | `List[Dict[str, Any]]` | List of evidence chunks accepted as defensible and sufficient. |
| `rejected_evidence` | `List[Dict[str, Any]]` | List of evidence chunks excluded (superseded, contradictory, or low relevance). |
| `confidence` | `float` | Overall decision confidence score `[0.0, 1.0]`. |
| `decision` | `str` | Categorical outcome: `"SUFFICIENT"`, `"INSUFFICIENT"`, or `"UNCERTAIN"`. |
| `relationships` | `Dict[str, Any]` | Summary of graph analysis (e.g., `node_count`, `edge_count`). |
| `conflicts` | `Dict[str, Any]` | Summary of contradiction detection (e.g., `detected`, `conflict_score`). |
| `temporal_context` | `Dict[str, Any]` | Temporal signals (e.g., `query_intent`, `target_date`, `enriched_count`). |
| `sufficiency` | `Dict[str, Any]` | State and coverage ratio from the S15 evaluator. |
| `adjudication` | `Dict[str, Any]` | Information regarding LLM consultation (`triggered`, `decision`, `confidence`). |
| `provenance` | `Optional[DecisionRecord]` | Complete decision archaeology artifact containing chronological event logs. |
| `safety` | `Dict[str, Any]` | Safety status flags (e.g., `deterministic_veto`, `veto_reason`). |
| `pipeline_time_ms` | `float` | End-to-end execution wall-clock time in milliseconds. |

## Methods:

to_dict() -> Dict[str, Any]: Serializes the entire result object, including nested provenance traces, into a standard JSON-compatible dictionary.

# 3. Serialization Contract

Calling result.to_dict() outputs the following schema:

```JSON

{
  "query": "What is the policy?",
  "selected_evidence": [
    {
      "chunk_id": "chunk_001",
      "text": "The corporate travel allowance policy limit is $150 per day.",
      "relevance_score": 0.95,
      "document_id": "policy_2026",
      "version": "2.0",
      "effective_date": "2026-01-01",
      "temporal_score": 1.0
    }
  ],
  "rejected_evidence": [
    {
      "chunk_id": "chunk_002",
      "text": "The travel allowance limit is $100 per day.",
      "relevance_score": 0.82,
      "document_id": "policy_2024",
      "version": "1.0",
      "effective_date": "2024-01-01",
      "temporal_score": 0.3
    }
  ],
  "confidence": 0.95,
  "decision": "SUFFICIENT",
  "relationships": {
    "enabled": true,
    "node_count": 2,
    "edge_count": 1
  },
  "conflicts": {
    "detected": false,
    "conflict_score": 0.0,
    "pair_count": 0
  },
  "temporal_context": {
    "enabled": true,
    "query_intent": "latest",
    "target_date": null,
    "enriched_count": 2
  },
  "sufficiency": {
    "state": "sufficient",
    "coverage": 1.0
  },
  "adjudication": {
    "triggered": false
  },
  "provenance": {
    "decision_id": "9f7b0451-24da-4e76-880a-9d95fbc9a1f2",
    "query": "What is the policy?",
    "final_status": "sufficient",
    "final_reason": "unified_pipeline_sufficient",
    "events": [
      {
        "stage": "candidate",
        "action": "consider",
        "reason": "candidate in initial pool",
        "evidence_id": "chunk_001"
      },
      {
        "stage": "temporal",
        "action": "temporal_match",
        "reason": "temporal_score=1.000",
        "evidence_id": "chunk_001"
      },
      {
        "stage": "relationship",
        "action": "supersede",
        "reason": "detected supersedes",
        "evidence_id": "chunk_001"
      },
      {
        "stage": "sufficiency",
        "action": "declare_sufficient",
        "reason": "state=sufficient"
      },
      {
        "stage": "ranking",
        "action": "select",
        "reason": "selected by unified pipeline",
        "evidence_id": "chunk_001"
      },
      {
        "stage": "ranking",
        "action": "reject",
        "reason": "rejected by unified pipeline",
        "evidence_id": "chunk_002"
      }
    ]
  },
  "safety": {
    "deterministic_veto": false,
    "veto_reason": null
  },
  "pipeline_time_ms": 2.5
}
```