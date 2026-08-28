# Aryntra Synapse — S10 Experiment Query Set

This query set is designed to test the adaptive decision boundary of the S10 Adaptive Strategy Selector. It consists of queries partitioned by structural complexity, keyword density, and expected relevance profiles.

## 1. Simple / Low-Complexity Queries
*Expected to route to **LIGHT** path on Candidates A, D, and E.*

* **Q1:** "What is Synapse?"
* **Q2:** "Version list"
* **Q3:** "Ollama mistral"
* **Q4:** "Chunk size"
* **Q5:** "Health check"

## 2. Moderate / Standard Queries
*Expected to route to **STANDARD** path on most candidates.*

* **Q6:** "How does the progressive context expansion handle tokens?"
* **Q7:** "What are the priority scores for high priority classes?"
* **Q8:** "How does semantic gate bypass work in Sprint 9?"
* **Q9:** "Explain the deduplication in S7 evidence reuse."
* **Q10:** "How to configure embedding cache max size?"

## 3. Highly Complex / Multi-Concept Queries
*Expected to route to **DEEP** path on Candidates A, D, and E.*

* **Q11:** "Detail the mathematical formulation of priority score blending semantic, lexical, and reuse signals with alpha beta gamma parameters."
* **Q12:** "Compare the performance of the lexical semantic gate in cold and warm cache scenarios, highlighting the latency reduction and upstream routing fidelity."
* **Q13:** "Explain the complete end-to-end context-engineering pipeline starting from FAISS retrieval through workspace deduplication, priority routing, sufficiency gates, and sentence-level compression."

## 4. Evaluation Scenarios
To evaluate Candidates B (Cache-Aware) and C (Reuse-Aware), the benchmark runner executes:
* **Cold Cache Run:** Clear caches before execution.
* **Warm Cache Run:** Execute the same query set sequentially without clearing the cache.
* **Novel Content Run:** Clear S7 Evidence Store.
* **Repeated Content Run:** Execute duplicate queries sequentially to measure S7-driven selection.