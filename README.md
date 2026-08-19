# Aryntra Synapse

**Adaptive Context Engineering Framework for Knowledge-Augmented Language Models**

Aryntra Synapse is a research-oriented framework for investigating how retrieved context can be constructed, represented, compressed, and progressively expanded before being supplied to a local language model.

The project begins with a conventional RAG baseline and incrementally evaluates additional context-engineering strategies.

## Current Status

**Sprint:** S0.2 — Baseline RAG Reconstruction  
**Version:** `v0.2.0`  
**Status:** Baseline Frozen

### Baseline

```text
User Query
    ↓
Sentence Transformers
    ↓
FAISS Top-K Retrieval
    ↓
Context Assembly
    ↓
Ollama / Mistral
    ↓
Answer
```
The v0.2.0 baseline is the control implementation for future Synapse experiments.

Research Direction

Future experiments will investigate:

Relationship-aware context
Structured context representation
Context compression
Bounded progressive context expansion
Adaptive / hybrid strategies

Each major experiment will be evaluated against the frozen baseline.

Technology Stack
Python 3.12+
FastAPI
Sentence Transformers
FAISS
Ollama
NumPy
Pandas
Pytest
Git / GitHub
```
Repository Structure
aryntra-synapse/
├── app/
│   ├── api/
│   ├── core/
│   ├── llm/
│   └── retrieval/
├── data/
├── experiments/
├── tests/
├── docs/
├── main.py
├── requirements.txt
└── README.md

```
---

Development Principle

Synapse is developed experimentally.

The baseline is kept simple and reproducible so that future changes can be evaluated independently rather than assuming that additional complexity produces better results.

---

Documentation

Sprint reports and research documentation are maintained under docs/.

Roadmap
S0.1  Project Foundation              ✓
S0.2  Conventional RAG Baseline      ✓
S1    Context Representation          → Next
S2    Context Compression             → Planned
S3    Progressive Expansion           → Planned
S4    Adaptive / Hybrid Strategies    → Planned
Project Status

Research / Experimental

Not intended as a production-ready RAG platform at this stage.
