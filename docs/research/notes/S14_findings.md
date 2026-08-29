# S14 Research Findings & Empirical Notes

## Date: March 2025
## Experiment: 8-Configuration Ablation Matrix (RQ1-RQ5)

---

## Finding 1: Progressive Assembly is the Dominant Factor
Config D (Assembly Only) achieved the largest single-factor improvement:
- Recall: 44.0% -> 80.0% (+36.0 points)
- Set Sufficiency: 38.5% -> 92.3% (+53.8 points)

This confirms H1b. The S13 fragmentation failure mode (54.8% Top-1) was primarily caused by the single-chunk selection assumption, not by ranking quality.

## Finding 2: Contradiction Detection is Cheap and Precise
Config B (Contradiction Only) added conflict awareness at 0.573ms mean latency with 33.3% conflict recall and zero false positives on clean queries. This confirms H1a.

The 33.3% conflict recall (rather than 100%) reflects the conservative topic-overlap threshold (Jaccard >= 0.30) which intentionally avoids false positives on loosely related chunks.

## Finding 3: Coverage Alone Improves Sufficiency but Not Recall
Config C (Coverage Only) improved set sufficiency from 38.5% to 53.8% but did not improve recall (44.0% unchanged). This is expected: coverage analysis identifies gaps but does not act on them without the assembly loop.

## Finding 4: Full Resolution Achieves Best Composite Trade-off
Config H (Full S14 Resolution) achieved:
- 80.0% recall, 92.3% set sufficiency, 16.7% conflict recall
- 2.992ms mean latency (below 5ms target)
- 15.73 trade-off score (7.7x improvement over S13 baseline of 2.04)

This confirms H1 and H1d.

## Finding 5: ConfidenceGuard Extension Reduces Guard Over-activation
S13 baseline guard activation was 69.2%. Config H reduced this to 53.8% because assembled evidence sets satisfy coverage thresholds that single chunks could not, reducing unnecessary fallback routing.

## Open Questions for S15
1. Can LLM-in-the-loop adjudication improve conflict recall beyond 16.7% without exceeding latency budget?
2. Does assembly benefit scale to corpus sizes above 250 chunks (S13 C250 benchmark)?
3. Can facet extraction generalize to domain-specific ontologies (medical, legal, financial)?
