---

# Post-Sprint Completion Report

## SC-S2: Synapse Enters the Comparison

**Project:** Aryntra Synapse — Synapse Compare v0.1
**Sprint ID:** SC-S2 (Sprint 2 of 4)
**Branch:** `advanced`
**Base Commit:** `6b779bd` (tagged `v-SC-S1`)
**Report Date:** 2026-10-26
**Prepared For:** Senior Development Review
**Status:** COMPLETE — All Definition of Done criteria satisfied

---

## 1. Executive Summary

SC-S2 successfully integrated the existing Aryntra Synapse `UnifiedEvidenceEngine` with the controlled temporal-retrieval scenario established during SC-S1. The same query, the same two-document corpus, and the same evaluation criteria were used to produce a reproducible, side-by-side comparison between conventional lexical retrieval and the Synapse evidence-intelligence engine.

**Central finding:** Neither system selected the correct current policy (AUTH-POLICY-V2). Both received a FAIL evaluation. However, the nature of each failure is materially different. The baseline confidently stated the outdated policy as fact. Synapse detected the temporal intent, identified the supersession relationship, recognized the evidence as insufficient, and returned an UNCERTAIN decision at 0.48 confidence — refusing to assert the wrong answer definitively.

This is a legitimate research outcome. The experiment was designed to observe actual behavior, not to produce a predetermined result.

---

## 2. Sprint Objectives and Scope

### 2.1 Primary Objective

Execute the SC-S1 scenario (`SC-S1-TEMPORAL-001`) through the real `UnifiedEvidenceEngine` and produce a reproducible comparison against the recorded lexical-retrieval baseline.

### 2.2 Research Question

> Can Aryntra Synapse use its existing evidence-intelligence capabilities to identify the current policy when a conventional lexical retrieval baseline selects outdated evidence?

### 2.3 Scope Delivered

| Deliverable | Status |
|---|---|
| Repository reconnaissance | Complete |
| Synapse engine adapter | Complete |
| Real engine execution | Complete |
| Synapse result artifact | Complete |
| Comparison runner | Complete |
| Comparison artifact | Complete |
| Terminal dashboards | Complete |
| Test suite (33 tests) | Complete, all passing |
| SC-S1 regression verification (27 tests) | Complete, all passing |
| README documentation | Complete |
| Sprint completion report | Complete |

### 2.4 Scope Explicitly Excluded (per sprint spec)

No frontend, no engine modifications, no new scenarios, no LLM integration, no new dependencies, no refactoring of existing code.

---

## 3. Repository Reconnaissance

Before any implementation, the following files were inspected to establish the actual contracts.

### 3.1 SC-S1 Result Schema (`experiments/synapse_compare/sc_s1/schemas.py`)

- Schema version: `1.0`
- Scenario ID: `SC-S1-TEMPORAL-001`
- Query constant: `"What authentication policy is currently in effect for internal systems?"`
- Expected document: `AUTH-POLICY-V2`
- Result structure: `schema_version`, `experiment_id`, `system`, `query`, `corpus`, `retrieval`, `decision`, `evaluation`
- The `decision` and `evaluation` sections are generic and reusable for Synapse output
- The `retrieval` section is baseline-specific (lexical scores, ranks) and required a Synapse-specific replacement

### 3.2 SC-S1 Baseline (`experiments/synapse_compare/sc_s1/baseline.py`)

- Loads fixtures from `sc_s1/fixtures/*.json`
- Required fixture fields: `document_id`, `version`, `publication_date`, `status`, `content`
- Retrieval method: lowercase token overlap, scored as `|query ∩ doc| / |query|`
- Tie-breaking: alphabetical by `document_id` (this is why V1 wins at equal scores)
- Metadata is deliberately ignored during retrieval

### 3.3 SC-S1 Fixtures

**AUTH-POLICY-V1:** version 1.0, published 2024-01-01, status `superseded`, content "Authentication is optional for internal systems."

**AUTH-POLICY-V2:** version 2.0, published 2025-01-01, status `current`, content "Authentication is mandatory for internal systems.", supersedes V1.

### 3.4 UnifiedEvidenceEngine (`app/evidence/unified.py`)

