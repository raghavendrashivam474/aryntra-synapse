# S1 — Research Findings

## Experiment

Structured Context Representation

## Research Question

Does structured representation of retrieved context improve the
usefulness of context supplied to the LLM compared with flat
Top-K context?

## Control

The frozen v0.2.0 conventional RAG pipeline.

The control used:

- FAISS retrieval
- all-MiniLM-L6-v2 embeddings
- Top-K = 3
- Ollama / Mistral
- S1 Query Set v1

## Intervention

S1 introduced `structured_v1` context representation while
leaving the retrieval stage unchanged.

## Dataset

S1 Query Set v1 containing 10 controlled queries across:

- direct factual
- multi-chunk factual
- relationship / multi-hop
- synthesis / comparison
- unanswerable / out-of-context

Knowledge source:

`data/sample.txt`

## Measurements

Retrieval behavior remained effectively unchanged because S1
operated after retrieval.

The baseline produced a context length of 1570 characters for
each query.

S1 produced contexts between 2068 and 2288 characters, increasing
the context supplied to the LLM.

Representation construction itself was inexpensive, with measured
build latency around 0.002 seconds in the recorded experiment.

Generation latency increased on 9 of the 10 queries. Q6 was the
only query where S1 generation latency was lower than the baseline.

The measured generation latency changes were:

| Query | Baseline | S1 |
|---|---:|---:|
| Q1 | 50.571s | 71.384s |
| Q2 | 20.930s | 36.103s |
| Q3 | 34.477s | 49.286s |
| Q4 | 28.755s | 44.653s |
| Q5 | 23.231s | 36.962s |
| Q6 | 47.759s | 41.104s |
| Q7 | 44.119s | 94.876s |
| Q8 | 31.274s | 43.347s |
| Q9 | 17.257s | 33.934s |
| Q10 | 19.400s | 37.975s |

## Observations

S1 produced qualitatively different answers on several queries.

For Q4, the S1 response explicitly referred to evidence sources
within the structured context.

For Q6, the baseline produced an incorrect and speculative
description of component roles, while S1 produced a more
conservative response stating that the supplied context did not
provide sufficient evidence.

For Q9 and Q10, both approaches correctly avoided inventing
answers to out-of-context questions.

These observations suggest that structured context may influence
grounding behavior, but the current experiment does not provide
enough evidence to quantify an overall answer-quality improvement.

## Limitations

The S1 evaluation used only 10 queries and a small controlled
knowledge source.

No formal human answer-quality scoring was included in this
experiment.

Therefore, qualitative differences should not be interpreted as
statistically established improvements.

The increase in context size also introduces additional generation
cost, making latency an important trade-off for future experiments.

## Finding

S1 demonstrates that context representation can be changed
independently of retrieval and can alter how the LLM interprets
retrieved evidence.

However, the current results do not establish that structured
context is superior to flat context overall.

The clearest measured effect is an increase in context size and
generation latency, while some queries show potentially improved
evidence-aware or conservative behavior.

Therefore, the S1 hypothesis is considered:

**PARTIALLY SUPPORTED / INCONCLUSIVE**

with respect to answer-quality improvement.

## Implication for Synapse

Future experiments should investigate whether the benefits of
structured context can be retained while reducing context
expansion and generation cost.

This motivates investigation of context compression and selective
context representation in subsequent experiments.