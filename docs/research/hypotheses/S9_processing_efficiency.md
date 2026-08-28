# Research Hypothesis: S9 Evidence Processing Efficiency

## Core Hypothesis
By utilizing a hierarchy of checks—using cheap, local lexical keyword metrics first to resolve obvious cases, combined with dual-layer (query + chunk) in-memory vector caches—we can skip up to 80% of deep neural embedding evaluations without altering the downstream prioritization ranking or harming sufficiency decisions.

## Mathematical Formulation
Let $Q$ be the query and $E$ be an evidence chunk.
Let $S_{lex}(Q, E)$ be the cheap Jaccard overlap score.
We define thresholds $\tau_{low} = 0.05$ and $\tau_{high} = 0.60$.

The gating decision function is:
$$
\text{NeedsSemantic}(Q, E) = 
\begin{cases} 
\text{False} & \text{if } S_{lex}(Q, E) \le \tau_{low} \text{ or } S_{lex}(Q, E) \ge \tau_{high} \\
\text{True} & \text{otherwise}
\end{cases}
$$
