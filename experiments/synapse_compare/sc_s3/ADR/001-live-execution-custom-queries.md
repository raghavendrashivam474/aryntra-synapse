# ADR-001: Live Engine Execution & Custom Query Architecture Proposal for SC-S4

**Status:** Approved with Conditions (Target: Sprint SC-S4)  
**Date:** 2025-02-18  
**Author:** Junior Developer  
**Reviewer:** Senior Developer / Technical Reviewer  
**Applies to:** `experiments/synapse_compare/`  

---

## 1. Summary Decision

The proposal to introduce live custom query execution via a lightweight FastAPI backend service is **Approved with conditions** for Sprint SC-S4.

---

## 2. Senior Developer Review & Decision Matrix

| Item | Proposal | Senior Dev Decision | Conditions / Architectural Directive |
|---|---|---|---|
| **Backend API** | Lightweight FastAPI wrapper under `experiments/synapse_compare/server/` | **Approved conditionally** | Service must expose public adapters without modifying shared engine internals. |
| **Endpoint** | `POST /api/v1/compare` | **Approved with refinements** | Request must require query text & `top_k`. Response must separate `execution`, `comparison`, and `evaluation`. |
| **Default Mode** | Recorded Artifact Mode as landing state | **Approved (Mandatory)** | SC-S1/SC-S2 recorded JSON artifacts remain the primary, reproducible scientific reference. |
| **Live Execution** | Custom Query Execution against fixed policy corpus | **Approved** | Allows testing arbitrary query text against the existing policy document set. |
| **Custom Uploads**| Uploading arbitrary custom documents | **Deferred** | Corpus parsing/validation carries isolate risks. Deferred to a future dedicated sprint. |
| **Engine Core** | Modify `UnifiedEvidenceEngine` | **Prohibited** | Must reuse public adapters (`synapse_adapter.py` and `baseline.py`). |
| **Evaluation** | Evaluate all live queries | **Approved with isolation** | Live queries without ground truth must mark evaluation as `not_applicable` rather than inferring correctness from agreement. |

---

## 3. Required API Contract for SC-S4

### Endpoint
`POST /api/v1/compare`

### Request
```json
{
  "query": "What authentication policy is currently in effect for internal systems?",
  "top_k": 2
}
```

### Response

```JSON
{
  "run_id": "live-run-uuid",
  "mode": "live",
  "query": "What authentication policy is currently in effect for internal systems?",
  "corpus": {
    "id": "existing-policy-corpus",
    "version": "1.0"
  },
  "baseline": {
    "execution_status": "success",
    "result": {},
    "error": null
  },
  "synapse": {
    "execution_status": "success",
    "result": {},
    "error": null
  },
  "comparison": {
    "status": "completed",
    "differences": []
  },
  "evaluation": {
    "status": "not_applicable",
    "ground_truth_id": null,
    "metrics": null
  }
}
```

## 4. Implementation Gate for SC-S4

Before implementation begins in SC-S4, the developer must complete a short reconnaissance report covering:

  1. Public interfaces of LexicalBaselineEngine and UnifiedEvidenceEngineAdapter.
  2. Corpus loading and configuration mechanisms.
  3. Concurrency and request validation limits.
  4. Proposed API request/response schema validation via Pydantic.
  5. Integration test strategy verifying live mode alongside SC-S1 and SC-S2 regressions.