This was the critical inspection. The actual interface differs from the assumed signature in several important ways:

| Property | Actual Implementation |
|---|---|
| Constructor | `UnifiedEvidenceEngine(config=UnifiedEvidenceConfig())` |
| Process method | `process(query: str, candidates: List[Any], context: Dict = None)` |
| Input format | List of dicts: `{"id": str, "text": str, "metadata": dict}` |
| Return type | `UnifiedProcessResult` dataclass |
| Key output fields | `decision` (str), `confidence` (float), `selected_evidence` (list of `{"chunk_id": id}`), `rejected_evidence`, `signals` (dict), `temporal_context` (dict), `relationships` (dict), `pipeline_time_ms` (float), `record` (DecisionRecord) |
| External dependencies | None — uses `MockAdjudicator` and rule-based components |
| Initialization | No model downloads, no API keys, no external services |

### 3.5 End-to-End Showcase (`experiments/end_to_end_showcase.py`)

Confirmed the invocation pattern: `engine = UnifiedEvidenceEngine()` followed by `engine.process(query, corpus)` where corpus is a list of `{"id", "text", "metadata"}` dicts. The showcase uses `sys.path.append(os.getcwd())` for import resolution.

### 3.6 Git State

- Branch: `advanced` (confirmed)
- HEAD: `6b779bd` (confirmed, matches `v-SC-S1` tag target)
- Working tree: clean (no unrelated modifications)
- SC-S1 files: all present and intact

---

## 4. Implementation Details

### 4.1 Synapse Adapter (`synapse_adapter.py`)

**Purpose:** Load SC-S1 fixtures, map them to the engine's input format, invoke the real engine, and normalize the response.

**Key functions:**

- `load_sc_s1_fixtures()` — Reads the canonical SC-S1 fixture JSON files directly from `sc_s1/fixtures/`. No duplication. Validates required fields.

- `map_to_synapse_format()` — Converts SC-S1 field names to engine field names:
  - `document_id` → `id`
  - `content` → `text`
  - `version`, `publication_date`, `status`, `supersedes` → nested `metadata` dict
  
  All metadata is preserved. Nothing is flattened into the text field.

- `run_synapse_engine()` — Instantiates `UnifiedEvidenceEngine()` and calls `process(query, synapse_corpus)`. Does not catch exceptions — callers handle failures to distinguish execution errors from evaluation outcomes.

- `normalize_engine_result()` — Converts `UnifiedProcessResult` into a JSON-serializable dict. Maps `chunk_id` values back to original document IDs. Extracts decision, confidence, temporal context, signals, and relationships. Evaluates temporal correctness against `AUTH-POLICY-V2`.

- `build_error_result()` — Produces a structured error result when the engine raises an exception. Does not fabricate a decision, confidence, or evaluation outcome.

**Design decisions:**
- The adapter does not select evidence on behalf of Synapse
- It does not reimplement temporal reasoning
- It does not recalculate confidence
- It does not manufacture a decision from metadata when the engine hasn't produced one
- Missing fields are represented as `null`, not invented

### 4.2 Synapse Runner (`run_synapse.py`)

**Purpose:** Orchestrate the end-to-end Synapse execution.

**Execution flow:**
1. Load SC-S1 canonical fixtures
2. Map to Synapse format
3. Invoke the engine via the adapter
4. Normalize the result (or capture the error)
5. Print a terminal dashboard showing decision, confidence, signals, and evaluation
6. Save `results/sc_s2_result.json`

### 4.3 Comparison Logic (`comparison.py`)

**Purpose:** Read both result artifacts, validate integrity, and produce a structured comparison.

**Key components:**

- `SystemSummary` dataclass — Captures one system's result for display (execution status, selected evidence, decision, confidence, temporal intent, conflict score, sufficiency score, evaluation status)

- `ComparisonResult` dataclass — Full comparison output including input integrity, both system summaries, evidence selection match, temporal correctness for each system, decision comparison narrative, and analytical notes

- `check_integrity()` — Validates that both results refer to the same experiment by comparing `experiment_id`, `query`, and `corpus.documents`. Returns `"MATCH"` or a description of the first mismatch.

