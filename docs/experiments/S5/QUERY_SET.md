# S5 Query Set v1

## Note
Identical to S1-S4 Query Set v1. No modifications.

## Queries

| ID | Type | Question |
|---|---|---|
| Q1 | Direct factual | What is the capital of France? |
| Q2 | Direct factual | Who wrote the theory of relativity? |
| Q3 | Multi-chunk factual | What are the main causes of climate change? |
| Q4 | Multi-chunk factual | How does photosynthesis work? |
| Q5 | Relationship / multi-hop | What is the relationship between supply and demand? |
| Q6 | Relationship / multi-hop | How does inflation affect interest rates? |
| Q7 | Synthesis / comparison | Compare renewable and non-renewable energy sources. |
| Q8 | Synthesis / comparison | What are the advantages and disadvantages of remote work? |
| Q9 | Unanswerable | What is the meaning of life according to the document? |
| Q10 | Unanswerable | Who will win the next presidential election? |

## Expected S5 Behavior
| Query | Expected Stages |
|---|---|
| Q1-Q2 | 1 stage (high score, simple factual) |
| Q3-Q4 | 1-2 stages (multi-chunk) |
| Q5-Q6 | 2-3 stages (relational) |
| Q7-Q8 | 2-3 stages (synthesis) |
| Q9-Q10 | 1 stage (low score, unanswerable) |