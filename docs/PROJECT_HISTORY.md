# Aryntra Synapse â€” Project History

> Chronological record of the development, experimentation, and research
> evolution of Aryntra Synapse.

---

## 1. Project Identity

**Project:** Aryntra Synapse

**Research Direction:** Context Engineering for Knowledge-Augmented
Language Models

**Current Release:** `v0.3.0`

**Current Status:** S1 complete and frozen

**Repository:**
`github.com/raghavendrashivam474/aryntra-synapse`

---

## 2. Research Motivation

Aryntra Synapse is a research-oriented system for investigating how
retrieved information can be represented, transformed, compressed,
and progressively supplied to a language model.

The project does not treat retrieval alone as the complete problem.

Instead, it investigates the layer between:

    Retrieved Evidence
            â†“
    Context Representation
            â†“
    Language Model
            â†“
          Answer

The long-term objective is to understand whether context can be made
more useful, efficient, and adaptive without unnecessarily increasing
computational cost.

---

## 3. Experimental Philosophy

Synapse follows a controlled experimental approach.

The primary principles are:

    1. Establish a measurable baseline.
    2. Freeze the baseline.
    3. Change one major experimental variable at a time.
    4. Keep other conditions controlled wherever practical.
    5. Measure both benefits and costs.
    6. Preserve experimental artifacts.
    7. Record limitations and unexpected results.
    8. Let evidence determine the next experiment.

A failed or inconclusive experiment is considered a valid research
outcome if it produces useful evidence for subsequent work.

---

# 4. Sprint 0.2 â€” Conventional RAG Baseline

## 4.1 Objective

Sprint 0.2 established the initial conventional Retrieval-Augmented
Generation pipeline and froze it as the experimental control for
future Synapse research.

## 4.2 Baseline Architecture

    User Query
        â†“
    Sentence Transformers
        â†“
    FAISS Retrieval
        â†“
    Top-K Retrieved Chunks
        â†“
    Flat Context Assembly
        â†“
    Ollama / Mistral
        â†“
    Generated Answer

## 4.3 Technology

The baseline uses:

    - FastAPI
    - Sentence Transformers
    - all-MiniLM-L6-v2
    - FAISS
    - NumPy
    - Ollama
    - Mistral

The embedding model produces 384-dimensional embeddings.

## 4.4 Baseline Dataset

The baseline used the controlled knowledge source:

    data/sample.txt

The source contains 10 indexed chunks during baseline operation.

The knowledge source covers concepts including:

    - Retrieval-Augmented Generation
    - FAISS
    - Sentence Transformers
    - Ollama
    - Mistral
    - Chunking
    - Baseline / experimental control

## 4.5 Baseline Testing

The baseline included:

    - automated test suite
    - API tests
    - retrieval tests
    - manual end-to-end testing

The recorded automated test result was:

    47 passed
    0 failed

A dedicated manual diagnostic script was also created for observing:

    - health status
    - retrieval behavior
    - retrieved chunks
    - retrieval latency
    - generation latency
    - total latency
    - context size
    - edge-case behavior

## 4.6 Baseline Release

The conventional RAG baseline was frozen as:

    v0.2.0

This release became the control condition for subsequent
experiments.

---

# 5. Research Foundation

After establishing the baseline, Synapse research documentation was
created before implementing the first experimental intervention.

The research foundation established:

    - research questions
    - experimental hypotheses
    - experiment specifications
    - controlled query sets
    - research notes
    - future paper structure

The first experimental query set was defined as:

    S1 Query Set v1

It contains 10 controlled queries across five categories:

    1. Direct factual
    2. Multi-chunk factual
    3. Relationship / multi-hop
    4. Synthesis / comparison
    5. Unanswerable / out-of-context

The query set was fixed so that experimental variants could be
compared under consistent conditions.

---

# 6. Sprint 1 â€” Structured Context Representation

## 6.1 Research Question

S1 investigated:

> Does structured representation of retrieved context improve the
> usefulness of context supplied to the LLM compared with flat
> Top-K context?

## 6.2 Hypothesis

The working hypothesis was that preserving meaningful relationships
between retrieved chunks could improve how the language model uses
retrieved evidence.

The hypothesis was treated as experimental rather than assumed to
be true.

## 6.3 Experimental Boundary

S1 deliberately did not modify the retrieval system.

The following remained controlled:

    - knowledge source
    - query wording
    - query order
    - embedding model
    - FAISS retrieval
    - Top-K
    - LLM model
    - evaluation procedure

