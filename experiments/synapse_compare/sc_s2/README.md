# SC-S2: Synapse Enters the Comparison

**Sprint:** SC-S2 (Sprint 2 of 4 — Synapse Compare v0.1)
**Branch:** `advanced`
**Preceding Sprint:** SC-S1 — The First Visible Comparison (`v-SC-S1`)

---

## 1. Objective

SC-S2 executes the same controlled temporal-retrieval scenario used in SC-S1
through the actual Aryntra Synapse `UnifiedEvidenceEngine` and compares
the result against the recorded lexical-retrieval baseline.

**Research question:** Can Aryntra Synapse use its existing evidence-intelligence
capabilities to identify the current policy when a conventional lexical retrieval
baseline selects outdated evidence?

## 2. Relationship to SC-S1

| Aspect | SC-S1 | SC-S2 |
|---|---|---|
| System | Lexical token-overlap baseline | UnifiedEvidenceEngine |
| Scenario | SC-S1-TEMPORAL-001 | SC-S1-TEMPORAL-001 (same) |
| Query | Identical | Identical |
| Corpus | 2 synthetic policy docs | Same fixtures (reused) |
| Result | FAIL (selected V1) | See Results section |

SC-S2 reuses the canonical SC-S1 fixtures and query. It does not duplicate them.

## 3. Engine Interface (Verified by Reconnaissance)

| Property | Actual Value |
|---|---|
| Class | `UnifiedEvidenceEngine` |
| Module | `app.evidence.unified` |
| Constructor | `UnifiedEvidenceEngine(config=UnifiedEvidenceConfig())` |
| Process | `process(query: str, candidates: List[dict], context: dict = None)` |
| Input format | `{"id": str, "text": str, "metadata": dict}` |
| Return type | `UnifiedProcessResult` dataclass |
| Key fields | `decision`, `confidence`, `selected_evidence`, `signals`, `temporal_context` |

## 4. Fixture Mapping

| SC-S1 Field | Synapse Input |
|---|---|
| `document_id` | `id` |
| `content` | `text` |
| `version`, `publication_date`, `status`, `supersedes` | `metadata` (nested dict) |

All metadata is preserved. Nothing is flattened into text.

## 5. Execution

From the repository root:

```powershell
# Step 1: Generate the Synapse result
python experiments/synapse_compare/sc_s2/run_synapse.py

# Step 2: Compare baseline vs Synapse
python experiments/synapse_compare/sc_s2/run_comparison.py
```

**Output Files**

| File | Description |
|---|---|
| `results/sc_s2_result.json` | Synapse engine result |
| `results/sc_s2_comparison.json` | Side-by-side comparison |
| `../sc_s1/results/sc_s1_result.json` | Baseline (unchanged) |

## 6. File Structure

```text
experiments/synapse_compare/sc_s2/
├── README.md              # This file
├── SPRINT_REPORT.md       # Detailed sprint completion report
├── synapse_adapter.py     # Engine integration adapter
├── run_synapse.py         # Engine execution script
├── comparison.py          # Comparison logic
├── run_comparison.py      # Comparison runner
├── results/
│   ├── sc_s2_result.json
│   └── sc_s2_comparison.json
└── tests/
    └── test_sc_s2.py      # 33 tests
```

## 7. Actual Observed Results

### Baseline (SC-S1)

- **Selected evidence:** AUTH-POLICY-V1
- **Decision:** "Authentication is optional for internal systems."
- **Confidence:** N/A (no confidence model)
- **Evaluation:** FAIL

The baseline selected the superseded policy because both documents scored
identically (0.5) and the alphabetical tie-breaker favored V1.

### Synapse (SC-S2)

- **Selected evidence:** AUTH-POLICY-V1
- **Rejected evidence:** AUTH-POLICY-V2
- **Decision:** UNCERTAIN
- **Confidence:** 0.48
- **Temporal intent detected:** "current"
- **Relationship graph:** 2 nodes, 1 edge (supersession link found)
- **Conflict score:** 0.0
- **Sufficiency score:** 0.0
- **Safety veto:** False
- **Evaluation:** FAIL

### Key Observation

Both systems selected AUTH-POLICY-V1 and both FAIL the temporal correctness
evaluation. However, they fail in fundamentally different ways:

| Dimension | Baseline | Synapse |
|---|---|---|
| Evidence selected | V1 (wrong) | V1 (wrong) |
| Decision confidence | High (stated definitively) | Low (0.48, UNCERTAIN) |
| Temporal awareness | None | Detected "current" intent |
| Relationship awareness | None | Built graph, found supersession edge |
| Sufficiency awareness | None | Scored 0.0 (insufficient) |
| Risk to user | **High** — confidently wrong | **Lower** — flagged uncertainty |

Synapse did not solve the temporal selection problem for this scenario,
but it correctly recognized that something was insufficient and refused
to state the outdated policy as fact.

## 8. Evaluation Methodology

Evaluation is based on a single criterion:

> Did the system select AUTH-POLICY-V2 (the current policy)?

- **PASS:** AUTH-POLICY-V2 is in the selected evidence list.
- **FAIL:** AUTH-POLICY-V2 is not selected.
- **NOT_EVALUATED:** Execution failed before evidence selection.

Evidence selection correctness and decision correctness are evaluated
separately. A system may select the right evidence but return uncertainty,
or select wrong evidence but flag it as insufficient.

## 9. Testing

```powershell
# Run SC-S2 tests (33 tests)
python -m pytest experiments/synapse_compare/sc_s2/tests/test_sc_s2.py -v

# Verify SC-S1 regression (27 tests)
python -m pytest tests/test_sc_s1_baseline.py -v
```

### Test Coverage

| Category | Count | Scope |
|---|---|---|
| Fixture loading | 5 | Document loading, field validation, error handling |
| Corpus mapping | 5 | Field mapping, metadata preservation, no flattening |
| Error handling | 2 | Error result structure, experiment ID preservation |
| Result normalization | 5 | PASS/FAIL evaluation, confidence, temporal, uncertainty |
| Integrity checks | 4 | Match, experiment_id/query/corpus mismatch detection |
| Comparison logic | 7 | Loading, integrity, evaluation, serialization, notes |
| Regression | 5 | SC-S1 unchanged, scores intact, Synapse result valid |

## 10. Known Limitations

1. **Single scenario.** This comparison covers one temporal scenario with
   two synthetic documents. Results do not generalize.

2. **Engine selected V1.** The UnifiedEvidenceEngine's evidence assembler
   selected AUTH-POLICY-V1 despite detecting "current" temporal intent.
   The temporal signal was not strong enough to override the assembler's
   selection logic.

3. **MockAdjudicator.** The engine uses a MockAdjudicator. Real semantic
   adjudication may produce different results.

4. **No LLM integration.** The engine operates on rule-based heuristics.
   No language model was invoked during this experiment.

5. **Sufficiency score 0.0.** The sufficiency evaluator scored the evidence
   as completely insufficient, which contributed to the UNCERTAIN calibration
   but did not change the evidence selection.

## 11. Next Steps (SC-S3)

SC-S3 is expected to introduce a web frontend for the comparison. Key
integration points identified during SC-S2:

- Both result JSON files are machine-readable and self-contained.
- The comparison artifact includes all fields needed for visualization.
- The adapter can be invoked programmatically for live comparison.
- The engine interface is stable and requires no special initialization.

## 12. Architectural Decisions

No changes were made to the existing Synapse engine, SC-S1 files, or
shared project configuration. SC-S2 is entirely additive.