# S14 Research Hypothesis: Conflict-Aware Evidence Resolution & Progressive Assembly

## Primary Hypothesis (H1)
Explicitly modeling pairwise contradiction and multi-concept coverage across candidate evidence chunks will improve evidence set sufficiency by at least 30 percentage points over S13 Top-1 ranking on fragmented and contradictory query classes, without degrading latency beyond 10ms mean.

## Sub-Hypotheses

### H1a: Contradiction Detection
Deterministic heuristic signals (date mismatch, status antonyms, polarity inversion, numeric divergence) can detect factual conflicts with precision above 90% and zero LLM cost.

### H1b: Progressive Assembly
Bounded greedy assembly using marginal coverage gain will recover fragmented evidence recall from below 60% to above 75% on multi-concept queries.

### H1c: Conflict-Aware Guard Routing
Extending ConfidenceGuard with contradiction and coverage signals will reduce false confidence on contradictory evidence sets by at least 20 percentage points.

### H1d: Trade-off Preservation
Full S14 resolution (Config H) will maintain mean latency below 5ms and zero regression on S13 baseline accuracy (random/topic distractors).

## Null Hypotheses
- H0a: Contradiction detection adds latency without improving ranking quality.
- H0b: Progressive assembly over-selects irrelevant chunks, degrading precision.
- H0c: Coverage analysis duplicates existing sufficiency engine behavior.

## Experimental Design
8-configuration ablation matrix (A through H) evaluated across 6 query classes: factual, multi-concept, fragmented, contradictory, mixed, and distractor-heavy. Metrics: Top-1 accuracy, recall, set sufficiency, conflict recall, guard activation rate, mean/P95 latency, and composite trade-off score.
