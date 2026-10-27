# SC-S2 Sprint Completion Report

**Sprint ID:** SC-S2
**Sprint Name:** Synapse Enters the Comparison
**Branch:** `advanced`
**Preceding Sprint:** SC-S1 (`v-SC-S1` at `6b779bd`)
**Status:** COMPLETE

---

## 1. Executive Summary

SC-S2 successfully integrated the Aryntra Synapse `UnifiedEvidenceEngine`
with the controlled temporal-retrieval scenario established in SC-S1.
The same query and corpus were executed through both systems, and a
reproducible side-by-side comparison was produced.

**Key finding:** Both systems selected AUTH-POLICY-V1 (the superseded
policy) and both FAIL the temporal correctness evaluation. However,
Synapse returned UNCERTAIN with 0.48 confidence and detected the
temporal intent, while the baseline confidently stated the wrong policy.

## 2. Implementation Scope

### Completed

- [x] Repository reconnaissance (engine interface, SC-S1 contracts)
- [x] Synapse adapter with fixture mapping
- [x] Real engine execution against shared scenario
- [x] Synapse result artifact (`sc_s2_result.json`)
- [x] Comparison runner with integrity validation
- [x] Comparison artifact (`sc_s2_comparison.json`)
- [x] Terminal dashboard for both execution and comparison
- [x] Test suite (33 tests, all passing)
- [x] SC-S1 regression verified (27 tests, all passing)
- [x] Documentation (README + this report)

### Not Attempted (Out of Scope)

- Web frontend (SC-S3)
- Engine modifications
- New scenarios
- LLM or embedding integration

## 3. Repository Reconnaissance Findings

### Engine Input Contract

| Property | Value |
|---|---|
| Class | `UnifiedEvidenceEngine` |
| Module | `app.evidence.unified` |
| Constructor | `UnifiedEvidenceEngine(config=UnifiedEvidenceConfig())` |
| Method | `process(query: str, candidates: List[dict], context: dict = None)` |
| Candidate format | `{"id": str, "text": str, "metadata": dict}` |
| Dependencies | None external (uses MockAdjudicator, rule-based components) |

### Engine Output Contract

| Field | Type | Description |
|---|---|---|
| `decision` | str | Calibrated decision: ANSWER/REJECT/UNCERTAIN |
| `confidence` | float | Calibrated confidence score [0.0, 1.0] |
| `selected_evidence` | List[dict] | `[{"chunk_id": id}, ...]` |
| `rejected_evidence` | List[dict] | `[{"chunk_id": id}, ...]` |
| `signals` | dict | Conflict, adjudication, safety, sufficiency |
| `temporal_context` | dict | `query_intent`, `target_date` |
| `relationships` | dict | `node_count`, `edge_count` |
| `pipeline_time_ms` | float | Execution latency |
| `record` | DecisionRecord | Provenance trace |

### SC-S1 Schema Compatibility

The SC-S1 schema's `decision` and `evaluation` sections are generic enough
to represent Synapse output. The `retrieval` section is baseline-specific
(lexical scores, ranks) and was replaced with a Synapse-specific structure
containing `selected_evidence` and `rejected_evidence` lists.

## 4. Files Added and Modified

### New Files

| File | Purpose |
|---|---|
| `experiments/synapse_compare/sc_s2/synapse_adapter.py` | Engine integration |
| `experiments/synapse_compare/sc_s2/run_synapse.py` | Execution script |
| `experiments/synapse_compare/sc_s2/comparison.py` | Comparison logic |
| `experiments/synapse_compare/sc_s2/run_comparison.py` | Comparison runner |
| `experiments/synapse_compare/sc_s2/results/sc_s2_result.json` | Synapse result |
| `experiments/synapse_compare/sc_s2/results/sc_s2_comparison.json` | Comparison |
| `experiments/synapse_compare/sc_s2/tests/test_sc_s2.py` | Test suite |
| `experiments/synapse_compare/sc_s2/tests/__init__.py` | Package init |
| `experiments/synapse_compare/sc_s2/results/.gitkeep` | Dir placeholder |
| `experiments/synapse_compare/sc_s2/README.md` | Documentation |
| `experiments/synapse_compare/sc_s2/SPRINT_REPORT.md` | This file |

### Modified Files

None. All changes are additive.

## 5. Engine Integration Details

The adapter performs three steps:

1. **Load** canonical SC-S1 fixtures from `sc_s1/fixtures/`
2. **Map** fields: `document_id`->`id`, `content`->`text`, rest->`metadata`
3. **Invoke** `UnifiedEvidenceEngine().process(query, corpus)`

No engine modifications were required. The engine initialized cleanly
with no external model dependencies.

## 6. Actual Experimental Results

### Baseline (SC-S1)

- Selected: AUTH-POLICY-V1
- Decision: "Authentication is optional for internal systems."
- Evaluation: FAIL

### Synapse (SC-S2)

- Selected: AUTH-POLICY-V1
- Decision: UNCERTAIN (confidence: 0.48)
- Temporal intent: "current"
- Relationship graph: 2 nodes, 1 edge
- Sufficiency: 0.0
- Evaluation: FAIL

### Interpretation

Neither system solved the temporal selection problem. The engine's
evidence assembler selected V1 despite the temporal analyzer correctly
identifying "current" intent. The gap between temporal detection and
evidence selection is a known area for future improvement.

However, Synapse's calibration layer correctly downgraded confidence
to 0.48 and returned UNCERTAIN, preventing the system from confidently
stating outdated policy as fact. The baseline made no such distinction.

## 7. Test Results

### SC-S2 Tests

```
33 passed in 15.01s
```

### SC-S1 Regression Tests

```
27 passed in 0.20s
```

All tests pass. No regressions detected.

## 8. Git Hygiene Report

| Check | Status |
|---|---|
| Branch | `advanced` |
| Base commit | `6b779bd` (v-SC-S1) |
| Working tree pre-implementation | Clean |
| SC-S1 files modified | None |
| Engine files modified | None |
| Shared config modified | None |
| Unrelated changes | None |

## 9. Problems Encountered

### Bug 1: `NameError` in `normalize_engine_result`

- **Cause:** The function referenced a bare `query` variable instead of
  `engine_result.query`. The `query` parameter was not in scope.
- **Fix:** Changed to `engine_result.query` which accesses the query
  stored in the `UnifiedProcessResult` dataclass.
- **Impact:** Adapter bug only. No engine or SC-S1 changes needed.

### Bug 2: Over-broad regex fix in `build_error_result`

- **Cause:** The PowerShell regex replacement for Bug 1 also matched
  the `build_error_result` function where the parameter IS named `query`.
- **Fix:** Reverted the replacement inside `build_error_result` only.
- **Impact:** Caught by tests (2 failures). Fixed and re-verified.

## 10. Architectural Decisions

No shared architectural changes were made. SC-S2 is entirely additive.

## 11. Known Limitations

1. Single scenario, two synthetic documents.
2. Engine selected V1 despite temporal detection.
3. MockAdjudicator in use; real adjudication may differ.
4. No LLM integration.
5. Sufficiency score 0.0 did not influence evidence selection.

## 12. Readiness Assessment for SC-S3

SC-S2 is ready to support SC-S3 frontend integration:

- Result JSON files are self-contained and machine-readable.
- Comparison artifact includes all visualization-relevant fields.
- Adapter can be imported for live execution.
- Engine requires no special initialization or external services.
- Test suite provides regression safety for future changes.

**Recommended SC-S3 starting point:** Read `sc_s2_result.json` and
`sc_s2_comparison.json` to populate a comparison dashboard.

