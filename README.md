# Aryntra Synapse

Adaptive Context Engineering Framework for Knowledge-Augmented Language Models.

---

## 1. Project Identity

Aryntra Synapse is a **research-oriented experimental framework**, not a production RAG platform.

Its purpose is to investigate how retrieved evidence can be:
- constructed
- represented
- compressed
- retained
- reused
- prioritized
- progressively expanded
- processed efficiently

before being supplied to a local language model.

---

## 2. Current Project State

As of the latest completed sprint:

| Item | Current State |
| :--- | :--- |
| **Current Sprint** | **S9 — Processing Efficiency** |
| **Current Release** | **`v1.1.0`** |
| **Status** | **S9 Complete and Frozen** |
| **Baseline Control** | **`v0.2.0`** |
| **Local LLM** | Ollama / Mistral |
| **Retrieval Layer** | Sentence Transformers (`all-MiniLM-L6-v2`) + FAISS |
| **API Framework** | FastAPI |
| **Testing Suite** | Pytest (158/158 passing) |
| **Development Mode** | Research / Experimental |

The `v0.2.0` conventional RAG implementation remains the **frozen experimental control**. All subsequent experiments are evaluated relative to that control or their explicitly defined local controls.

---

## 3. Experimental Philosophy

Synapse follows a strict experimental methodology:

1. Maintain a reproducible baseline.
2. Introduce one capability at a time.
3. Measure its effect.
4. Identify its overheads and shortcomings.
5. Compare against an appropriate control.
6. Test promising alternatives individually.
7. Test technically sensible combinations.
8. Compare the resulting trade-offs.
9. Prefer the configuration with the best useful improvement / overhead balance.

> **Core Principle:** More sophisticated does not automatically mean better. The objective is not maximum complexity; it is minimum sufficient context engineering.

---

## 4. Baseline Architecture (v0.2.0 Control)

The original control pipeline is:

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

*Note: This is the frozen baseline/control against which later context-engineering experiments evolved, not the complete current architecture.*

---

## 5. Research Evolution

```text
S0.1  Project Foundation                  ✓
S0.2  Conventional RAG Baseline           ✓  v0.2.0 (Frozen Control)
S1    Context Representation              ✓  v0.3.0
S2    Context Compression                 ✓  v0.4.0
S3    Progressive Expansion               ✓  v0.5.0
S4    Evidence Workspace                  ✓  v0.6.0
S5    Evidence Sufficiency                ✓  v0.7.0
S6    Semantic Sufficiency                ✓  v0.8.0
S7    Evidence Reuse & Deduplication      ✓  v0.9.0
S8    Evidence Relevance & Priority       ✓  v1.0.0
S9    Processing Efficiency               ✓  v1.1.0
```

---

## 6. What Each Sprint Added

### S1 — Context Representation (`v0.3.0`)
Introduced structured representation of retrieved context.
- **Measured Result:** Average context size: **+38.17%**, Aggregate generation latency: **+54.08%**. Answer-quality improvement remained **inconclusive**.
- **Research Lesson:** Additional context structure can change evidence-aware behavior, but it can also introduce substantial context and latency overhead.

### S2 — Context Compression (`v0.4.0`)
Introduced syntactic context pruning and deduplication.
- **Measured Result:** Average context size: **−34.42%**, Aggregate generation latency: **−24.41%**. All 10 recorded queries became faster with no observed regressions in answer fidelity or refusals.

### S3 — Progressive Context Expansion (`v0.5.0`)
Introduced bounded, progressive expansion rather than treating retrieval as a single irreversible context-selection operation.

### S4 — Evidence Workspace (`v0.6.0`)
Introduced a persistent, non-destructive workspace for retained evidence and context management.
- **Key Concept:** Evidence does not have to be immediately promoted into active LLM context or discarded.

### S5 — Evidence Sufficiency (`v0.7.0`)
Introduced deterministic keyword-coverage sufficiency evaluation to reduce unnecessary context expansion.

### S6 — Semantic Sufficiency (`v0.8.0`)
Strengthened sufficiency evaluation with semantic gating to make expansion decisions more context-aware.

