# S6 Query Set v1 (Synapse Domain)

## Knowledge Source
Evaluated against `data/sample.txt` (Sprint 0.2 Baseline Knowledge Source).

## Queries

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

## Theoretical Sufficiency Bounds
- **Q1, Q2, Q8**: Grounded in 1 chunk -> Expected Stage 1 early stop.
- **Q3, Q4, Q5, Q6, Q7**: Require multi-chunk / relational synthesis -> Expected Stage 2-3 expansion.
- **Q9, Q10**: Unanswerable -> Must not trigger false early stop.
