---

# ARYNTRA SYNAPSE — SPRINT 17 POST-IMPLEMENTATION REPORT

**To:** Senior Development Lead
**From:** S17 Implementation Team
**Date:** August 2026
**Release:** v1.9.0 (tagged and pushed to `origin/main`)
**Base:** v1.8.0 (S16 Temporal & Version-Aware Evidence Selection)
**Sprint:** S17 — Evidence Relationship Graph & Coherent Evidence Assembly

---

## 1. EXECUTIVE SUMMARY

Sprint 17 introduced a deterministic evidence relationship layer into the Synapse assembly pipeline. The system now constructs an explicit `EvidenceGraph` over candidate evidence chunks, capturing how selected pieces of evidence relate to one another — supersession, contradiction, document identity, temporal adjacency, and version lineage — before and during assembly.

This is an architectural transition, not merely an accuracy improvement. Prior to S17, Synapse evaluated each evidence chunk independently across multiple signal dimensions (relevance, coverage, conflict, sufficiency, temporal validity). S17 adds structural awareness: the system now understands that chunk A supersedes chunk B, that chunks C and D belong to the same document, and that chunks E and F are in factual contradiction — and it uses that structural knowledge to inform candidate ordering and assembly coherence.

**Headline results:** 348/348 tests passing (312 baseline + 36 new), 100% benchmark pass rate across 6 scenarios, 0% false relationship rate, 0.883 ms average relationship overhead. Zero regressions against S14, S15, and S16.

---

## 2. WHAT WAS BUILT

### 2.1 Core Module: `app/evidence/relationships.py`

Three primary constructs:

**`RelationshipType` (Enum)** — A deliberately small vocabulary of 8 relationship types:
- `SUPERSEDES` / `SUPERSEDED_BY`: Version lineage (e.g., policy v3 supersedes v2)
- `CONTRADICTS`: Factual opposition (consumes S14 `ContradictionDetector` output)
- `SAME_DOCUMENT`: Shared `document_id` identity
- `SAME_VERSION_CHAIN`: Shared document root lineage (e.g., `policy_v1` and `policy_v2` share root `policy`)
- `TEMPORALLY_ADJACENT`: Consecutive years or contiguous effective date ranges
- `SUPPORTS` / `ELABORATES`: Explicit structural references (parent-child links, in-text citations)

**`EvidenceGraph` (Dataclass)** — A lightweight, bounded in-memory graph storing nodes (chunk metadata) and directed/typed edges (`Relationship` objects). Provides lookup methods: `get_supersedes()`, `get_superseded_by()`, `get_contradictions()`, `get_version_chain()`. No external database, no Neo4j, no distributed storage. Strictly local and bounded.

**`RelationshipAnalyzer`** — The pairwise edge detector. Given a list of candidate chunks, it performs O(n²) analysis (bounded to `max_graph_nodes=20`) and constructs an `EvidenceGraph`. Detection logic:
- Supersession: Compares parsed version tuples from S16 `TemporalMetadata`; respects explicit `supersedes` metadata tags; supports transitive inference (A→B→C implies A→C) when enabled.
- Contradiction: Calls `ContradictionDetector.analyze_pair()` from S14 directly. Does not re-implement conflict detection.
- Same-document: Exact `document_id` match.
- Version chain: Regex-based root document ID extraction (strips version suffixes, compares stems).
- Temporal adjacency: Year delta of exactly 1, or `effective_until` of one chunk matching `effective_from` of another.
- Elaboration: Only when explicit `parent_id` metadata or in-text chunk/document references exist. Will not infer from semantic similarity alone.

### 2.2 Configuration: `S17RelationshipConfig` in `app/evidence/config.py`

Follows the existing dataclass pattern established by `S14ResolutionConfig`, `S15SufficiencyConfig`, and `S16TemporalConfig`. Key controls:
- `relationship_enabled` (bool): Master switch. Defaults to `True`.
- `relationship_weight` (float): Influence on candidate reordering. Defaults to `0.15`.
- `max_relationship_edges` (int): Hard cap on graph size. Defaults to `50`.
- `max_graph_nodes` (int): Hard cap on analyzed chunks. Defaults to `20`.
- Per-detector enable flags: `enable_supersession_edges`, `enable_contradiction_edges`, `enable_same_doc_edges`, `enable_version_chain_edges`, `enable_temporal_adjacency_edges`, `enable_elaboration_edges`, `enable_transitive_supersession`.
- Reordering weights: `superseded_candidate_demotion=0.20`, `current_version_head_boost=0.05`.
- Factory presets: `balanced()`, `strict()`, `conservative()`, `disabled()`.