The primary experimental change was:

    Flat Context
        â†“
    Structured Context Representation

## 6.4 Architectural Change

The representation layer was separated from retrieval and generation.

The conceptual pipeline became:

    User Query
        â†“
    Retriever
        â†“
    Retrieved Chunks
        â†“
    Context Representation
        â†“
    LLM
        â†“
    Answer

S1 introduced a representation abstraction allowing the context
construction strategy to be changed independently of retrieval.

Two representation modes were established:

    Flat representation
        Control-compatible representation

    Structured_v1
        Experimental representation

## 6.5 Baseline Control for S1

Before evaluating the intervention, the frozen `v0.2.0` baseline was
executed against S1 Query Set v1.

The resulting control record was preserved as:

    experiments/S1_baseline_results_v1.json

This provided the reference measurements for the S1 experiment.

## 6.6 S1 Experimental Evaluation

The structured representation was evaluated using the same:

    - 10 queries
    - knowledge source
    - Top-K configuration
    - embedding model
    - LLM configuration
    - evaluation procedure

The experimental record was preserved as:

    experiments/S1_results_v1.json

---

# 7. S1 Results

## 7.1 Retrieval

Retrieval was intentionally left unchanged.

Therefore, the experiment primarily measured the effects of changing
context representation after retrieval.

## 7.2 Context Size

The baseline context length was:

    1570 characters

The S1 structured representation produced contexts ranging from:

    2068 â€” 2288 characters

Therefore, structured representation increased the amount of context
supplied to the language model.

## 7.3 Representation Cost

The recorded representation-build latency was approximately:

    0.002 seconds

This indicates that the representation construction itself was
relatively inexpensive compared with model generation.

## 7.4 Generation Latency

S1 generation latency increased on 9 of the 10 evaluation queries.

The only query where S1 generation latency was lower was:

    Q6

Recorded generation latency:

    Baseline: 47.759 seconds
    S1:       41.104 seconds

Other queries generally showed increased generation latency under
the structured representation.

## 7.5 Qualitative Answer Observations

The experiment produced qualitative differences in several answers.

For Q4, the S1 response explicitly referred to evidence sources
within the structured context.

For Q6, the baseline produced an incorrect and speculative
description of component roles, while S1 produced a more
conservative response indicating that the supplied context did not
provide sufficient evidence.

For Q9 and Q10, both approaches correctly avoided inventing answers
outside the supplied knowledge source.

---

# 8. S1 Interpretation

The S1 experiment demonstrated that context representation can be
changed independently of retrieval and can alter how retrieved
evidence is presented to the language model.

However, the experiment did not establish an overall answer-quality
advantage for structured context.

The clearest measured effects were:

    Context size       â†‘
    Generation cost    â†‘
    Retrieval           â‰ˆ unchanged
    Representation cost Low

Some queries also showed potentially improved evidence-aware or
conservative behavior.

Because no formal human answer-quality scoring was performed, the
qualitative answer differences cannot be treated as a statistically
established improvement.

The S1 result is therefore recorded as:

    PARTIALLY SUPPORTED / INCONCLUSIVE

---

# 9. S1 Limitation

The primary limitations of S1 were:

    - small controlled knowledge source
    - 10-query evaluation set
    - absence of formal human answer-quality scoring
    - increased context size
    - increased generation latency
    - limited experimental scope

These limitations are preserved as part of the research record.

---

# 10. S1 Research Implication

S1 produced an important design observation:

> Adding useful structure to retrieved context can introduce
> additional context and generation cost.

This motivates the next research direction:

    Preserve useful information
            â†“
    Reduce unnecessary context
            â†“
    Reduce generation cost

This provides the experimental motivation for S2.

---

# 11. Release Milestones

| Milestone | Description | Status |
|---|---|---|
| `v0.2.0` | Conventional RAG baseline | ðŸ”’ Frozen |
| S1 foundation | Research questions, hypothesis, specification, query set | âœ… |
| S1 control | Frozen baseline evaluation | âœ… |
| S1 implementation | Structured context representation | âœ… |
| S1 evaluation | Baseline vs structured representation | âœ… |
| S1 findings | Evidence-based research record | âœ… |
| `v0.3.0` | S1 experiment complete | ðŸ”’ Frozen |

---

# 12. Current Research Position

At the end of S1, Synapse has established:

    Conventional RAG
            â†“
    Controlled experimentation
            â†“
    Context representation as an
    independent architectural layer
            â†“
    Measured structured-context experiment
            â†“
    Evidence of a cost / usefulness trade-off

