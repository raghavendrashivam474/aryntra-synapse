# S9 Experiment Specification: Evidence Processing Efficiency

## 1. Context & Baseline
- **Target Release:** `v1.1.0`
- **Previous Baseline:** `v1.0.0` (Sprint 8 - Priority Management)
- **Primary Objective:** Reduce the computational and latency overhead introduced by S8 semantic scoring from ~153ms down to under 50ms while maintaining 100% routing fidelity and preservation of sufficiency behavior.

## 2. Tested Hypotheses & Mitigators
- **Candidate A (Evidence Cache):** SHA-256 fingerprint-keyed LRU cache for chunk embeddings to skip re-computation on repeated chunk appearances.
- **Candidate B (Query Cache):** LRU cache for query embeddings to skip re-computation on identical or normalized query repetitions.
- **Candidate C (Lexical Fast-Path Gate):** A cheap keyword overlap check (Jaccard) to confidently classify and route obvious `HIGH` or `LOW` priority evidence before calling semantic models.
- **Candidate D (Evidence Cache + Gate):** Combining pre-filtering with chunk caching.
- **Candidate E (Full Blend):** Caching both queries and chunks, wrapped with the lexical pre-filter.

## 3. Evaluation Protocol
- **Dataset:** 5 distinct architectural queries and 2 immediate query repetitions.
- **Metrics Tracked:** Priority latency, total semantic evaluations, sufficiency rate, and average active chunks.