The `disabled()` preset sets `relationship_enabled=False` and `relationship_weight=0.0`, providing a backward-compatible escape hatch if S17 behavior needs to be toggled off in production.

### 2.3 Assembly Integration: `app/evidence/assembly.py`

Changes were deliberately minimal and additive:

- **New factory method:** `EvidenceAssembler.with_relationships()` extends the existing `with_temporal()` chain. Internally creates a `RelationshipAnalyzer` wired to the assembler's existing `ContradictionDetector` and `TemporalAnalyzer` instances (no duplication).

- **Graph construction slot:** After S16 temporal enrichment and before the greedy assembly loop, the assembler calls `self.relationship_analyzer.build_graph(ranked_chunks)` to construct the evidence graph over the full candidate pool.

- **Relationship-aware reordering:** A new `_relationship_aware_reorder()` method adjusts `combined_score` on candidates based on graph signals. Chunks superseded by other candidates in the pool are demoted (multiplied by `1.0 - demotion`). Chunks that are version chain heads (supersede other candidates) receive a small boost. This reordering is a stable sort — it never removes chunks.

- **Result extension:** `AssemblyResult` gains an `evidence_graph` field (type `Optional[EvidenceGraph]`). `AssemblyMetrics` gains `relationship_edges` and `relationship_nodes` counters. All existing fields and behaviors are unchanged.

---

## 3. DESIGN DECISIONS AND RATIONALE

### 3.1 Why Not a Full Knowledge Graph?

The brief explicitly prohibited Neo4j, distributed graph storage, LLM-generated relationships, autonomous graph construction, and unrestricted recursive traversal. This was the correct constraint. Synapse's candidate pools are small (bounded by S15 to typically 5–10 chunks). A full graph-RAG system would add massive infrastructure complexity for negligible benefit at this scale. The in-memory `EvidenceGraph` with O(n²) pairwise analysis handles the actual use case in sub-millisecond time.

### 3.2 Why Consume S14/S16 Signals Rather Than Re-Detect?

The `CONTRADICTS` relationship calls `ContradictionDetector.analyze_pair()` directly. The `SUPERSEDES` relationship reads `TemporalMetadata.version` and `TemporalMetadata.supersedes` from S16's `TemporalAnalyzer`. This avoids:
- Signal divergence (two detectors disagreeing on the same pair)
- Maintenance burden (updating logic in two places)
- Test surface explosion

The relationship layer is a consumer of existing authority signals, not a parallel detection system.

### 3.3 Why Conservative on SUPPORTS/ELABORATES?

These relationship types are the most tempting to over-generate. A naive implementation would use semantic similarity to infer that chunk A "supports" chunk B. We explicitly rejected this approach. In S17, `SUPPORTS` and `ELABORATES` edges are only created when deterministic structural evidence exists: explicit `parent_id` metadata, or in-text references to another chunk's ID or document ID. This keeps the false relationship rate at 0% and avoids the precision degradation that would undermine trust in the graph.

### 3.4 Why Demotion/Boost Rather Than Filtering?

The relationship-aware reordering adjusts scores but never removes candidates from the pool. This preserves the S14 conflict safety invariant and the S15 sufficiency control loop. The assembly loop itself remains the authority over what gets selected. The graph provides structural context; it does not override the existing decision machinery.

---

## 4. INVARIANT COMPLIANCE

| Invariant | Status | Evidence |
|---|---|---|
| Zero LLM/embedding calls in hot path | **Maintained** | All detection is regex, metadata, and lexical |
| S14 conflict safety (no silent suppression) | **Maintained** | `CONTRADICTS` marks structurally; `ConfidenceGuard` remains authoritative; test `test_contradiction_does_not_suppress` verifies both nodes preserved |
| S15 bounded expansion | **Maintained** | Assembly loop unchanged; `max_assembly_chunks` and `max_assembly_iterations` still govern |
| S15 MSE stopping | **Maintained** | `SufficiencyEvaluator` called identically; no new signals injected into sufficiency scoring |
| S16 temporal enrichment | **Maintained** | `TemporalAnalyzer.enrich_chunks()` runs before graph construction; temporal scores unchanged |
| S16 zero false suppression | **Maintained** | No chunks removed by relationship layer |
| Deterministic results | **Maintained** | All operations are rule-based; no randomness, no model inference |
| Bounded graph construction | **Maintained** | `max_graph_nodes=20`, `max_relationship_edges=50`; `add_edge()` enforces cap |
| Backward compatibility | **Maintained** | `with_temporal()` and `with_sufficiency()` factories unchanged; `S17RelationshipConfig.disabled()` provides opt-out |

