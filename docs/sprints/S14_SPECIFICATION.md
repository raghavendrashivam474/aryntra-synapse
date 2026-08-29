# Aryntra Synapse — Sprint 14 Specification

**Target Version:** `v1.6.0`  
**Theme:** Conflict-Aware Evidence Resolution & Progressive Evidence Assembly  
**Scope:** Controlled transition from pure evidence selection (ranking) to evidence interpretation (relational coherence and progressive assembly).

---

## 1. Executive Summary & Problem Statement

S13 revealed that while multi-signal calibrated ranking and `ConfidenceGuard` achieve 95.2% Top-1 accuracy and 97.7% recovery on standard distractors, the system degraded when faced with two distinct structural failure modes:
1. **Contradictory Distractors (D6):** 65.1% Top-1 accuracy due to ranking algorithms treating mutually incompatible statements as equally plausible high-relevance chunks.
2. **Fragmented / Partial Evidence (D5):** 54.8% Top-1 accuracy and 59.3% recall because Top-1 ranking inherently assumes a single chunk contains the complete answer.

Sprint 14 transitions Synapse from asking *"Which evidence is most relevant?"* to asking:
> **"How do these candidate pieces of evidence relate to one another, and does the assembled combination form an internally consistent and sufficient basis for an answer?"**

---

## 2. Research Questions (RQ1–RQ5)

* **RQ1 (Contradiction Detection):** Can Synapse deterministically detect mutually incompatible claims across candidate evidence chunks without relying on costly LLM inference?
* **RQ2 (Contradiction-Aware Ranking):** Does explicitly penalizing contradiction improve evidence selection compared with semantic and lexical ranking alone?
* **RQ3 (Progressive Fragment Assembly):** Can multiple individually partial chunks be progressively assembled into a sufficient evidence set using bounded greedy selection?
* **RQ4 (Relational Evidence State):** Can Synapse distinguish between `SUPPORTING`, `CONTRADICTORY`, `PARTIAL`, `INSUFFICIENT`, and `SUFFICIENT` relational states?
* **RQ5 (Trade-off Frontier):** Can these capabilities be introduced while maintaining sub-5ms processing latency and zero degradation to baseline routing safety?

---

## 4. Benchmark Configuration Matrix (Configs A–H)

| Config | Name | Contradiction | Coverage | Progressive Assembly | ConfidenceGuard |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **A** | S13 Baseline | No | No | No | Standard |
| **B** | Contradiction Only | Yes | No | No | Standard |
| **C** | Coverage Only | No | Yes | No | Standard |
| **D** | Assembly Only | No | No | Yes | Standard |
| **E** | Contra + Coverage | Yes | Yes | No | Extended |
| **F** | Contra + Assembly | Yes | No | Yes | Extended |
| **G** | Coverage + Assembly | No | Yes | Yes | Extended |
| **H** | Full S14 Resolution | Yes | Yes | Yes | Extended |
