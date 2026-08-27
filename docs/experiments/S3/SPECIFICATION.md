# S3 Specification — Progressive Context Expansion

## Status: FROZEN SPECIFICATION
## Sprint: S3
## Frozen Predecessor: v0.4.0 (S2 Context Compression)
## Control Baseline: Static compressed_v1 pipeline (Top-K = 3)

---

## 1. Research Question
Can context be progressively expanded only when additional evidence is required, reducing unnecessary initial context while preserving answer quality?

## 2. Working Hypothesis
A bounded progressive context strategy can reduce the initial context supplied to the LLM while maintaining answer quality by introducing additional retrieved evidence only when necessary.

## 3. Expansion Policy
- **Top-K Retrieval Budget**: 3 (from existing FAISS retriever)
- **Initial Chunk Exposure**: 1 chunk (highest similarity score)
- **Max Expansion Steps**: 2 (Stage 1 -> Stage 2 -> Stage 3)
- **Bounded Limit**: At Stage 3 (all Top-K chunks exposed), the system terminates expansion and proceeds directly to final answer generation.

## 4. Sufficiency Protocol
After constructing the active context representation (using deterministic compressed_v1 rules), the LLM is queried with a binary sufficiency instruction:
Given the following evidence and the user's question, do you have enough information to provide a complete and accurate answer?

Question: {query}

Evidence:
{context}

Respond with exactly one word: SUFFICIENT or INSUFFICIENT

text

- If SUFFICIENT: Terminate expansion; generate final answer.
- If INSUFFICIENT: Promote the next retrieved chunk (e.g. C1 -> C1 + C2); repeat.
- Every sufficiency call is recorded as an independent model call and its latency is accounted for.

## 5. Lifecycle & Context Accounting
Every request records:
1. initial_context_length (characters of Stage 1 context)
2. inal_context_length (characters of final context delivered to generation)
3. peak_context_length (largest context in any single LLM invocation)
4. cumulative_context_length (sum of context characters processed across all sufficiency and generation calls)
5. expansion_steps (0, 1, or 2)
6. 	otal_model_calls (1 for static, 1..3 for progressive)
7. Latency breakdown: retrieval, sufficiency, generation, total.
