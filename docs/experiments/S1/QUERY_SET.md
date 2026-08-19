# S1 — Evaluation Query Set

**Version:** v1

**Purpose:** Fixed evaluation set for comparing the frozen `v0.2.0` baseline with S1 context-representation variants.

## Query Set

| ID | Category | Question |
|---|---|---|
| Q1 | Direct factual | What is Retrieval-Augmented Generation (RAG)? |
| Q2 | Direct factual | What embedding model does Synapse use in Sprint 0.2? |
| Q3 | Multi-chunk factual | How do Sentence Transformers and FAISS work together in the Synapse retrieval pipeline? |
| Q4 | Multi-chunk factual | How does a query move from text to retrieved document chunks in the baseline? |
| Q5 | Relationship / multi-hop | Why is chunking necessary, and how does chunk overlap help retrieval? |
| Q6 | Relationship / multi-hop | What roles do FAISS, Sentence Transformers, and Ollama each play in the baseline RAG pipeline? |
| Q7 | Synthesis / comparison | What are the respective purposes of RAG, FAISS, Sentence Transformers, and Ollama in Synapse? |
| Q8 | Synthesis / comparison | Why does Synapse use local Ollama/Mistral instead of relying on cloud-based model APIs during baseline research? |
| Q9 | Unanswerable | What is the population of France? |
| Q10 | Unanswerable | What accuracy percentage did the Synapse baseline achieve in Sprint 0.2? |

## Categories

### Direct Factual

The answer should be directly supported by a relevant chunk.

### Multi-Chunk Factual

The answer requires information from multiple retrieved chunks.

### Relationship / Multi-Hop

The question requires connecting information from multiple parts of the knowledge source.

### Synthesis / Comparison

The question requires combining or comparing multiple concepts or system components.

### Unanswerable / Out-of-Context

The knowledge source does not contain sufficient evidence to answer the question.

The expected behavior is to avoid unsupported claims rather than invent an answer.

## Control Requirements

The same following conditions should be used for both `v0.2.0` and S1 wherever practical:

- Knowledge source
- Query wording
- Query order
- Embedding model
- Top-K configuration
- LLM model and configuration
- Evaluation procedure

## Evaluation Record

For each query, record:

- Retrieved chunk IDs
- Retrieval scores
- Context representation
- Context relevance
- Answer
- Answer quality
- Context/token usage
- Retrieval latency
- Generation latency
- Total latency
- Number of model calls
- Failure observations

## Versioning

This initial query set is `v1`.

The query set must not be selectively changed after observing experimental results. Any modification should create a new version and document the reason for the change.

## Dataset

The queries are designed against the controlled knowledge source:

`data/sample.txt`

The knowledge source should remain unchanged during the initial S1 comparison.