---

## 5. BENCHMARK RESULTS AND INTERPRETATION

### 5.1 Scenario Results

| Scenario | Description | Result | Latency |
|---|---|---|---|
| R1 — Version Chain | v3→v2→v1 direct + transitive supersession | PASS | 0.888 ms |
| R2 — Contradiction | S14 conflict consumption, both nodes preserved | PASS | 0.213 ms |
| R3 — Same Document | Two chunks from same doc, one from different | PASS | 0.268 ms |
| R4 — Temporal Adjacency | 2023→2024 adjacent, 2030 non-adjacent | PASS | 0.318 ms |
| R5 — Mixed Assembly | Current + old + contradictor + support, full pipeline | PASS | 3.280 ms |
| R6 — Precision Guard | Three unrelated domain chunks, zero edges | PASS | 0.331 ms |

### 5.2 Aggregate Metrics

- **Pass rate:** 100% (6/6)
- **Relationship precision:** 100% (every generated edge was valid)
- **False relationship rate:** 0% (no spurious edges on unrelated chunks)
- **Supersession correctness:** 100% (version chains resolved correctly including transitive)
- **Conflict preservation:** 100% (contradictions marked without suppression)
- **Average overhead:** 0.883 ms
- **Peak overhead:** 3.280 ms (full mixed assembly with temporal + relationship + sufficiency)

### 5.3 Honest Interpretation

These results are strong but scoped. The benchmark validates the relationship engine on 6 carefully designed scenarios with clean metadata. It does not yet establish:

- **Recall on noisy corpora:** Real-world evidence may have missing version tags, inconsistent document IDs, or ambiguous temporal markers. The engine will correctly produce no edges in these cases (precision-first), but recall may be low.
- **Behavior at scale:** The benchmark uses 2–5 chunk pools. Behavior with 20+ chunks (the `max_graph_nodes` cap) is untested in the benchmark, though the unit tests cover graph bounds.
- **Impact on final answer quality:** The benchmark measures relationship detection accuracy, not downstream answer correctness. The relationship graph improves candidate ordering, but we have not yet measured whether this translates to better answers on complex multi-document queries.
- **Conflicting relationship signals:** Scenarios where temporal signals suggest one ordering but version signals suggest another are not yet benchmarked.

The 0% false relationship rate is the most important metric. It means the graph is trustworthy — every edge it produces is real. The tradeoff is that it will miss relationships when metadata is incomplete. This is the correct tradeoff for S17.

---

## 6. TEST COVERAGE

**Total test suite:** 348 tests, 0 failures, 226.41s execution time.

**S17-specific tests:** 36 tests in `tests/test_s17_relationships.py`, organized as:

- `TestVersionChain` (5 tests): Direct supersession, full chain graph, inverse SUPERSEDED_BY, explicit metadata supersession.
- `TestContradiction` (3 tests): Status contradiction, negation contradiction, non-suppression invariant.
- `TestSameDocument` (2 tests): Same document_id produces edge, different document_id produces no edge.
- `TestTemporalAdjacency` (3 tests): Consecutive years, non-adjacent years, effective date continuity.
- `TestMixedEvidence` (1 test): Multi-signal pool with current, old, contradictor, and distractor.
- `TestNoFalseRelationships` (2 tests): Unrelated chunks produce zero high-confidence edges; no-version chunks produce no supersession.
- `TestTransitiveSupersession` (2 tests): Transitive inference enabled and disabled.
- `TestGraphBounds` (4 tests): Empty input, single chunk, max_nodes cap, max_edges cap.
- `TestAssemblyIntegration` (6 tests): Factory creation, S16 behavior preservation, graph presence in result, empty candidates, conflict preservation in graph, backward compatibility without relationships.
- `TestEvidenceGraph` (5 tests): Node/edge addition, deduplication, contradiction lookup, serialization, version chain lookup.
- `TestS17Config` (3 tests): Balanced defaults, disabled mode, strict mode.

**Regression status:** All 312 pre-existing tests (S1–S16) pass without modification.

---

## 7. COMMIT HISTORY AND ARTIFACTS