The project has therefore moved from:

    "building a RAG system"

toward:

    "experimentally investigating how context should be
     represented and supplied to language models."

---

# 13. Next Research Direction

The next planned experiment is S2.

The working direction is:

    S1 Structured Context
            â†“
    Context Compression
            â†“
    Reduced context cost
            while attempting to preserve
            useful evidence

S2 will be specified and evaluated independently.

No S2 conclusions are recorded in this document until the experiment
has been performed.

---

# 14. Paper Development Status

The project is currently in the evidence-collection phase.

The full research paper is intentionally not finalized yet.

Current strategy:

    Experiment
        â†“
    Evidence
        â†“
    Research Finding
        â†“
    Historical Record
        â†“
    Accumulated Research Story
        â†“
    Formal Paper

S0.2 and S1 provide the first substantive experimental records.

Future experiments will add evidence before the final paper narrative
is constructed.

---

# 15. Chronological Summary

    S0.2
      â”‚
      â”œâ”€â”€ Conventional RAG baseline established
      â”œâ”€â”€ FAISS retrieval implemented
      â”œâ”€â”€ MiniLM embeddings established
      â”œâ”€â”€ Ollama / Mistral generation established
      â”œâ”€â”€ Automated tests completed
      â””â”€â”€ v0.2.0 frozen
             â”‚
             â–¼
    Research Foundation
      â”‚
      â”œâ”€â”€ Research questions
      â”œâ”€â”€ Hypotheses
      â”œâ”€â”€ S1 specification
      â””â”€â”€ S1 Query Set v1
             â”‚
             â–¼
    S1
      â”‚
      â”œâ”€â”€ Baseline control recorded
      â”œâ”€â”€ Structured representation implemented
      â”œâ”€â”€ Baseline and S1 evaluated
      â”œâ”€â”€ Results preserved
      â””â”€â”€ Findings documented
             â”‚
             â–¼
    v0.3.0
      â”‚
      â””â”€â”€ S1 frozen
             â”‚
             â–¼
    S2
      â”‚
      â””â”€â”€ Context compression research

---
**Document Status**

**Document type**: Project historical record

**Coverage**: Project origin through S1 / v0.3.0

**Status**: Living document

Future completed sprints should append to this history without
rewriting historical findings except when a factual correction is
required.
## Sprint 8 — Evidence Relevance & Priority Management
- **Release**: 1.0.0
- **Capabilities Added**:
  - EvidencePriorityEngine with deterministic semantic, lexical, and S7 reuse scoring signals.
  - Three-tier classification (HIGH, MEDIUM, LOW) and active/retained workspace partitioning.
  - Priority initial promotion in EvidenceWorkspace.
  - Full ablation evaluation across Semantic-only, Lexical-only, Semantic+Lexical, and Full Blend.
  - Live /ask endpoint priority observability and accounting metrics.
- **Tests**: 149/149 passing (10 new S8 tests, 0 regressions).

## Sprint 9 â€” Evidence Processing Efficiency
- **Release**: `v1.1.0`
- **Capabilities Added**:
  - `EmbeddingCache`: Thread-safe, fingerprint-keyed LRU caching for query and evidence chunk vector embeddings.
  - `LexicalSemanticGate`: Jaccard-based lexical pre-filter that routes obvious high/low relevance chunks around deep embedding models.
  - S9 Integration in `EvidencePriorityEngine`: Conditional semantic evaluation and vector reuse.
  - Full API telemetry exposure for semantic calls, cache hits/misses, and gate fast-path hit rates.
  - 6-configuration ablation benchmark validating that Exp E (Full Blend) slashes priority latency by 68.8% cold and 99.7% warm.
- **Tests**: 158/158 passing (19 new tests, 0 regressions).

## Sprint 10 — Adaptive Evidence Strategy Selection (v1.2.0)
* **Status:** Completed
* **Tests:** 179 / 179 passing
* **Core Contribution:**
  * Implemented deterministic adaptive strategy selector (pp/strategy/).
  * Evaluated 5 candidate routing strategies (Lexical Complexity, Cache Warmth, Reuse Confidence, Priority Pre-screen, Composite Score).
  * Selected Candidate E (Composite) as Primary and Candidate D (Pre-screen) as Fallback.
  * Achieved 68.4% priority latency reduction and 40.8% total query latency reduction across benchmark workloads.
  * Added full observability telemetry to /ask and /health endpoints.