# S7 Handoff Report → S8

**From:** Sprint 7 — Evidence Reuse & Deduplication
**To:** Sprint 8 — Fine-Grained Promotion
**Release:** v0.9.0

---

## What S7 Delivered

1. **EvidenceFingerprint** (`app/retrieval/evidence_fingerprint.py`)
   - Normalize + SHA-256
   - Deterministic, conservative normalization
   - `tag_chunks()` adds fingerprint metadata to chunk dicts

2. **EvidenceStore** (`app/context/evidence_store.py`)
   - Cross-query persistent fingerprint → evidence mapping
   - `process()` classifies chunks as new/reused
   - ReuseMetrics per batch
   - Cumulative stats

3. **Pipeline Integration** (`app/api/routes.py`)
   - S7 sits between retrieval and LLM generation
   - Controlled by `evidence_reuse_enabled` config flag
   - S7 response fields for observability

## What S7 Does NOT Do

- Does not filter or remove evidence
- Does not decide sufficiency
- Does not compress
- Does not change retrieval
- Does not alter LLM behavior

## What S8 Should Know

- Chunks now carry `fingerprint` and `evidence_status` keys
- The EvidenceStore is accessible at the application level
- Reuse rate varies by workload (see S7 experiment results)
- The separation of concerns is strict:
  - S7: "Have we seen this?" (identity)
  - S6: "Is this enough?" (sufficiency)
  - S8: "How much should we expose?" (promotion)

## Frozen Components

Do not modify during S8:
- `evidence_fingerprint.py`
- `evidence_store.py`
- `sufficiency.py`
- `semantic_gate.py`
- `workspace.py` (unless adding promotion logic)

## Open Questions for S8

1. Can fine-grained promotion leverage fingerprint data to skip
   re-processing of already-promoted evidence?
2. Does selective promotion interact with reuse in unexpected ways?
3. What is the combined effect of S7 reuse + S8 promotion on latency?
