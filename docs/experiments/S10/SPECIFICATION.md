# S10 Experiment Specification — Adaptive Evidence Strategy Selection

## 1. Objective
Sprint 10 introduces dynamic, deterministic strategy selection into the Aryntra Synapse context-engineering pipeline. Instead of processing every incoming query uniformly through every heavy semantic and priority layer, Synapse evaluates cheap query and evidence signals to select an optimal processing path (`LIGHT`, `STANDARD`, or `DEEP`).

## 2. Research Hypothesis
By dynamically gating query/evidence evaluation through deterministic, low-overhead heuristic signals, Synapse can significantly reduce end-to-end priority and processing latency without sacrificing downstream context fidelity or retrieval quality.

## 3. Evaluated Candidates

* **Control Baseline:** Universal full execution (`STANDARD` path on 100% of queries).
* **Candidate A (Lexical Complexity Gate):** Routes short, simple queries (<=4 words, <=3 keywords) to `LIGHT` and complex queries (>=10 words, >=7 keywords) to `DEEP`.
* **Candidate B (Cache Warmth Router):** Routes cold-cache/multi-chunk queries away from expensive semantic re-embeddings.
* **Candidate C (Reuse Confidence Router):** Routes highly reused evidence batches (>=80% reuse rate from S7) to `LIGHT`, bypassing redundant re-scoring.
* **Candidate D (Priority Pre-screener):** Evaluates lexical overlap of the leading chunk; very high (>=0.60) or very low (<=0.05) overlap routes to `LIGHT`, while ambiguous cases (0.15–0.45) route to `DEEP`.
* **Candidate E (Composite Score Router):** Multi-signal weighted scoring combining query complexity, keyword density, cache hit rate, S7 reuse rate, and lexical overlap into a normalized [0.0, 1.0] intensity score.
* **Adaptive Combination (Primary + Fallback):** Candidate E as Primary with Candidate D as safety Fallback (upgrading uncertain `LIGHT` decisions to `STANDARD`).

## 4. Workload and Methodology
* 13 diverse test queries across Simple, Moderate, and Complex categories.
* Executed in 2 sequential sweeps (Cold Cache + Warm Cache), totaling 26 evaluations per configuration.
* All runs recorded under `experiments/S10_results.json`.