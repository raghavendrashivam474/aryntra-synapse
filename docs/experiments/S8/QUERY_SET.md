# Aryntra Synapse — Sprint 8 Query Set & Ablation Matrix

## Evaluation Queries

1. `Q1` [Architecture]: "What is the core architecture of Aryntra Synapse?"
2. `Q2` [Compression]: "How does context compression reduce token usage?"
3. `Q3` [Workspace]: "What is the role of the evidence workspace in managing context?"
4. `Q4` [Sufficiency]: "How does deterministic sufficiency evaluate keyword coverage?"
5. `Q5` [Reuse]: "What are the benefits of cross-query evidence reuse and fingerprinting?"

## Ablation Matrix

| Configuration | Alpha (Semantic) | Beta (Lexical) | Gamma (Reuse) | Description |
|---|---|---|---|---|
| Control | N/A | N/A | N/A | S7 baseline (unprioritized order) |
| Exp-A | 1.00 | 0.00 | 0.00 | Pure semantic cosine similarity |
| Exp-B | 0.00 | 1.00 | 0.00 | Pure lexical keyword overlap |
| Exp-C | 0.60 | 0.40 | 0.00 | Hybrid semantic + lexical |
| Exp-D | 0.50 | 0.30 | 0.20 | Full blend (Semantic + Lexical + Reuse) |
