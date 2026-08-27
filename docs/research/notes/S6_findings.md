# S6 Research Findings: Semantic Sufficiency & Adaptive Routing

## Summary
Sprint 6 evaluated whether a local semantic similarity signal (Candidate A) or a hybrid lexical+semantic gate (Candidate B) could replace rigid lexical heuristics to enable genuine early stopping without adding LLM latency.

## Key Empirical Findings

1. **Resolution of S5 False Sufficiency on Unanswerable Queries**:
   - S5 falsely declared Q10 sufficient at Stage 0 due to lexical keyword hits (`Synapse`, `baseline`, `Sprint`, `0.2`).
   - S6 evaluated semantic sufficiency at `0.5538 < 0.60` threshold, rejecting single-chunk sufficiency and avoiding false early termination.
   - Q9 was safely rejected at `0.1228`.

2. **Adaptive Depth for Multi-Component Queries**:
   - Single-chunk direct factual queries (Q1, Q2, Q5, Q8) reached `0.6219 - 0.7412` semantic similarity and early-stopped at Stage 0 (1 chunk), saving 60-70% context.
   - Multi-chunk relational queries (Q3, Q4, Q6) appropriately expanded across stages.
   - Complex synthesis (Q7) reached sufficiency at Stage 1 (2 chunks, `0.6368`).

3. **Zero Inference Tax**:
   - Sufficiency evaluations required 0 LLM calls, maintaining total model calls at exactly 1.0 per query.
   - S6-B achieved an average total latency of 12.89s compared to S5's 15.46s.
