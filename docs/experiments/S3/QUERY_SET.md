# S3 Query Set v1

## Note
This query set is **identical** to S1 and S2 Query Set v1.
No wording, ordering, or prompt modifications are introduced.

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

## Expected Behavior Key

| Query | Expected Progression Target |
|---|---|
| Q1-Q2 | Stage 1 (1 Chunk) sufficient |
| Q3-Q4 | Stage 2 or 3 required (Multi-chunk factual) |
| Q5-Q6 | Stage 2 or 3 required (Relational / multi-hop) |
| Q7-Q8 | Stage 2 or 3 required (Synthesis / comparison) |
| Q9-Q10 | Stage 1 sufficient to declare unanswerable / missing evidence |
