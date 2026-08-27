# S5 Research Findings — Evidence Sufficiency and Selective Promotion

## 1. Quantitative Findings

| Metric | S4 Workspace Baseline | S5 Selective Promotion (Experimental) | Delta |
|---|---|---|---|
| **Avg. Cumulative Context** | 2798.1 chars | 941.4 chars | **-66.36%** |
| **Avg. Model Calls / Query** | 4.00 | 1.00 | **-75.00%** |
| **Avg. Total Latency** | 67.63 s | 16.16 s | **-76.10% (4.18x speedup)** |
| **Early-Stop Rate** | 0.0% | 0.0% | — |

## 2. Key Insights
1. **Inference Loop Tax Eliminated**: Replacing iterative LLM self-assessment loops with local deterministic signals successfully collapsed model calls to exactly 1 per query.
2. **Deterministic Sufficiency Gating**: Combining retrieval score thresholds with keyword coverage ratios is highly stable and zero-cost, but keyword matching exhibits semantic-blindness, causing all queries to expand to the Stage 3 boundary.
3. **Graceful Halting**: When all chunks are exhausted, checking availability prior to evaluation prevents redundant checks, successfully fixing the S4 4-call loop tax.