### S7 — Evidence Reuse & Deduplication (`v0.9.0`)
Implemented cross-query evidence reuse to prevent repeatedly re-processing encountered text:
- Deterministic SHA-256 evidence fingerprinting and whitespace normalization
- Persistent cross-query evidence store with reuse telemetry
- **Verification:** **119/119 tests passing**.

### S8 — Evidence Relevance & Priority (`v1.0.0`)
Implemented a deterministic priority engine combining semantic similarity, lexical overlap, and S7 reuse signals:

```text
Priority Score = α × Semantic Relevance + β × Lexical Relevance + γ × Reuse Signal
```

Classifies evidence into `HIGH`, `MEDIUM`, and `LOW` tiers to partition active workspace context from retained fallback context.
- **Verification:** **149/149 tests passing**.
- **Ablation Summary:**

| Configuration | α | β | γ | Priority Latency | Sufficiency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Control** | — | — | — | 0.00 ms | 20% |
| **Semantic Only** | 1.0 | 0.0 | 0.0 | 157.11 ms | 20% |
| **Lexical Only** | 0.0 | 1.0 | 0.0 | **0.25 ms** | 20% |
| **Semantic + Lexical** | 0.6 | 0.4 | 0.0 | 139.92 ms | 20% |
| **Full Blend** | 0.5 | 0.3 | 0.2 | 154.36 ms | 20% |

- **Research Lesson:** S8 demonstrated that priority management is possible, but the benchmark did not yet demonstrate a sufficiency-rate improvement over the control.

### S9 — Processing Efficiency (`v1.1.0`)
Addressed the high computational overhead of S8 semantic scoring (~154 ms per query) via lightweight pre-filtering and caching:
- Dual-layer bounded LRU cache for query and chunk embeddings
- Fast-path lexical Jaccard gate to bypass embedding calls for obvious matches/mismatches
- **Verification:** **158/158 tests passing**.
- **Results:** Priority latency reduced by **68.8% on cold queries** and **99.7% on warm queries** (down to 0.40 ms) with 100% downstream routing fidelity.

---

## 7. Current Research Position After S9

Synapse currently operates across the full evidence lifecycle:

```text
       Retrieve (FAISS)
              ↓
       Deduplicate & Reuse (S7)
              ↓
       Pre-Filter Gate & Cache (S9)
              ↓
       Prioritize / Rank (S8)
              ↓
       Assess Sufficiency (S5/S6)
              ↓
       Expand Context (If Insufficient)
              ↓
       Compress Context (S2)
              ↓
       Generate (Ollama)
```

Detailed experimental findings and raw benchmark datasets are maintained in the corresponding sprint reports under `docs/sprints/`.

---

## 8. Repository Structure & Stack

```text
aryntra-synapse/
├── app/
│   ├── api/                   # FastAPI route definitions and telemetry schemas
│   ├── core/                  # Configuration settings, toggles, and tuning thresholds
│   ├── llm/                   # Ollama local inference provider
│   ├── optimization/          # S9 embedding caches and lexical gating modules
│   └── retrieval/             # Embedding layers, chunking rules, and FAISS index
├── data/                      # Sample documents and text inputs
├── docs/                      # Scientific hypotheses, specs, and sprint completion files
│   └── sprints/               # Authoritative reports for S1 through S9
├── experiments/               # Ablation and benchmark execution scripts
├── tests/                     # Test suite (158 passing tests)
├── main.py                    # Application entry point
├── requirements.txt
└── README.md
```

**Technology Stack:**
- Python 3.12+
- FastAPI
- Sentence Transformers
- FAISS
- Ollama / Mistral
- NumPy, Pandas
- Pytest
- Git / GitHub

---

## 9. Getting Started

### Prerequisites
1. Download and run [Ollama](https://ollama.com/) with Mistral:
   ```bash
   ollama run mistral
   ```
2. Initialize virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Running Server & Verification
- **Start API server:** `python main.py` (API docs available at `http://localhost:8000/docs`).
- **Run test suite:** `pytest` (verifies all 158 tests across S1–S9).
- **Run S9 benchmark:** `python experiments/s9_efficiency_ablation.py`.

---

## 10. Project Status

**Research / Experimental**

Not intended as a production-ready RAG platform at this stage. It is an experimental framework for studying how much evidence should be retrieved, retained, reused, prioritized, expanded, compressed, and ultimately exposed to a language model — and what computational and contextual costs those decisions introduce.
```