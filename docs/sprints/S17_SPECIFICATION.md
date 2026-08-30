# SPRINT 17 SPECIFICATION — Evidence Relationship Graph & Coherent Evidence Assembly

**Sprint:** S17  
**Target Release:** `v1.9.0`  
**Base Release:** `v1.8.0` (S16 Temporal & Version-Aware Selection)  
**Status:** Completed & Validated  
**Module:** `app/evidence/relationships.py`, `app/evidence/assembly.py`, `app/evidence/config.py`

---

## 1. Problem Statement & Motivation

Prior to S17, Synapse possessed sophisticated individual-evidence scoring capabilities across multiple dimensions:
- Semantic & Lexical relevance (S1–S10)
- Adaptive routing and calibration (S11–S13)
- Conflict detection and safety invariants (S14)
- Minimum Sufficient Evidence (MSE) stopping control (S15)
- Temporal and version validity scoring (S16)

However, the assembly model was fundamentally flat:
```text
Selected Evidence: [A, B, C, D]
The system evaluated what each chunk was, but not how chunks structurally related to one another. This created structural incoherence risks where individually high-scoring chunks could be assembled together despite supersession, lineage redundancy, or unlinked contradictions.

S17 transitions Synapse from:

"Which evidence chunks are relevant?"
to:
"How do these evidence chunks relate to one another?"

2. Core Architectural Principles & Invariants
Zero LLM / Embedding Calls: All relationship detection is strictly deterministic, regex/metadata/lexical-based.
Reuse Existing Authority Signals:
Consumes S14 ContradictionDetector for CONTRADICTS edges.
Consumes S16 TemporalAnalyzer / TemporalMetadata for SUPERSEDES and TEMPORALLY_ADJACENT edges.
Conflict Safety Invariant: CONTRADICTS edges structurally mark factual opposition; they never silently delete or suppress candidate evidence.
Precision Guard Invariant: Unrelated chunks must yield zero edges. No speculative or probabilistic edge inference.
Bounded Graph Construction: 
O
(
n
2
)
O(n 
2
 ) pairwise analysis bounded strictly by candidate pool size (max_graph_nodes=20, max_relationship_edges=50). No external graph databases.
3. Relationship Vocabulary
Relationship Type    Directionality    Detection Mechanism    Confidence
SUPERSEDES    Directed (
A
→
B
A→B)    Version comparison (
v
A
>
v
B
v 
A
​
 >v 
B
​
 ) or explicit metadata    0.95–1.00
SUPERSEDED_BY    Directed (
B
→
A
B→A)    Inverse of supersession    0.95–1.00
CONTRADICTS    Bidirectional / Directed    S14 ContradictionDetector conflict report    Overlap score (0.4–1.0)
SAME_DOCUMENT    Undirected / Symmetric    Shared document_id or identical source doc    1.00
SAME_VERSION_CHAIN    Undirected / Lineage    Shared document root lineage (e.g. policy_v1 ~ policy_v2)    0.95
TEMPORALLY_ADJACENT    Directed (
t
1
→
t
2
t 
1
​
 →t 
2
​
 )    Consecutive calendar years (
Δ
y
=
1
Δy=1) or contiguous effective dates    0.85–0.90
ELABORATES    Directed (
A
→
B
A→B)    Explicit section/chunk citation or parent_id hierarchy    0.85–1.00
SUPPORTS    Directed (
A
→
B
A→B)    Explicit deterministic structural support    0.85–1.00
4. Integration into Assembly Pipeline
text

Query + Ranked Candidates
        │
        ▼
S16 Temporal Enrichment
        │
        ▼
S17 Relationship Graph Construction (EvidenceGraph)
        │
        ▼
Relationship-Aware Candidate Ordering (Demote superseded, boost chain head)
        │
        ▼
Bounded Progressive Assembly Loop (S14 Greedy + S15 MSE Stopping)
        │
        ▼
Global Contradiction & Conflict Guard (S14 Invariant)
        │
        ▼
AssemblyResult (Selected Chunks + Relational State + EvidenceGraph + Metrics)
5. Configuration Interface (S17RelationshipConfig)
relationship_enabled: bool = True
relationship_weight: float = 0.15
max_relationship_edges: int = 50
max_graph_nodes: int = 20
enable_supersession_edges: bool = True
enable_contradiction_edges: bool = True
enable_same_doc_edges: bool = True
enable_version_chain_edges: bool = True
enable_temporal_adjacency_edges: bool = True
enable_elaboration_edges: bool = True
enable_transitive_supersession: bool = True
superseded_candidate_demotion: float = 0.20
current_version_head_boost: float = 0.05
