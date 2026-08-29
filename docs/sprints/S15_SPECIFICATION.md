# Aryntra Synapse — Sprint 15 Specification

**Sprint:** 15
**Target:** `v1.7.0`
**Title:** Minimum Sufficient Evidence Controller
**Status:** Completed

---

## 1. Problem Statement

Sprint 14 introduced bounded progressive evidence assembly, improving set
sufficiency from 38.5% to 92.3%. However, the assembly loop uses a single
coverage-ratio threshold (`cov_report.is_sufficient`) to decide when to stop
expanding the evidence set.

This creates two failure modes:

### Failure A — Premature Stopping
Coverage ratio reaches the threshold, but critical query concepts remain
uncovered. The system stops too early and produces an incomplete answer.

### Failure B — Over-Expansion
Assembly continues adding low-value chunks after the answer is already
well-supported. This increases context size, latency, and the risk of
introducing contradictory or distracting information.

S15 introduces a **multi-signal sufficiency evaluator** that replaces the
single coverage-ratio check with a principled STOP / EXPAND / UNCERTAIN
decision based on six deterministic signals.

---

## 2. Research Question

> Can Synapse reliably stop evidence expansion once the current evidence
> set is sufficient, while avoiding premature stopping that causes
> unsupported or incomplete answers?

---

## 3. Architecture

### 3.1 Pipeline Position
text

               QUERY
                 │
                 ▼
        Adaptive Strategy
                 │
                 ▼
          Evidence Search
                 │
                 ▼
          Priority Engine
                 │
                 ▼
         ConfidenceGuard
                 │
                 ▼
      Conflict Resolution
                 │
                 ▼
    Progressive Evidence Assembly
                 │
                 ▼
      ┌─────────────────────┐
      │  S15 Sufficiency    │  ← NEW
      │     Evaluator       │
      └──────────┬──────────┘
                 │
         ┌───────┴────────┐
         ▼                ▼
     INSUFFICIENT      SUFFICIENT
     UNCERTAIN
         │                │
         ▼                ▼
      EXPAND            STOP
         │                │
         └───────┐        │
                 ▼        ▼
              Evidence → Answer
text


### 3.2 Integration Point

The evaluator plugs into `EvidenceAssembler.assemble()` at the loop
condition. Previously:

```python
while ... and not cov_report.is_sufficient:
Now (when evaluator is present):

Python

while ... and sufficiency_result.decision in (INSUFFICIENT, UNCERTAIN):
When no evaluator is provided, S14 behavior is byte-identical.

4. Signals
The evaluator combines six deterministic signals. All are derived from
S14's existing CoverageAnalyzer and ContradictionDetector outputs
plus chunk metadata. Zero LLM calls. Zero embedding calls.

#    Signal    Source    Range    Default Weight
1    Query coverage    CoverageReport.coverage_ratio    0–1    0.30
2    Evidence support    Mean priority_score of selected chunks    0–1    0.15
3    Unresolved concepts    1 - (missing / total) from CoverageReport    0–1    0.20
4    Conflict state    1 - ConflictReport.conflict_score    0–1    0.15
5    Redundancy    1 - normalized_marginal_gain    0–1    0.10
6    Marginal gain    Best remaining candidate ΔC    0–1    0.10
Signal Rationale
Coverage (0.30): Primary signal. Directly measures how many query
concepts are addressed by the current evidence set.
Unresolved (0.20): Complements coverage by penalizing specific
missing facets (e.g., query asks "cause and effect" but only cause
is covered).
Conflict (0.15): High conflict means the evidence set is internally
inconsistent. Stopping on contradictory evidence produces unreliable
answers.
Support (0.15): Low-relevance chunks are weak evidence even if
they cover the right concepts.
Redundancy (0.10): If remaining candidates add almost nothing new,
continued expansion is wasteful.
Marginal gain (0.10): Directly measures whether the next expansion
would materially improve coverage.
5. Decision Model
5.1 Score Computation
text

score = Σ (weight_i × signal_i)   for i in {coverage, support, unresolved,
                                              conflict, redundancy, marginal}
5.2 Special Rules (applied after base score)
Rule A — Redundancy Boost (conditional)
If no severe conflict exists AND either:

No remaining candidates + coverage ≥ sufficient_threshold, OR
Redundancy ≥ 0.90 + coverage ≥ 0.85 × sufficient_threshold
Then: score = max(score, sufficient_threshold)

Rule B — Conflict Veto (hard ceiling)
If conflict_score ≥ 0.40 AND coverage < 0.80:
Then: score = min(score, sufficient_threshold - 0.05)

This is a hard safety invariant. Severe conflict with incomplete
coverage must never be declared sufficient, regardless of other signals.

5.3 Decision Thresholds
Score Range    Decision    Assembly Action
≥ 0.70    SUFFICIENT    STOP
< 0.40    INSUFFICIENT    EXPAND
0.40 – 0.70    UNCERTAIN    EXPAND (conservative)
6. Safety Invariants
Conflict veto: High conflict + low coverage → never SUFFICIENT.
Hard bounds: max_chunks=5, max_iterations=4 (inherited from S14).
Conservative uncertainty: UNCERTAIN → EXPAND, not STOP.
Backward compatibility: No evaluator = S14 behavior.
No LLM dependency: All signals are deterministic and sub-millisecond.
7. Configuration
S15SufficiencyConfig provides five presets:

Preset    Sufficient Threshold    Use Case
balanced()    0.70    Default production
conservative()    0.80    High-stakes queries
aggressive()    0.60    Latency-sensitive
coverage_only()    0.70    Ablation study
no_conflict()    0.70    Ablation study
All weights and thresholds are configurable. No magic numbers are
hard-coded in the evaluation logic.

8. Out of Scope
S15 does NOT implement:

LLM-based evidence evaluation
Temporal reasoning
Multi-hop reasoning
Answer verification
Conflict adjudication (detection only, inherited from S14)
Domain-specific facet ontologies
These are candidates for S16+.