- `compare()` — Builds the full comparison. Generates analytical notes based on observed behavior (e.g., "Synapse returned UNCERTAIN rather than confidently selecting outdated evidence").

### 4.4 Comparison Runner (`run_comparison.py`)

**Purpose:** Orchestrate the comparison and produce both terminal and JSON output.

**Execution flow:**
1. Load `sc_s1/results/sc_s1_result.json`
2. Load `sc_s2/results/sc_s2_result.json`
3. Run integrity checks
4. Build comparison
5. Print side-by-side terminal dashboard
6. Save `results/sc_s2_comparison.json`

### 4.5 Test Suite (`tests/test_sc_s2.py`)

**33 tests across 7 categories:**

| Category | Tests | What Is Verified |
|---|---|---|
| `TestLoadFixtures` | 5 | Document count, IDs, required fields, missing directory error, query match |
| `TestCorpusMapping` | 5 | Field mapping, text preservation, metadata preservation, no flattening, supersession |
| `TestBuildErrorResult` | 2 | Error structure, experiment ID preservation |
| `TestNormalizeEngineResult` | 5 | PASS/FAIL evaluation, confidence preservation, temporal context, uncertainty not overridden |
| `TestIntegrityChecks` | 4 | Match, experiment_id mismatch, query mismatch, corpus mismatch |
| `TestComparison` | 7 | Loading, integrity, both-fail evaluation, evidence match, confidence not fabricated, serialization, notes |
| `TestRegression` | 5 | SC-S1 result unchanged, scores intact, Synapse result exists, valid JSON, execution info |

---

## 5. Actual Experimental Results

### 5.1 Baseline (SC-S1) — Recorded

| Property | Value |
|---|---|
| Selected evidence | AUTH-POLICY-V1 |
| Decision | "Based on top-ranked evidence (AUTH-POLICY-V1): Authentication is optional for internal systems." |
| Confidence | N/A |
| Temporal awareness | None |
| Evaluation | **FAIL** |

### 5.2 Synapse (SC-S2) — Observed

| Property | Value |
|---|---|
| Selected evidence | AUTH-POLICY-V1 |
| Rejected evidence | AUTH-POLICY-V2 |
| Decision | UNCERTAIN |
| Confidence | 0.48 |
| Temporal intent | "current" |
| Target date | None |
| Relationship graph | 2 nodes, 1 edge |
| Conflict detected | False |
| Conflict score | 0.0 |
| Adjudication | UNCERTAIN |
| Safety veto | False |
| Sufficiency score | 0.0 |
| Pipeline latency | ~3.16 ms |
| Evaluation | **FAIL** |

### 5.3 Comparative Analysis

| Dimension | Baseline | Synapse |
|---|---|---|
| Evidence selected | V1 (wrong) | V1 (wrong) |
| Core evaluation | FAIL | FAIL |
| Decision stance | Definitive (stated wrong policy as fact) | UNCERTAIN (refused to commit) |
| Confidence | N/A | 0.48 (below threshold) |
| Temporal detection | None | "current" intent detected |
| Relationship awareness | None | Supersession edge found |
| Sufficiency awareness | None | 0.0 (recognized insufficiency) |
| User risk | **High** — confidently wrong | **Lower** — flagged uncertainty |

**Honest assessment:** Synapse did not solve the temporal selection problem for this scenario. The evidence assembler selected V1 despite the temporal analyzer correctly identifying "current" intent. The gap between temporal detection and evidence selection is a real architectural limitation, not a measurement artifact.

However, the calibration layer correctly synthesized the weak signals (low sufficiency, uncertain adjudication) into a downgraded confidence and an UNCERTAIN decision. The baseline has no such mechanism and stated the outdated policy with full confidence.

---

## 6. Problems Encountered and Mitigations

### 6.1 Problem 1: `NameError` in `normalize_engine_result`

**Symptom:** `NameError: name 'query' is not defined` when executing `run_synapse.py`.

**Root Cause:** The `normalize_engine_result()` function referenced a bare `query` variable in its return dict, but the function's parameters are `engine_result` and `sc_s1_documents`. There is no `query` parameter in scope. This was a coding error in the initial adapter implementation.

