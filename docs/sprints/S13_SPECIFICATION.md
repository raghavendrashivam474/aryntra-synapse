# Sprint 13 Specification: Master Generalization & Failure Mapping

**Target Version:** `v1.5.0`  
**Role:** Diagnostic & Empirical Research Sprint  
**Baseline Test Count:** 216 tests  
**New Target Test Count:** 227 tests  

---

## 1. Executive Intent

Sprint 13 systematically evaluates the calibrated adaptive evidence architecture established in S12 across varying corpus scales, distractor types, query complexities, and evidence distributions. Rather than introducing architectural components or modifying the calibrated weights, Sprint 13 implements a reproducible Generalization Laboratory to measure failure boundaries and classify failure root causes.

---

## 2. Experimental Dimensions Under Evaluation

1. **Dimension A — Corpus Scaling:**
   - Evaluated at `N = {5, 25, 50, 100, 150, 250}` chunks.
2. **Dimension B — Distractor Taxonomy & Densities:**
   - `D1_random`: Unrelated background statements.
   - `D2_topic`: Same engineering topic, non-answer facts.
   - `D3_lexical`: High keyword overlap without answer semantics.
   - `D4_semantic`: Semantically adjacent concepts without target answer.
   - `D5_partial`: Incomplete fragment of the answer.
   - `D6_contradictory`: Direct negative contradictions of target facts.
   - Densities: Low (1:4), Moderate (1:9), High (1:24), Dense (1:49).
3. **Dimension C — Query Complexity Classes:**
   - `Q1_factual`, `Q2_keyword_heavy`, `Q3_paraphrased`, `Q4_multi_concept`, `Q5_multi_hop`, `Q6_ambiguous`, `Q7_sparse`.
4. **Dimension D — Evidence Distribution:**
   - Concentrated, Distributed, Redundant, Sparse, Fragmented.
5. **Dimension E — Signal Configurations:**
   - `calibrated_blend` (0.50 / 0.35 / 0.15)
   - `semantic_only` (1.00 / 0.00 / 0.00)
   - `lexical_only` (0.00 / 1.00 / 0.00)
   - `semantic_lexical` (0.60 / 0.40 / 0.00)
   - `semantic_reuse` (0.70 / 0.00 / 0.30)
   - `lexical_reuse` (0.00 / 0.70 / 0.30)
6. **Dimension F — Adaptive Routing & Telemetry:**
   - Observability for `LIGHT`, `STANDARD`, `DEEP`, and `FALLBACK` execution paths.
7. **Dimension G — ConfidenceGuard & Recovery Rate:**
   - Fallback trigger assessment and measurement of recovered answer-bearing evidence.

---

## 3. Failure Severity Taxonomy (F0–F4)

- **F0 (No Failure):** Top-1 is answer bearing and recall is 100%.
- **F1 (Selection Degradation):** Top-1 missed, but evidence survived in Top-K (recall ≥ 0.66) and context survival ≥ 50%.
- **F2 (Deprioritized Recoverable):** Evidence ranked low (recall < 0.66), but survived or guard triggered fallback.
- **F3 (Evidence Pruned):** Answer-bearing evidence completely suppressed from active context.
- **F4 (Dangerous Unsupported):** Contradictory distractor placed at Top-1 with high confidence.

---

## 4. Verification Requirements

- Execute multi-dimensional matrix (1,512 trials across 6 configurations).
- Execute distractor density benchmark.
- Generate machine-readable artifacts (`S13_results.json`, `S13_distractor_benchmark_results.json`).
- Ensure all 216 baseline tests + 11 new tests pass (227 total).
