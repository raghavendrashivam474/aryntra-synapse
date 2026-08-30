# ARYNTRA SYNAPSE — S19 DECISION PROVENANCE ARCHITECTURAL SPECIFICATION

## 1. Architectural Mission

The goal of S19 is **decision archaeology**: making every evidence reasoning step explainable, traceable, and reproducible from a single, unified, serializable artifact.

```text
       ┌──────────────────────────────────────────────────────────┐
       │                 Pipeline Reasoning Stages                │
       └──────────────────────────────────────────────────────────┘
           │               │              │               │
           ▼               ▼              ▼               ▼
      [S16 Temporal] [S17 Graph]   [S14 Conflict]  [S18 Adjudicate]
           │               │              │               │
           └───────────────┼──────────────┼───────────────┘
                           │ Observational
                           ▼
               ┌───────────────────────┐
               │    DecisionRecorder   │
               └───────────────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │     DecisionRecord    │
               │   (JSON Serializable) │
               └───────────────────────┘
2. Core Data Models
2.1 DecisionStage and DecisionAction Enums
Categorizes the lifecycle stages and causal transitions:

Stages: CANDIDATE_SELECTION, TEMPORAL, RELATIONSHIP, CONFLICT, SUFFICIENCY, EXPANSION, ADJUDICATION, SAFETY, FINALIZATION.
Actions: SELECT, REJECT, SUPERSEDE, FLAG, EXPAND, STOP, ADJUDICATE, VETO, FINALIZE.
2.2 DecisionEvent
Represents an atomic, causal reasoning transition:

Python

@dataclass
class DecisionEvent:
    stage: str
    action: str
    evidence_id: Optional[str] = None
    related_evidence_id: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
2.3 AdjudicationRecord
Preserves S18 semantic adjudication state and deterministic safety overrides:

Python

@dataclass
class AdjudicationRecord:
    invoked: bool = False
    candidates: List[str] = field(default_factory=list)
    decision: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    selected_evidence: List[str] = field(default_factory=list)
    veto_applied: bool = False
    veto_reason: Optional[str] = None
2.4 DecisionRecord
The primary archaeological artifact:

Python

@dataclass
class DecisionRecord:
    decision_id: str
    query: str
    created_at: float
    candidate_ids: List[str]
    selected_ids: List[str]
    rejected_ids: List[str]
    events: List[DecisionEvent]
    adjudication: AdjudicationRecord
    final_status: Optional[str]
    final_confidence: Optional[float]
    final_reason: Optional[str]
    trace_complete: bool
    trace_truncated: bool
3. Archaeology & Replay Interface
The artifact supports full serialization and human-readable narrative generation without re-invoking any upstream computational engines:

Python

# Serialization / Deserialization
json_str = record.to_json()
restored_record = DecisionRecord.from_json(json_str)

# Human narrative generation
narrative = record.explain()
4. Bounds & Safety Protections
Trace Cap (DEFAULT_MAX_EVENTS = 200): Prevents unbounded memory growth in complex iterative expansion loops.
Exception Containment: DecisionRecorder methods wrap internal modifications in try...except blocks, logging warnings on failure while allowing normal evidence processing to continue unimpeded.
Null Object Pattern: NullDecisionRecorder provides a zero-overhead no-op implementation when provenance tracking is disabled.
