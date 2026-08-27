# Sprint 3 to Sprint 4 Handoff Report — Transition to Evidence Workspace

## 1. What Sprint 4 Inherits from Sprint 3
- **Frozen Baseline**: `v0.5.0` (S3 Progressive Context Expansion)
- **Verified Concept**: The core idea that retrieved context can be stored, staged, and actively managed over time, rather than processed as a static, block-injected string.
- **Differentiated Metrics**: S3 leaves a clean logging structure distinguishing **Peak Context** from **Cumulative Context**, preventing misleading optimizations that hide recurrent token consumption.

## 2. Roadmap to Sprint 4 (The Evidence Workspace / Context Cache)
While S3 proved that progressive context management can work, it highlighted a major vulnerability: **redundant reprocessing** of the same chunks across successive stages (e.g. evaluating C1, then C1+C2, then C1+C2+C3). 

This sets up the transition to **Sprint 4 — Evidence Workspace & Context Retention Cache**:
text

                   RETRIEVAL LAYER
                          │
                          ▼
                  Candidate Chunks
                          │
                          ▼
         ┌──────────────────────────────────┐
         │    SYNAPSE EVIDENCE WORKSPACE    │
         │                                  │
         │   [ Inactive Cached Evidence ]   │
         │                │                 │
         │                ▼  (Promotion)    │
         │   [  Active Generation Prompt ]  │
         └────────────────┬─────────────────┘
                          │
                          ▼
                     OLLAMA LLM
text


### Objectives of Sprint 4:
1. **Stateful Retained Context**: Establish an in-memory/session-level context cache so that once evidence is read by the LLM, it is stored in a structured workspace state, rather than re-appended and re-sent through a raw string.
2. **Selective Context Promotion**: Design a policy where the LLM can selectively fetch and promote specific chunks from the cached background repository into the active window.
3. **Recursive Cost Suppression**: Maximize the ratio of answer coverage to cumulative character overhead.