# S6 Experiment Specification

## Sprint
S6 — Semantic Sufficiency & Adaptive Routing

## Research Question
Can semantic similarity improve evidence-sufficiency decisions compared
with lexical matching while preserving S5's efficiency advantage?

## Modes Under Test

| Mode | Config Value | Sufficiency Engine | Description |
|---|---|---|---|
| S5 Baseline | `selective_v1` | `SufficiencyEngine` | Lexical only (frozen) |
| S6-A | `semantic_v1` | `SemanticSufficiencyEngine(semantic_only)` | Semantic only |
| S6-B | `blended_v1` | `SemanticSufficiencyEngine(blended)` | Lexical + Semantic |

## Procedure

1. Start server with `CONTEXT_REPRESENTATION=selective_v1`
2. Run `s6_experiment.py` → produces `S6_results_selective_v1.json`
3. Restart server with `CONTEXT_REPRESENTATION=semantic_v1`
4. Run `s6_experiment.py` → produces `S6_results_semantic_v1.json`
5. Restart server with `CONTEXT_REPRESENTATION=blended_v1`
6. Run `s6_experiment.py` → produces `S6_results_blended_v1.json`
7. Run `s6_analysis.py` → compares all three

## Metrics

- early_stop_rate
- false_sufficiency_rate (especially Q9-Q10)
- average_expansion_steps
- average_active_chunks
- model_calls (should remain 1 for all modes)
- cumulative_context_length
- total_latency
- sufficiency_log (semantic_score, lexical coverage, reasons)

## Success Criteria

- S6-A or S6-B achieves >0% early stopping (S5 achieved 0%)
- No false sufficiency on Q9-Q10
- Model calls remain at 1 (no LLM sufficiency judge)
- Answer quality preserved
