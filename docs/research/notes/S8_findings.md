# Research Findings S8: Evidence Relevance & Priority Scoring

## Empirical Summary

From the S8 ablation experiment on the benchmark queries:
1. **Lexical Priority (Exp-B)** achieved ultra-low scoring latency of **0.247 ms** per query batch.
2. **Batch Embedding Optimization** reduced semantic scoring from serial loops down to a single batch matrix multiplication.
3. **Initial Context Activation** successfully selected high-priority chunks on focused queries (e.g. Q1 Architecture resolved in 1 chunk, 237 chars), proving that ranking correctly exposes sufficient context immediately.
4. **Preservation Guarantee** verified that unpromoted chunks remain available in the workspace if S6 sufficiency requires expansion.
