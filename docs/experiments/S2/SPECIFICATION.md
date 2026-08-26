# S2 Specification — Context Compression

## Status
Draft → **Approved** → In Progress → Complete

## Version
v1

## Date
2026-08-26

---

## 1. Research Question

> Can useful contextual information be retained while reducing the
> amount of context supplied to the language model?

## 2. Motivation (from S1)

S1 introduced structured context representation (structured_v1).
Results showed:

| Metric | Baseline | S1 | Delta |
|---|---|---|---|
| Avg context length | 1570 chars | 2169 chars | +38.17% |
| Total gen latency | 317.77s | 489.63s | +54.08% |

Representation construction was negligible in cost.
The latency increase came from the LLM processing more tokens.

S2 investigates whether we can reduce context volume
**after retrieval** while preserving answer quality.

## 3. Hypothesis

> Selective context compression can reduce context size and
> generation latency while preserving sufficient evidence for
> answering the controlled query set.

## 4. Variables

### Fixed (inherited from S1 baseline)
- Knowledge source: data/sample.txt
- Embedding model: ll-MiniLM-L6-v2
- Retriever: FAISS
- Top-K: 3
- LLM: Ollama / Mistral
- Query set: S1 Query Set v1 (10 queries, unchanged)
- Query wording and ordering

### Independent Variable
- Context representation method:
  - **Control:** lat (existing baseline)
  - **Experiment:** compressed_v1 (S2 intervention)

### Dependent Variables
- Context length (characters)
- Compression ratio
- Generation latency (seconds)
- Total pipeline latency (seconds)
- Answer quality (categorical score)
- Number of model calls

## 5. Compression Algorithm: compressed_v1

A deterministic, rule-based compressor applied **after** retrieval
and **before** generation.

### Steps

1. **Whitespace normalization**
   - Collapse runs of 3+ newlines to 2.
   - Strip leading/trailing whitespace per chunk.

2. **Sentence-boundary truncation**
   - Each chunk is truncated to a maximum of MAX_CHUNK_CHARS
     characters (default: 400).
   - Truncation occurs at the last sentence boundary (., !, ?)
     that falls within the limit.
   - If no sentence boundary exists within the limit, hard-truncate
     at MAX_CHUNK_CHARS and append ....

3. **Structural marker removal**
   - Remove S1-style structural headers (e.g., [Source: ...],
     [Relevance: ...]) if present, since S2 operates on the
     lat representation as its control baseline.

4. **Deduplication across chunks**
   - If two chunks share a sentence with >90% character overlap,
     retain the sentence only in the higher-scored chunk.

### Configuration
CONTEXT_REPRESENTATION=compressed_v1
S2_MAX_CHUNK_CHARS=400
S2_DEDUP_THRESHOLD=0.90

text


### Determinism guarantee

Given identical input chunks, the compressor produces
byte-identical output. No randomness, no LLM calls.

## 6. Control

The control run uses the existing lat representation
with no compression. This is identical to the S0.2/S1
baseline behavior.
CONTEXT_REPRESENTATION=flat

text


## 7. Evaluation Method

### 7.1 Quantitative

For each of the 10 queries, measure:
- Original context length vs compressed context length
- Compression ratio
- Generation latency
- Total latency

### 7.2 Qualitative (Answer Quality)

Each answer is scored on a 5-category rubric:

| Score | Label | Definition |
|---|---|---|
| 5 | Correct | Fully accurate, well-supported |
| 4 | Partially correct | Core answer right, minor gaps |
| 3 | Incomplete | Some relevant info, missing key points |
| 2 | Incorrect | Factually wrong or misleading |
| 1 | Hallucinated | Unsupported claims, fabricated info |
| 0 | Appropriate refusal | Correctly identifies insufficient evidence |

For Q9-Q10 (unanswerable), score 0 is the **target**.

### 7.3 Scoring protocol

- Rubric is defined **before** inspecting results.
- Both control and experiment answers are scored
  without knowing which is which (blind if possible).

## 8. Success / Failure Criteria

### Engineering success (all required)
- [ ] Compressor is deterministic
- [ ] Compressor reduces context size on ≥8/10 queries
- [ ] All existing tests pass
- [ ] Baseline lat behavior unchanged
- [ ] Experiment is reproducible from repo

### Research outcomes (any is valid)
- **Supported:** Context ↓ ≥20%, quality preserved (avg score ≥ control)
- **Trade-off:** Context ↓, quality ↓ — compression has a cost
- **Null:** No meaningful difference in either metric
- **Surprise:** Context ↓, quality ↑ — noise reduction effect

## 9. Limitations

- Single knowledge source (sample.txt)
- Single LLM (Mistral via Ollama)
- Small query set (n=10)
- Rule-based compression only (no learned models)
- No reranking or retrieval changes
- Results may not generalize to larger corpora

## 10. Out of Scope

- Modifying the retriever or FAISS index
- Changing the embedding model
- Introducing a second LLM for summarization
- Reranking models
- Graph-based retrieval
- Learned / neural compression
- Changing the query set wording

---

## Approval

| Role | Name | Date | Status |
|---|---|---|---|
| Research Lead | | | Pending |
| Senior Dev | | | Pending |
