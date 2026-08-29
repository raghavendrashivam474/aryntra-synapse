# ARYNTRA SYNAPSE — S16 TECHNICAL SPECIFICATION
## Sprint 16: Temporal & Version-Aware Evidence Selection (v1.7.0)

---

## 1. Architectural Mandate & Objectives
Sprint 16 adds deterministic temporal and version-aware criteria to Synapse's evidence pipeline. It addresses a core limitation: standard vector/lexical retrieval models ignore temporal context, treating historical or superseded information as interchangeable with current facts.

### Core Goals
- **Temporal Extraction (RQ1):** Parse date values, month/year expressions, and version hierarchies from document content without LLM or vector calls.
- **Intent Detection (RQ2):** Classify queries into structural temporal intents (`CURRENT`, `HISTORICAL`, `FUTURE`, `TIME_RANGE`, `POINT_IN_TIME`, `UNKNOWN`).
- **Temporal Compatibility (RQ3):** Compute non-destructive compatibility scores between query intents and chunk temporal states.
- **Version & Supersession (RQ4):** Construct version lineages to identify and penalize older, superseded information while boosting current iterations.
- **Safety Bounds (Critical Safety Principle):** Ensure no evidence is deleted or suppressed if temporal metadata is missing or unknown.

---

## 2. Design & API Architecture

```text
                 USER QUERY
                     │
                     ▼
          TemporalAnalyzer.extract_query_intent()
                     │
                     ▼
          Candidate Evidence (Chunks)
                     │
                     ▼
          TemporalAnalyzer.enrich_chunks()
                     │
         [Score combined & re-ranked]
                     │
                     ▼
          EvidenceAssembler.assemble()
                     │
                     ▼
          SufficiencyEvaluator (7 Signals)
                     │
          ConfidenceGuard (8 Signals)
                     │
                     ▼
                 STOP/EXPAND
2.1 Class Interface Definitions
TemporalState (Enum)
Python

class TemporalState(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"
    TIME_BOUNDED = "time_bounded"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"
QueryTemporalIntent (Enum)
Python

class QueryTemporalIntent(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"
    TIME_RANGE = "time_range"
    POINT_IN_TIME = "point_in_time"
    UNKNOWN = "unknown"
TemporalMetadata (Data Class)
Python

@dataclass
class TemporalMetadata:
    timestamp: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    version: Optional[str] = None
    supersedes: Optional[str] = None
    document_id: Optional[str] = None
    published_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    temporal_state: TemporalState = TemporalState.UNKNOWN
    years_mentioned: List[str] = field(default_factory=list)
3. Compatibility Matrix & Multi-Signal Scoring
The system maps extracted intents and states using a calibrated scoring matrix.

Query Intent    Evidence State    Compatibility Score
CURRENT    CURRENT    1.00
CURRENT    HISTORICAL    0.30
CURRENT    FUTURE    0.20
CURRENT    TIME_BOUNDED    0.60
CURRENT    SUPERSEDED    0.10 (Penalized)
HISTORICAL    CURRENT    0.30
HISTORICAL    HISTORICAL    1.00
HISTORICAL    SUPERSEDED    0.40
POINT_IN_TIME    TIME_BOUNDED    0.90 (Evaluated within range bounds)
Combined Scoring Formula
The final scoring blend is computed as follows:
combined_score
=
(
1.0
−
w
temporal
)
×
S
priority
+
w
temporal
×
S
temporal
combined_score=(1.0−w 
temporal
​
 )×S 
priority
​
 +w 
temporal
​
 ×S 
temporal
​
 
Where 
w
temporal
=
0.25
w 
temporal
​
 =0.25 by default, and 
S
priority
S 
priority
​
  is the S12 calibrated priority score.

4. Integration Specifications
4.1 S15 Sufficiency Integration
An additional evaluation signal is registered in the MSE controller:

Signal 7 (Temporal Compatibility): Calculates the average compatibility score of selected chunks.
Scoring Weight: Integrated into the multi-signal weighted combination as config.temporal_weight * s_temporal (with a default of 0.0 for S15 backwards compatibility).
4.2 ConfidenceGuard Integration
Confidence assessment includes a new signal checking temporal coherence:

Signal 8 (Temporal Coherence): Evaluates the average temporal score across ranked chunks. A low average temporal score (
<
0.30
<0.30) triggers a small confidence penalty to prevent routing to un-coherent historical distractors.
