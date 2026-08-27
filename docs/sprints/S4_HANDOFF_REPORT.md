# Sprint 4 to Sprint 5 Handoff — Cognitive Routing Gate

## 1. Handoff Elements
- **Frozen Predecessor**: `v0.6.0` (S4 Evidence Workspace)
- **Proven Substrate**: Stateful `EvidenceWorkspace` isolates query execution memory and calculates context composition metrics perfectly.
- **Identified Bottleneck**: Evaluating sufficiency dynamically at *every* stage is highly expensive (Loop Tax) and general LLMs show a 100% risk-averse bias to expand context to max steps.

## 2. Transition to Sprint 5
Sprint 5 moves the platform toward **Intelligent Context Gating**. Instead of letting the model iteratively self-assess context, a lightweight cognitive routing gate categorizes query complexity up front:
- Simple factual query -> Promote 1 chunk (One-shot, exactly 1 LLM call, bypass loops).
- Complex comparison -> Promote 3 chunks (One-shot).
- Adaptive route -> Run workspace progression.