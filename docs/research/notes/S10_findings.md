# Sprint 10 Research Findings: Adaptive Evidence Strategy Selection

## Empirical Results Summary

| Configuration | Mean Priority Latency (ms) | Mean Total Latency (ms) | LIGHT | STANDARD | DEEP | Latency Reduction |
|---|---|---|---|---|---|---|
| **Control** | 15.124 ms | 32.769 ms | 0 | 26 | 0 | Baseline |
| **Candidate A** | 4.078 ms | 19.845 ms | 10 | 10 | 6 | -73.0% priority / -39.4% total |
| **Candidate B** | 4.851 ms | 19.563 ms | 0 | 26 | 0 | -67.9% priority / -40.3% total |
| **Candidate C** | 1.162 ms | 15.660 ms | 21 | 5 | 0 | -92.3% priority / -52.2% total |
| **Candidate D** | 4.107 ms | 18.494 ms | 12 | 14 | 0 | -72.8% priority / -43.6% total |
| **Candidate E** | 4.685 ms | 19.947 ms | 2 | 18 | 6 | -69.0% priority / -39.1% total |
| **Adaptive (Primary)** | 5.108 ms | 19.696 ms | 2 | 18 | 6 | -66.2% priority / -39.9% total |
| **Adaptive + Fallback**| 4.784 ms | 19.404 ms | 2 | 18 | 6 | -68.4% priority / -40.8% total |

## Key Insights
1. **Candidate C (Reuse)** was the fastest individual candidate due to aggressive `LIGHT` pathing on warm runs, but lacked granularity for novel complex queries.
2. **Candidate D (Pre-screener)** provided the cleanest lexical boundary distinction between clear and ambiguous evidence.
3. **Candidate E (Composite)** offered the most balanced multi-signal decision surface, routing 7.7% of queries to `LIGHT`, 69.2% to `STANDARD`, and 23.1% to `DEEP`.
4. **Adaptive + Fallback** successfully combined Candidate E as primary selector with Candidate D as fallback verification, achieving **-68.4% priority latency reduction** with full safety.