# SC-S1 Sprint Completion Report

**Sprint ID:** SC-S1
**Sprint Name:** The First Visible Comparison
**Project:** Aryntra Synapse -> Synapse Compare v0.1

---

## 1. Objective

Establish a reproducible baseline showing how a conventional retrieval
system behaves when presented with temporally versioned evidence.

## 2. Implemented functionality

- Two-document policy corpus (V1 superseded, V2 current).
- Pure-Python lexical retrieval baseline (lexical_token_overlap).
- Deterministic ranking with alphabetical tie-breaking.
- Machine-readable JSON result (schema_version 1.0).
- Terminal dashboard driven by the same result object.
- Honest evaluation (observation vs expected outcome).
- 27 automated tests.

## 3. Files added

  experiments/synapse_compare/sc_s1/README.md
  experiments/synapse_compare/sc_s1/SPRINT_REPORT.md
  experiments/synapse_compare/sc_s1/run_baseline.py
  experiments/synapse_compare/sc_s1/baseline.py
  experiments/synapse_compare/sc_s1/schemas.py
  experiments/synapse_compare/sc_s1/fixtures/policy_v1.json
  experiments/synapse_compare/sc_s1/fixtures/policy_v2.json
  experiments/synapse_compare/sc_s1/results/.gitkeep
  experiments/synapse_compare/sc_s1/results/sc_s1_result.json
  tests/test_sc_s1_baseline.py

## 4. Files modified

**None.** No existing project file was altered during SC-S1.

## 5. Commands executed

  python experiments/synapse_compare/sc_s1/run_baseline.py
  python -m pytest tests/test_sc_s1_baseline.py -v

## 6. Test results

**27 passed, 0 failed** in approximately 0.5 seconds.

## 7. Actual retrieval output

  1. AUTH-POLICY-V1 | Score: 0.5
  2. AUTH-POLICY-V2 | Score: 0.5
  Baseline output: Authentication is optional for internal systems.

## 8. Actual evaluation outcome

  expected_current_document: AUTH-POLICY-V2
  selected_current_document: false
  status: FAIL

No manipulation was applied to force this outcome.

## 9. Known limitations

- Two-document corpus; minimal lexical retrieval.
- No generative answer layer.
- No Synapse engine invocation (by design).
- Contradictory-evidence and safety-trap scenarios deferred.

## 10. Existing-engine integrity

- end_to_end_showcase.py: unmodified
- app/: unmodified
- tests/: only test_sc_s1_baseline.py added
- Verified via git diff --name-only returning empty.

## 11. Git commit information

  Branch: advanced
  Baseline HEAD: 41741a5d11ee682368b9b5a50b7361bdcf7da1ba
  Tag context: v1.13.0-1-g41741a5
  Working tree: clean prior to SC-S1

## 12. Recommended next step for SC-S2

Add a Synapse runner that imports UnifiedEvidenceEngine,
runs the same query against the same corpus, and writes
a result JSON with system=synapse. No engine changes needed.
