# S5 Specification - Evidence Sufficiency and Selective Promotion

## Status: FROZEN SPECIFICATION
## Sprint: S5
## Frozen Predecessor: v0.6.0 (S4 Evidence Workspace)
## Control Baseline: S4 evidence_workspace_v1

---

## 1. Research Question
Can evidence sufficiency assessment reduce unnecessary context promotion
while maintaining answer quality and grounding?

## 2. Working Hypothesis
If Synapse can estimate whether active evidence sufficiently supports the
current query using lightweight deterministic signals, it can stop
progressive expansion earlier for queries that do not require additional
evidence, reducing model calls and cumulative context exposure without
materially degrading answer quality.

## 3. Sufficiency Mechanism

### Primary Signal: Retrieval Score Threshold
If the highest-ranked active chunk score exceeds a configurable threshold,
the evidence is considered potentially sufficient.

### Secondary Signal: Query-Evidence Keyword Coverage
If the overlap between query keywords and active evidence keywords exceeds
a configurable threshold, the evidence is considered topically sufficient.

### Combined Decision
Both signals must be satisfied for sufficiency to be declared.
This is a deterministic, zero-LLM-call mechanism.

### Configuration
- sufficiency_score_threshold: 0.45 (default)
- sufficiency_coverage_threshold: 0.25 (default)
- context_strategy: selective_v1

## 4. Loop Fix (from S4)
The sufficiency check must NOT execute when all chunks are already active.
Check has_available() BEFORE running sufficiency evaluation.
This eliminates the 4-call loop tax observed in S4.

## 5. Bounded Expansion
- MAX_ACTIVE_CHUNKS = 3
- MAX_EXPANSION_STEPS = 2
- Termination: sufficient | max_reached | no_more_evidence

## 6. Control
S4 evidence_workspace_v1 (frozen v0.6.0). Same retriever, queries, LLM.