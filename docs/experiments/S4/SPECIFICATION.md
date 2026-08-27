# S4 Specification - Evidence Workspace and Context Retention

## Status: FROZEN SPECIFICATION
## Sprint: S4
## Frozen Predecessor: v0.5.0 (S3 Progressive Context Expansion)
## Control Baseline: S3 progressive_v1 (Top-K=3, initial=1, max_steps=2)

---

## 1. Research Question
Can an Evidence Workspace with selective promotion and incremental reuse
reduce redundant context processing while preserving the benefits of
progressive context expansion?

## 2. Working Hypothesis
A stateful Evidence Workspace can retain acquired evidence separately
from active LLM context, while controlled promotion and incremental
reuse can reduce repeated context processing and cumulative inference cost.

## 3. Three Components

### Component A - Evidence Workspace
Per-query stateful store that classifies retrieved chunks as
ACTIVE (currently in the LLM prompt) or AVAILABLE (retained but
not yet promoted). Workspace is created per query and discarded
after generation completes. No cross-query leakage.

### Component B - Controlled Promotion
Evidence moves from AVAILABLE to ACTIVE only when the expansion
mechanism determines additional evidence is required. Promotion
is bounded (MAX_ACTIVE_CHUNKS=3, MAX_EXPANSION_STEPS=2) and
deterministic (score-ordered). Each promotion event is recorded
with metadata (chunk_id, stage, reason, counts).

### Component C - Incremental Reuse Investigation
Investigate whether Ollama's conversation context field can be
reused across sufficiency and generation calls to avoid
reprocessing previously exposed tokens. This is an investigation,
not an assumption. Both paths (with and without reuse) are measured.

## 4. New vs Repeated Context Accounting
Every LLM call records:
- new_context_length: characters introduced for the first time
- repeated_context_length: characters already seen by the model
- cumulative_context_length: total across all calls

## 5. Configuration
- context_representation=evidence_workspace_v1
- max_active_chunks=3
- max_expansion_steps=2
- initial_chunk_count=1
- reuse_ollama_context=true|false (ablation toggle)

## 6. Control
S3 progressive_v1 (frozen). Same retriever, same queries, same LLM.
Only the context retention and reuse mechanism changes.