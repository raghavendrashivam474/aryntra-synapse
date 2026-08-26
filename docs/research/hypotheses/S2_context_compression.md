# S2 Hypothesis — Context Compression

## Sprint
S2

## Date
2026-08-26

## Status
Active

---

## Primary Hypothesis

> Selective context compression can reduce context size and
> generation latency while preserving sufficient evidence for
> answering the controlled query set.

## Rationale

S1 demonstrated that richer context representation improves
evidence organization but increases context volume by ~38%
and generation latency by ~54%.

The latency cost is downstream (LLM token processing), not
upstream (representation construction was negligible).

This suggests a potential optimization surface: if we can
remove redundant or low-value text from retrieved chunks
**before** sending them to the LLM, we may recover the
latency cost without losing the evidence that matters.

## Null Hypothesis

> Context compression has no meaningful effect on answer
> quality or generation latency.

## Alternative Hypotheses

1. Compression reduces context but degrades answer quality
   (evidence loss dominates).
2. Compression reduces context and latency but quality is
   unchanged (noise removal).
3. Compression reduces context and **improves** quality
   (less noise = better focus).

## Prediction

We predict outcome 2: moderate context reduction (~20-35%)
with preserved answer quality and reduced generation latency.

## Falsification

The hypothesis is falsified if:
- Compression reduces context by <5% (not meaningful)
- Answer quality drops by ≥2 categories on ≥3/10 queries
- Generation latency does not decrease despite context reduction

## Relationship to S1

S1 asked: *How should context be structured?*
S2 asks: *How much context is actually needed?*

S2 does not contradict S1. It operates on a different axis.
A future S3 could combine structured representation **with**
compression.
