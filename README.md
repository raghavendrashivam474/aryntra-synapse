# Aryntra Synapse

**Adaptive Context Engineering Framework for Knowledge-Augmented Language Models**

Aryntra Synapse is a research-oriented framework for investigating how retrieved context can be constructed, represented, compressed, and progressively expanded before being supplied to a local language model.

The project begins with a conventional RAG baseline and incrementally evaluates additional context-engineering strategies.

## Current Status

**Current Sprint:** S2 — Context Compression  
**Current Release:** `v0.4.0`  
**Status:** S2 Complete and Frozen

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

Synapse investigates how retrieved context can be constructed,
represented, compressed, and progressively expanded before being
supplied to a language model.

Completed experiments:

- Structured context representation
- Context compression

Current research direction:

- Bounded progressive context expansion
- Adaptive / hybrid context strategies

Each major experiment is evaluated against controlled baselines.

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
```
Sprint reports and research documentation are maintained under docs/.

Roadmap

S0.1  Project Foundation              ✓
S0.2  Conventional RAG Baseline       ✓  v0.2.0
S1    Context Representation          ✓  v0.3.0
S2    Context Compression             ✓  v0.4.0
S3    Progressive Expansion           → Next
S4    Adaptive / Hybrid Strategies    → Planned

```
```
## Experimental Results

### S1 — Structured Context Representation

S1 increased average context size by 38.17% and aggregate
generation latency by 54.08% compared with the frozen baseline.
The experiment produced potentially improved evidence-aware
behavior on some queries, but overall answer-quality improvement
remained inconclusive.

### S2 — Context Compression

S2 reduced average context size by 34.42% and aggregate generation
latency by 24.41% compared with its flat-context control. All 10
queries were faster in the recorded experiment, with no observed
answer-fidelity or refusal regressions.

S2 is frozen under release `v0.4.0`.
```
Project Status

Research / Experimental

Not intended as a production-ready RAG platform at this stage.