Five atomic commits on `main`, tagged `v1.9.0`, pushed to `origin`:

```
e0724d5 docs(S17): sprint specification, completion, handoff, and review
56d569e benchmark(S17): relationship engine evaluation suite and results
0e805ce test(S17): add 36 relationship engine and integration tests
bc14184 feat(S17): integrate relationship graph into assembly pipeline
fae4f3b feat(S17): add deterministic evidence relationship graph engine
```

**Files changed/created:**
- `app/evidence/relationships.py` (new, ~470 lines)
- `app/evidence/config.py` (modified, +65 lines)
- `app/evidence/assembly.py` (modified, +115/-4 lines)
- `tests/test_s17_relationships.py` (new, ~471 lines)
- `experiments/s17_relationship_benchmark.py` (new, ~200 lines)
- `experiments/S17_relationship_results.json` (new, benchmark artifact)
- `docs/sprints/S17_SPECIFICATION.md` (new)
- `docs/sprints/S17_COMPLETION_REPORT.md` (new)
- `docs/sprints/S17_HANDOFF_REPORT.md` (new)
- `docs/sprints/S17_post_senior_dev.md` (new)

---

## 8. KNOWN LIMITATIONS AND RISKS

1. **Metadata dependency:** The relationship engine is only as good as the metadata on evidence chunks. Chunks without `document_id`, `version`, or temporal markers will produce few or no edges. This is by design (precision-first), but it means the graph will be sparse on poorly annotated corpora.

2. **No semantic relationship inference:** S17 deliberately avoids inferring relationships from embedding similarity or LLM analysis. This keeps the system deterministic and fast, but it means genuinely related chunks without explicit metadata links will not be connected.

3. **Transitive supersession depth:** The current transitive inference is single-pass (A→B→C). It does not handle arbitrarily deep chains (A→B→C→D→E) in a single pass, though in practice version chains rarely exceed 3–4 levels.

4. **Reordering influence is modest:** The `superseded_candidate_demotion=0.20` and `current_version_head_boost=0.05` are intentionally conservative. In edge cases where a superseded chunk has much higher base relevance, it may still rank above the current version. This is the safe default but may need tuning based on real-world evaluation.

5. **Graph not yet used in sufficiency:** The `EvidenceGraph` is available in `AssemblyResult` but is not yet consumed by `SufficiencyEvaluator`. S18 could feed graph structural metrics (e.g., unresolved contradiction count, version chain completeness) into sufficiency signals.

---

## 9. RECOMMENDATIONS FOR S18

1. **Graph-informed sufficiency:** Feed relationship graph topology into `SufficiencyEvaluator` as a new signal. For example, if the graph shows unresolved contradictions among selected chunks, sufficiency should lean toward UNCERTAIN rather than SUFFICIENT.

2. **Cross-document relationship assembly:** Evaluate multi-document queries where complementary sub-claims span distinct sources. The current `SAME_DOCUMENT` and `SAME_VERSION_CHAIN` edges handle intra-document structure; S18 should test inter-document coherence.

3. **Provenance-aware answer generation:** Pass the `EvidenceGraph` to the downstream answer generation layer so that generated answers can cite not just individual evidence chunks but their structural relationships (e.g., "according to the current version of the policy, which supersedes the 2023 edition...").

4. **Recall evaluation on noisy corpora:** Run the relationship engine against a corpus with missing or inconsistent metadata to quantify recall degradation and identify which metadata fields have the highest impact on graph quality.

5. **Relationship weight tuning:** Experiment with `superseded_candidate_demotion` values on real multi-version query sets to find the optimal balance between preferring current evidence and preserving historically relevant context.

---

## 10. CONCLUSION

Sprint 17 successfully delivered the foundational relationship layer that transitions Synapse from flat evidence evaluation to structurally aware evidence assembly. The implementation is small, deterministic, bounded, and fully integrated with the existing S14–S16 pipeline. All invariants are preserved, all tests pass, and the benchmark demonstrates 100% precision with sub-millisecond overhead.

The system is not yet production-validated on broad real-world corpora, and the downstream impact on answer quality remains to be measured. But the architectural foundation is solid, the precision guard is effective, and the integration surface is clean. S17 provides the structural substrate that S18–S20 can build upon.

**Recommendation:** Approve v1.9.0 for merge and proceed to S18 planning with focus on graph-informed sufficiency and cross-document relationship evaluation.

---

*End of Report*