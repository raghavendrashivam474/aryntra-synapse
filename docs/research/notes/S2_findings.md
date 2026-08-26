# S2 Findings — Context Compression

## Date
2026-03-31

## Status
Complete / Validated

---

## 1. Executive Summary

Sprint 2 evaluated the **Selective Context Compression** hypothesis:
> Can retrieved context volume be deterministically reduced prior to LLM generation while preserving useful evidence and improving generation latency?

The experimental intervention (`compressed_v1`) introduced:
1. Whitespace & delimiter normalization
2. Structural marker removal
3. Sentence-boundary truncation (400 char cap per chunk)
4. Cross-chunk sentence deduplication (90% similarity threshold)

The intervention resulted in:
- **-34.42% context volume reduction** (1,435.6 → 941.4 characters)
- **-24.41% aggregate generation latency reduction** (228.69s → 172.87s)
- **10/10 queries faster** with 0 latency regressions
- **38ms average compression overhead** (negligible vs 5.58s average latency savings per query)
- **Zero evidence degradation** on factual and synthesis queries; appropriate refusal preserved on unanswerable queries.

The hypothesis is **strongly supported**.

---

## 2. Quantitative Comparison

| Metric | Baseline (`flat`) | S2 (`compressed_v1`) | Absolute Delta | Percentage Delta |
|---|---:|---:|---:|---:|
| **Avg Context Length (chars)** | 1435.6 | 941.4 | -494.2 chars | **-34.42%** |
| **Total Gen Latency (s)** | 228.686s | 172.869s | -55.817s | **-24.41%** |
| **Avg Gen Latency (s)** | 22.869s | 17.287s | -5.582s | **-24.41%** |
| **Total Pipeline Latency (s)** | 229.009s | 173.524s | -55.485s | **-24.23%** |
| **Avg Pipeline Latency (s)** | 22.901s | 17.352s | -5.549s | **-24.23%** |
| **Avg Rep Build Latency (s)** | 0.000015s | 0.038036s | +0.038021s | +38.0ms |

---

## 3. Per-Query Breakdown

| ID | Query Category | Base Ctx | S2 Ctx | Reduction | Base Gen (s) | S2 Gen (s) | Gen Delta | Quality Preservation |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| **Q1** | Direct factual | 1570 | 983 | 37.4% | 41.420 | 26.976 | -34.87% | Preserved |
| **Q2** | Direct factual | 1570 | 961 | 38.8% | 24.264 | 15.476 | -36.22% | Preserved |
| **Q3** | Multi-chunk factual | 1570 | 1066 | 32.1% | 22.501 | 21.358 | -5.08% | Preserved |
| **Q4** | Multi-chunk factual | 1570 | 976 | 37.8% | 20.985 | 15.909 | -24.19% | Preserved |
| **Q5** | Relationship / multi-hop | 1570 | 997 | 36.5% | 21.373 | 17.094 | -20.02% | Preserved |
| **Q6** | Relationship / multi-hop | 1122 | 724 | 35.5% | 23.049 | 11.993 | -47.97% | Preserved |
| **Q7** | Synthesis / comparison | 1122 | 773 | 31.1% | 18.258 | 13.502 | -26.05% | Preserved |
| **Q8** | Synthesis / comparison | 1570 | 1096 | 30.2% | 20.128 | 18.823 | -6.48% | Preserved |
| **Q9** | Unanswerable | 1570 | 1001 | 36.2% | 24.976 | 21.716 | -13.05% | Refusal preserved |
| **Q10** | Unanswerable | 1122 | 837 | 25.4% | 11.731 | 10.021 | -14.58% | Refusal preserved |

---

## 4. Key Observations

1. **Downstream Latency Decoupling:** S1 showed that richer context increased generation latency by +54.08%. S2 demonstrates the converse: reducing context by -34.42% reduced generation latency by -24.41%. Generation time is strongly bounded by input prompt length on local LLM runtimes.
2. **Computational Asymmetry:** Compression logic execution took an average of **38.0ms** CPU time, while saving an average of **5,582ms** GPU/inference time. Post-retrieval context reduction is a high-leverage optimization.
3. **Evidence Density:** Sentence boundary truncation and cross-chunk deduplication successfully eliminated redundant overlap across retrieved chunks without dropping critical facts.

---

## 5. Synthesis & S3 Recommendation

- **S1 Finding:** Structured representation provides explicit relational topology (+38% context, +54% latency).
- **S2 Finding:** Context compression reduces context (-34% context, -24% latency) without quality degradation.
- **S3 Direction:** **Structured Compressed Context Representation (`structured_compressed_v1`)** — combining the relational graph/continuity metadata of S1 with the compact evidence payload of S2 to achieve high relational clarity at baseline-or-better latency.
