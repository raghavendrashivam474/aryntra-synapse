# S3 Hypothesis — Progressive Context Expansion

## Core Hypothesis
A bounded progressive context strategy reduces the initial context supplied to the LLM while maintaining answer quality by introducing additional retrieved evidence only when necessary.

## Success Criteria & Outcomes
- **Outcome A (Strong Support)**: Initial context is reduced by >40%, total answer accuracy is preserved, and cumulative cost is bounded.
- **Outcome B (Partial Support)**: Prompt context size is reduced, but repeated LLM sufficiency calls increase cumulative prompt tokens/latency.
- **Outcome C (Negative Result)**: Model fails to judge sufficiency accurately (false SUFFICIENT or false INSUFFICIENT loops) or answer quality degrades.
