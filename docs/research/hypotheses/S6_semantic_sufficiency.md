# S6 Hypothesis: Semantic Sufficiency

## Primary Hypothesis (H1)
Semantic cosine similarity between query and active evidence provides
a more reliable sufficiency signal than lexical keyword coverage alone,
enabling genuine early stopping without sacrificing answer quality.

## Secondary Hypothesis (H2)
A blended gate requiring BOTH lexical coverage AND semantic similarity
produces fewer false-sufficiency errors than either signal alone,
particularly on unanswerable queries (Q9-Q10).

## Null Hypothesis (H0)
Semantic similarity adds no meaningful improvement over S5's lexical
signals. Early-stop rates remain at 0% or false sufficiency increases
unacceptably.

## Key Risk
False sufficiency: semantic similarity may be high for topically related
but evidentially insufficient chunks (e.g., "X occurred in 2024" is
semantically close to "What caused X?" but does not answer it).

## Falsification
If S6-A (semantic_only) produces false sufficiency on Q9-Q10, the
semantic-only mode is unsafe and only blended mode should be retained.
