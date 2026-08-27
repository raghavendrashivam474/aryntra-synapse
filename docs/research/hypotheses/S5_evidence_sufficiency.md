# S5 Hypothesis - Evidence Sufficiency and Selective Promotion

## Core Hypothesis
Lightweight deterministic sufficiency signals (retrieval score + keyword
coverage) can identify when active evidence is sufficient, enabling early
termination of progressive expansion and reducing unnecessary model calls.

## Expected Outcomes
- **Strong Support**: Early-stop rate > 40%, model calls reduced, quality preserved.
- **Partial Support**: Some early stops, modest call reduction, quality preserved.
- **No Improvement**: Sufficiency signals fail to discriminate, all queries expand to max.
- **Negative**: False sufficiency causes answer quality degradation.