**Diagnosis:** The error was initially misattributed to the engine itself. A direct invocation test (`python -c "engine.process(query, corpus)"`) succeeded with `SUCCESS: UNCERTAIN`, proving the engine was functional. The traceback was then traced to line 173 of `synapse_adapter.py`.

**Fix:** Changed `"query": query,` to `"query": engine_result.query,` in `normalize_engine_result()`. The `UnifiedProcessResult` dataclass carries the original query as a field, making this the correct reference.

**Impact:** Adapter-only bug. No engine or SC-S1 changes required.

### 6.2 Problem 2: Over-Broad Regex Replacement in `build_error_result`

**Symptom:** 2 test failures in `TestBuildErrorResult` — `NameError: name 'engine_result' is not defined` at line 237 of `synapse_adapter.py`.

**Root Cause:** The PowerShell regex replacement used to fix Problem 1 (`-replace '"query": query,' '"query": engine_result.query,'`) matched both occurrences of the pattern in the file. The second occurrence was inside `build_error_result()`, where the function parameter IS correctly named `query`. The replacement incorrectly changed it to `engine_result.query`, which does not exist in that scope.

**Diagnosis:** The test failures pointed directly to line 237 inside `build_error_result`. Inspection confirmed the function takes `query: str` as a parameter, so the original reference was correct.

**Fix:** Reverted line 237 back to `"query": query,` using a context-aware PowerShell script that checked which function each occurrence belonged to.

**Impact:** Caught by the test suite before commit. Both tests pass after the fix. This incident validated the decision to write comprehensive tests early.

### 6.3 Lessons Learned

1. **PowerShell regex replacements on multi-function files are fragile.** Future fixes should use line-specific or function-scoped targeting.
2. **The test suite caught the regression immediately.** The 2 failing tests in `TestBuildErrorResult` were the only failures in an otherwise clean 33-test run, making the problem easy to isolate.
3. **Direct engine invocation tests are essential for isolating adapter bugs from engine bugs.** The `python -c` diagnostic in Block 5b prevented unnecessary investigation of the engine itself.

---

## 7. Test Results

### 7.1 SC-S2 Test Suite

```
33 passed in 15.01s
```

All 33 tests pass across all 7 categories.

### 7.2 SC-S1 Regression Suite

```
27 passed in 0.20s
```

All 27 existing SC-S1 tests continue to pass. No regressions introduced.

### 7.3 Reproducibility

The Synapse execution was run multiple times during development. The engine produces consistent results for this scenario: V1 selected, UNCERTAIN decision, ~0.48 confidence. The temporal intent detection and relationship graph construction are deterministic for this input.

---

## 8. Git Hygiene Report

| Check | Status |
|---|---|
| Development branch | `advanced` ✅ |
| Base commit | `6b779bd` (v-SC-S1) ✅ |
| Working tree pre-implementation | Clean ✅ |
| SC-S1 files modified | None ✅ |
| Engine files modified | None ✅ |
| Showcase modified | None ✅ |
| Shared config modified | None ✅ |
| Dependencies changed | None ✅ |
| Unrelated changes | None ✅ |
| Commits to `main` | None ✅ |
| Force-push | None ✅ |

All changes are additive, contained within `experiments/synapse_compare/sc_s2/`.

---

## 9. Architectural Decisions

**No shared architectural changes were made.** SC-S2 is entirely additive.

The default rule from the sprint specification was followed: the existing Synapse engine was not modified. The integration was achieved through an external adapter that maps SC-S1 fixtures to the engine's expected input format and normalizes the output for comparison.

If future sprints require the engine to weight temporal signals more heavily during evidence assembly (rather than only during calibration), that would constitute an architectural change requiring the approval process defined in Section 11 of the sprint specification.

---

## 10. Known Limitations

1. **Single scenario.** This comparison covers one temporal scenario with two synthetic documents. The results do not generalize to larger corpora, more complex temporal relationships, or real-world policy documents.

2. **Evidence assembler gap.** The engine's temporal analyzer correctly detected "current" intent, and the relationship analyzer found the supersession edge, but the evidence assembler still selected V1. The temporal and relationship signals are not currently strong enough to influence the assembler's selection logic. This is the primary area for potential improvement.

