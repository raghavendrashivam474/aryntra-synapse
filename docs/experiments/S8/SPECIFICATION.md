# Aryntra Synapse — Sprint 8 Specification
## Evidence Relevance & Priority Management

**Sprint:** S8  
**Baseline:** `v0.9.0` (S7 Evidence Reuse & Deduplication)  
**Target Module:** `app/context/evidence_priority.py`

---

## 1. Objectives

1. Create a lightweight, deterministic evidence priority engine.
2. Score candidate evidence across semantic similarity, lexical overlap, and reuse history.
3. Partition evidence into `HIGH`, `MEDIUM`, and `LOW` priority classes.
4. Route `HIGH` priority evidence immediately into active context while retaining `MEDIUM`/`LOW` evidence for progressive expansion.
5. Retain zero-LLM-call overhead for priority assessment ($<1$ ms for lexical, $<150$ ms for batched semantic embeddings).

---

## 2. Priority Scoring Formula

$$\text{Priority Score} = \alpha \cdot \text{Semantic} + \beta \cdot \text{Lexical} + \gamma \cdot \text{Reuse}$$

Where:
- $\alpha = 0.50$, $\beta = 0.30$, $\gamma = 0.20$ (default full blend)
- $\text{Threshold}_{\text{HIGH}} = 0.60$
- $\text{Threshold}_{\text{MEDIUM}} = 0.30$

### Priority Classes & Lifecycle
- **HIGH** ($\ge 0.60$): Classified as `active` upon initial workspace allocation.
- **MEDIUM** ($[0.30, 0.60)$): Classified as `retained`; eligible for promotion during expansion.
- **LOW** ($< 0.30$): Classified as `retained`; lowest rank in progressive expansion queue.
