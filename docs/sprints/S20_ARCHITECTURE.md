# ARYNTRA SYNAPSE — S20 ARCHITECTURE SPECIFICATION
## Unified Evidence Intelligence Pipeline

- **Sprint:** S20
- **Theme:** Unified Evidence Intelligence / End-to-End Decision Pipeline
- **Status:** Complete & Validated (455/455 tests passing)
- **Primary Objective:** Consolidate the discrete intelligence layers developed across S14 through S19 into one coherent, inspectable, and deterministic-first decision engine without modifying their underlying algorithms.

---

## 1. System Overview

Prior to S20, Synapse had developed sophisticated evidence intelligence components sprint-by-sprint:
- **S14:** Conflict-aware assembly, progressive candidate expansion, and contradiction detection.
- **S15:** Multi-signal Minimum Sufficient Evidence (MSE) evaluation.
- **S16:** Temporal intelligence, query intent classification, and target date compatibility.
- **S17:** Deterministic relationship graphs (supersession, version chains, same-document linkage).
- **S18:** Gated semantic adjudication with authoritative deterministic safety vetoes.
- **S19:** Provenance recording and decision archaeology replay.

S20 integrates these standalone components into the **`UnifiedEvidenceEngine`**. Callers provide a query and candidate evidence, and the engine produces a single, defensible evidence selection along with an exhaustive reasoning trace explaining why every decision was made.

---

## 2. Architectural Pipeline Flow

The execution model follows a strict **deterministic-first** hierarchy where semantic reasoning (LLMs) is consulted only when deterministic ambiguity is detected and is strictly bounded by safety vetoes.

```text
                        User Query + Candidate Pool
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 0: Candidate Bounding & Ingestion                │
       │ Enforces max_candidates bound; initializes Provenance.  │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 1: Temporal Intelligence (S16)                    │
       │ Extracts intent (point_in_time / latest / interval);    │
       │ computes compatibility scores per candidate.           │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 2: Relationship Graph Construction (S17)          │
       │ Identifies supersession, version chains, same-doc links.│
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 3: Conflict-Aware Assembly & Sufficiency (S14/15) │
       │ Detects contradictions; computes multi-signal MSE       │
       │ (coverage, conflict, support, temporal, redundancy).   │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 4: Deterministic Signal Extraction                │
       │ Gathers confidence gap, conflict severity, and          │
       │ superseded IDs to evaluate the Adjudication Gate.     │
       └────────────────────────────┬────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
           [No Ambiguity Detected]         [Ambiguity Detected]
                    │                               │
                    │                               ▼
                    │              ┌─────────────────────────────────┐
                    │              │ Layer 5: Semantic Reasoning (S18)│
                    │              │ Bounded candidate consultation  │
                    │              │ with validated JSON response.   │
                    │              └────────────────┬────────────────┘
                    │                               │
                    │                               ▼
                    │              ┌─────────────────────────────────┐
                    │              │ Layer 6: Deterministic Veto     │
                    │              │ Overrides LLM ACCEPT if         │
                    │              │ superseded or safety floor hit. │
                    │              └────────────────┬────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 7: Evidence Partitioning & Selection              │
       │ Separates candidates into selected vs. rejected sets.  │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Layer 8: Provenance Finalization (S19)                  │
       │ Seals the serializable DecisionRecord for archaeology.  │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
                         UnifiedEvidenceResult

# 3. Core Design Principles

```text
## Principle 1: Deterministic Safety is Authoritative
The hierarchy of authority is strictly preserved:
Deterministic Safety
≻
Deterministic Intelligence
≻
Semantic Adjudication
≻
Final Decision
≻
Provenance
Deterministic Safety≻Deterministic Intelligence≻Semantic Adjudication≻Final Decision≻Provenance
An LLM or semantic adjudicator can never override a deterministic safety constraint (such as supersession or hard contradiction floors).

## Principle 2: Zero Algorithm Duplication
UnifiedEvidenceEngine acts solely as an orchestrator. It wires existing components via their public interfaces (EvidenceAssembler, TemporalAnalyzer, RelationshipAnalyzer, AdjudicationController, DecisionRecorder) rather than reimplementing feature algorithms.

## Principle 3: Fault Isolation and Safe Degradation
Subsystem failures (e.g., malformed date strings, invalid metadata, adjudication timeout) are caught locally and logged as warnings.
The pipeline degrades gracefully to neutral/safe fallback states.
Observability is non-blocking: Provenance recording failures will never alter the correctness of an evidence decision.

```

# 4. Subsystem Interactions & Fallbacks

```text
Subsystem	Input Source	Pipeline Output / Contribution	Safe Degradation Fallback
Temporal (S16)	Query + Candidates	Enriched temporal scores & query intent	Returns original candidates un-scored
Relationships (S17)	Enriched Candidates	EvidenceGraph with node & edge mappings	Graph with 0 edges; continues assembly
Assembly (S14/15)	Query + Candidates + Graph	AssemblyResult (relational state, coverage, conflicts)	Empty assembly result
Adjudication (S18)	Ambiguous subset (
≤
3
≤3 chunks)	Structured judgment (ACCEPT/REJECT/UNCERTAIN)	Safe UNCERTAIN decision
Provenance (S19)	Events across all layers	Auditable DecisionRecord	NullDecisionRecorder (zero overhead)

```

# 5. State Invariants

```text

Max Candidates Enforced: Input candidate sets are truncated to config.max_candidates before processing.
Adjudication Bounded: No more than max_candidates (default 3) are ever sent to an LLM adjudicator.
Trace Completeness: Every decision path produces a valid DecisionRecord with non-empty event history when provenance is enabled.
Backward Compatibility: All existing entry points for S14, S15, S16, S17, S18, and S19 continue to function independently with unchanged semantics.

```