3. **MockAdjudicator.** The engine uses a `MockAdjudicator` rather than a real semantic adjudication model. A real adjudicator might produce different conflict assessments and adjudication decisions.

4. **No LLM integration.** The engine operates entirely on rule-based heuristics. No language model was invoked during this experiment. The decision and confidence values are products of the calibration layer's rule-based logic.

5. **Sufficiency score 0.0.** The sufficiency evaluator scored the evidence as completely insufficient, which contributed to the UNCERTAIN calibration but did not change the evidence selection. The sufficiency signal influences the final decision but not the intermediate assembly step.

6. **Two-document corpus.** The relationship graph (2 nodes, 1 edge) is minimal. More complex corpora would exercise the graph analysis more thoroughly.

---

## 11. Definition of Done Verification

### A. Integration
- [x] `UnifiedEvidenceEngine` interface inspected
- [x] Engine invoked using shared scenario
- [x] Original SC-S1 query unchanged
- [x] Canonical SC-S1 fixtures reused
- [x] Document metadata preserved
- [x] Actual engine output captured
- [x] Missing fields handled honestly
- [x] No mock output presented as real result

### B. Result Contract
- [x] Separate Synapse result artifact exists
- [x] Original baseline result preserved
- [x] Scenario and system identities explicit
- [x] Result contains actual execution information
- [x] Evidence and decision information recorded
- [x] Evaluation separate from execution status
- [x] JSON serialization works

### C. Comparison
- [x] Both result artifacts loadable
- [x] Query identity verified
- [x] Corpus identity verified
- [x] Evidence selection compared
- [x] Temporal correctness evaluated
- [x] Decision outcomes distinguished from evidence selection
- [x] Uncertainty represented accurately
- [x] Terminal report generated from actual results
- [x] Machine-readable comparison artifact produced

### D. Testing
- [x] Adapter tests pass (12 tests)
- [x] Comparison tests pass (11 tests)
- [x] Regression tests pass (5 tests)
- [x] Error-handling tests pass (2 tests)
- [x] All 27 SC-S1 tests still pass
- [x] At least one real end-to-end Synapse execution succeeded

### E. Repository Safety
- [x] SC-S1 files intact
- [x] Showcase behavior intact
- [x] No unrelated changes
- [x] No existing changes discarded
- [x] Final diff reviewed
- [x] No shared architectural changes made
- [x] Work on `advanced` branch

### F. Documentation
- [x] README exists with execution instructions
- [x] Actual findings recorded
- [x] Limitations documented
- [x] Git state recorded
- [x] SC-S3 integration requirements identified

---

## 12. Recommendations for SC-S3

1. **Frontend data sources.** Both `sc_s2_result.json` and `sc_s2_comparison.json` are self-contained and machine-readable. The frontend can consume them directly without additional transformation.

2. **Live comparison capability.** The `synapse_adapter` module can be imported and invoked programmatically for live comparison if SC-S3 requires real-time execution rather than static result display.

3. **Engine initialization.** The engine requires no special initialization, model downloads, or external services. It can be instantiated inline with `UnifiedEvidenceEngine()`.

4. **Temporal assembler gap.** If SC-S3 or SC-S4 intends to demonstrate improved temporal selection (not just improved calibration), the evidence assembler's interaction with temporal signals should be investigated. The temporal analyzer produces correct output; the assembler does not yet consume it effectively.

5. **Additional scenarios.** The contradictory-evidence and safety-trap scenarios mentioned in the sprint specification remain untested. They would provide a more comprehensive evaluation of the engine's capabilities.

---

## 13. Conclusion

SC-S2 achieved its objective: a working, reproducible, honest comparison between conventional lexical retrieval and the Aryntra Synapse engine against a controlled temporal scenario.

The result is nuanced. Synapse did not select the correct document, but it demonstrated materially different failure behavior — detecting temporal intent, building relationship graphs, recognizing evidence insufficiency, and calibrating to uncertainty rather than confidently asserting the wrong answer.

Both outcomes (the baseline's confident error and Synapse's uncertain non-selection) are valuable data points for the project's evidence-intelligence roadmap.

**SC-S2 is complete and ready for review.**

---

*End of Report*