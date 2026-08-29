"""
Aryntra Synapse — Sprint 14
Conflict-Aware Evidence Resolution & Progressive Assembly Benchmark Matrix

Evaluates 8 Configurations (A–H) across 6 Benchmark Query Classes:
1. Normal / Single-chunk factual (Q1-Q3)
2. Multi-concept facets (Cause, Date, Outcome)
3. Fragmented evidence (Distributed across 2-5 chunks)
4. Contradictory evidence (Direct negation / status / temporal conflict)
5. Mixed (Fragmented + Contradictory)
6. Distractor-heavy (Relevant + Topic + Lexical + Contradictory + Partial)

Configurations evaluated:
- Config A: S13 Baseline
- Config B: Contradiction Only
- Config C: Coverage Only
- Config D: Progressive Assembly Only
- Config E: Contradiction + Coverage
- Config F: Contradiction + Progressive Assembly
- Config G: Coverage + Progressive Assembly
- Config H: Full Resolution (Contradiction + Coverage + Progressive Assembly + Guard)
"""
import os
import sys
import json
import time
import statistics
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.retrieval.embeddings import EmbeddingModel
from app.optimization.embedding_cache import EmbeddingCache
from app.evidence.contradiction import ContradictionDetector, ConflictReport
from app.evidence.coverage import CoverageAnalyzer, CoverageReport
from app.evidence.assembly import EvidenceAssembler
from app.evidence.config import S14ResolutionConfig
from app.evidence.state import EvidenceState

# Load S13 queries and distractors
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "s13"))


def load_s13_data():
    with open(os.path.join(DATA_DIR, "query_suite.json"), "r", encoding="utf-8") as f:
        queries = json.load(f)
    with open(os.path.join(DATA_DIR, "distractor_corpus.json"), "r", encoding="utf-8") as f:
        distractors = json.load(f)
    return queries, distractors


# Construct specialized S14 multi-concept and fragmented test cases
S14_SPECIALIZED_DATASET = [
    # 1. Multi-concept & Fragmented queries
    {
        "id": "s14_frag_1",
        "query": "What caused the cluster failover, when did it happen, and what was the outcome?",
        "type": "multi_concept_fragmented",
        "useful_chunks": [
            {"chunk_id": "u1", "text": "The cluster failover was caused by a memory exhaustion leak in worker node 4.", "is_useful": True, "facet": "cause"},
            {"chunk_id": "u2", "text": "The failover incident happened at date 2024-08-12 at 04:15 UTC during backup cycle.", "is_useful": True, "facet": "time"},
            {"chunk_id": "u3", "text": "The resulting outcome was zero transaction loss and healthy standby promotion in 450ms.", "is_useful": True, "facet": "outcome"},
        ],
        "contradictory_chunks": [
            {"chunk_id": "c1", "text": "Standby promotion completely failed causing 100% permanent data loss.", "is_contradictory": True},
        ],
    },
    {
        "id": "s14_frag_2",
        "query": "What is the cache policy mechanism, where is it hosted, and what is its capacity limit?",
        "type": "multi_concept_fragmented",
        "useful_chunks": [
            {"chunk_id": "u1", "text": "The embedding cache uses an LRU eviction mechanism for bounded storage.", "is_useful": True, "facet": "mechanism"},
            {"chunk_id": "u2", "text": "The cache storage region is hosted in the US-East datacenter cluster.", "is_useful": True, "facet": "location"},
            {"chunk_id": "u3", "text": "The cache capacity limit is strictly bounded to 4096 vectors.", "is_useful": True, "facet": "outcome"},
        ],
        "contradictory_chunks": [
            {"chunk_id": "c1", "text": "The cache capacity limit is infinite and never evicts any vectors.", "is_contradictory": True},
        ],
    },
    {
        "id": "s14_contra_1",
        "query": "Is the progressive context expansion feature enabled or deprecated?",
        "type": "contradictory_focus",
        "useful_chunks": [
            {"chunk_id": "u1", "text": "Progressive context expansion feature is active and enabled across all pipelines.", "is_useful": True},
        ],
        "contradictory_chunks": [
            {"chunk_id": "c1", "text": "Progressive context expansion feature is completely deprecated and disabled in all pipelines.", "is_contradictory": True},
        ],
    },
    {
        "id": "s14_contra_2",
        "query": "When was the Synapse priority scoring engine launched?",
        "type": "contradictory_focus",
        "useful_chunks": [
            {"chunk_id": "u1", "text": "The Synapse priority scoring engine was officially launched in 2024.", "is_useful": True},
        ],
        "contradictory_chunks": [
            {"chunk_id": "c1", "text": "The Synapse priority scoring engine was officially launched in 2021.", "is_contradictory": True},
        ],
    },
]


def run_benchmark_matrix():
    print("=" * 80)
    print("  ARYNTRA SYNAPSE — SPRINT 14 EMPIRICAL BENCHMARK MATRIX (RQ1–RQ5)")
    print("=" * 80)

    s13_queries, distractors = load_s13_data()
    embedder = EmbeddingModel()
    cache = EmbeddingCache(max_entries=8192)
    weights = EvidencePriorityWeights(semantic_weight=0.50, lexical_weight=0.35, reuse_weight=0.15)
    engine = EvidencePriorityEngine(
        embedding_model=embedder,
        weights=weights,
        query_cache=cache,
        evidence_cache=cache
    )
    detector = ContradictionDetector()
    analyzer = CoverageAnalyzer()
    guard = ConfidenceGuard()

    # Configurations A to H
    configs = {
        "Config A (S13 Baseline)": {
            "use_contradiction": False,
            "use_coverage": False,
            "use_assembly": False,
            "cfg": S14ResolutionConfig.baseline_s13(),
        },
        "Config B (Contradiction Only)": {
            "use_contradiction": True,
            "use_coverage": False,
            "use_assembly": False,
            "cfg": S14ResolutionConfig.contradiction_only(),
        },
        "Config C (Coverage Only)": {
            "use_contradiction": False,
            "use_coverage": True,
            "use_assembly": False,
            "cfg": S14ResolutionConfig.coverage_only(),
        },
        "Config D (Assembly Only)": {
            "use_contradiction": False,
            "use_coverage": False,
            "use_assembly": True,
            "cfg": S14ResolutionConfig.assembly_only(),
        },
        "Config E (Contra + Coverage)": {
            "use_contradiction": True,
            "use_coverage": True,
            "use_assembly": False,
            "cfg": S14ResolutionConfig(
                relevance_weight=0.45, lexical_weight=0.25,
                coverage_weight=0.25, contradiction_penalty_weight=0.30
            ),
        },
        "Config F (Contra + Assembly)": {
            "use_contradiction": True,
            "use_coverage": False,
            "use_assembly": True,
            "cfg": S14ResolutionConfig(
                relevance_weight=0.50, lexical_weight=0.30,
                coverage_weight=0.0, contradiction_penalty_weight=0.30,
                max_assembly_chunks=5
            ),
        },
        "Config G (Coverage + Assembly)": {
            "use_contradiction": False,
            "use_coverage": True,
            "use_assembly": True,
            "cfg": S14ResolutionConfig(
                relevance_weight=0.40, lexical_weight=0.25,
                coverage_weight=0.35, contradiction_penalty_weight=0.0,
                max_assembly_chunks=5
            ),
        },
        "Config H (Full S14 Resolution)": {
            "use_contradiction": True,
            "use_coverage": True,
            "use_assembly": True,
            "cfg": S14ResolutionConfig.full_resolution(),
        },
    }

    # Build Test Batches
    test_cases = []

    # 1. Standard S13 factual queries with topic distractors
    for q in s13_queries[:5]:
        target = q["expected_answers"][0]
        chunks = [{"chunk_id": "u0", "text": target, "is_useful": True}]
        for i, d_text in enumerate(distractors["D2_topic"][:4]):
            chunks.append({"chunk_id": f"d_topic_{i}", "text": d_text, "is_useful": False})
        test_cases.append({
            "category": "standard_factual",
            "query": q["query"],
            "chunks": chunks,
            "has_conflict": False,
            "target_id": "u0",
            "required_count": 1,
        })

    # 2. Fragmented Queries
    for spec in S14_SPECIALIZED_DATASET:
        if "fragmented" in spec["type"]:
            chunks = list(spec["useful_chunks"])
            for i, d_text in enumerate(distractors["D2_topic"][:4]):
                chunks.append({"chunk_id": f"d_frag_{i}", "text": d_text, "is_useful": False})
            test_cases.append({
                "category": "fragmented",
                "query": spec["query"],
                "chunks": chunks,
                "has_conflict": False,
                "target_ids": [c["chunk_id"] for c in spec["useful_chunks"]],
                "required_count": len(spec["useful_chunks"]),
            })

    # 3. Contradictory Queries
    for spec in S14_SPECIALIZED_DATASET:
        chunks = list(spec["useful_chunks"]) + list(spec["contradictory_chunks"])
        for i, d_text in enumerate(distractors["D3_lexical"][:3]):
            chunks.append({"chunk_id": f"d_contra_{i}", "text": d_text, "is_useful": False})
        test_cases.append({
            "category": "contradictory",
            "query": spec["query"],
            "chunks": chunks,
            "has_conflict": True,
            "target_ids": [c["chunk_id"] for c in spec["useful_chunks"]],
            "contradictory_ids": [c["chunk_id"] for c in spec["contradictory_chunks"]],
            "required_count": 1,
        })

    # 4. Distractor-Heavy Mixed Queries (D1 + D2 + D3 + D4 + D5 + D6)
    for spec in S14_SPECIALIZED_DATASET[:2]:
        chunks = list(spec["useful_chunks"]) + list(spec["contradictory_chunks"])
        chunks.append({"chunk_id": "d_rnd", "text": distractors["D1_random"][0], "is_useful": False})
        chunks.append({"chunk_id": "d_top", "text": distractors["D2_topic"][0], "is_useful": False})
        chunks.append({"chunk_id": "d_lex", "text": distractors["D3_lexical"][0], "is_useful": False})
        chunks.append({"chunk_id": "d_sem", "text": distractors["D4_semantic"][0], "is_useful": False})
        test_cases.append({
            "category": "distractor_heavy_mixed",
            "query": spec["query"],
            "chunks": chunks,
            "has_conflict": True,
            "target_ids": [c["chunk_id"] for c in spec["useful_chunks"]],
            "required_count": len(spec["useful_chunks"]),
        })

    results_table = []

    for name, opt in configs.items():
        assembler = EvidenceAssembler(
            config=opt["cfg"],
            contradiction_detector=detector,
            coverage_analyzer=analyzer
        )

        top1_hits = 0
        total_useful_retrieved = 0
        total_useful_needed = 0
        sufficient_sets = 0
        conflict_detected_correctly = 0
        conflict_false_positives = 0
        total_conflicts_ground_truth = sum(1 for tc in test_cases if tc["has_conflict"])
        total_clean_ground_truth = sum(1 for tc in test_cases if not tc["has_conflict"])
        guard_activations = 0
        latencies = []
        chunk_costs = []

        for tc in test_cases:
            query = tc["query"]
            chunks = tc["chunks"]
            has_conflict_gt = tc["has_conflict"]

            t0 = time.perf_counter()

            # Rank chunks using calibrated priority engine
            ranked, pm = engine.rank(query, chunks)

            # Signal resolution & Assembly
            if opt["use_assembly"]:
                asm_res = assembler.assemble(query, ranked)
                selected = asm_res.selected_chunks
                c_rep = asm_res.conflict_report
                cov_rep = asm_res.coverage_report
                is_suff = (asm_res.relational_state.state == EvidenceState.SUFFICIENT)
            else:
                selected = [ranked[0]] if ranked else []
                c_rep = detector.analyze(ranked[:3]) if opt["use_contradiction"] else ConflictReport(False, 0.0)
                cov_rep = analyzer.evaluate(query, selected) if opt["use_coverage"] else CoverageReport([], [], [], 0.5, False)
                is_suff = cov_rep.is_sufficient

            # ConfidenceGuard Assessment
            assessment = guard.assess(query, ranked, conflict_report=c_rep, coverage_report=cov_rep)
            if assessment.decision != FallbackDecision.TRUST_PRIORITY:
                guard_activations += 1

            latency = (time.perf_counter() - t0) * 1000  # ms
            latencies.append(latency)
            chunk_costs.append(len(selected))

            # Metric: Top-1 bearing check
            top_chunk_id = ranked[0].get("chunk_id", "")
            target_ids = tc.get("target_ids", [tc.get("target_id", "u0")])
            if top_chunk_id in target_ids:
                top1_hits += 1

            # Metric: Recall of useful evidence
            selected_ids = {c["chunk_id"] for c in selected}
            hits = len(selected_ids & set(target_ids))
            total_useful_retrieved += hits
            total_useful_needed += len(target_ids)

            # Metric: Set Sufficiency
            if is_suff or (hits >= len(target_ids) and not (c_rep.detected and opt["use_contradiction"])):
                sufficient_sets += 1

            # Metric: Contradiction Detection
            if c_rep.detected:
                if has_conflict_gt:
                    conflict_detected_correctly += 1
                else:
                    conflict_false_positives += 1

        top1_acc = (top1_hits / len(test_cases)) * 100
        recall = (total_useful_retrieved / max(1, total_useful_needed)) * 100
        set_suff = (sufficient_sets / len(test_cases)) * 100
        conflict_prec = (conflict_detected_correctly / max(1, conflict_detected_correctly + conflict_false_positives)) * 100 if opt["use_contradiction"] else 0.0
        conflict_rec = (conflict_detected_correctly / max(1, total_conflicts_ground_truth)) * 100 if opt["use_contradiction"] else 0.0
        guard_rate = (guard_activations / len(test_cases)) * 100
        mean_lat = statistics.mean(latencies)
        p95_lat = statistics.quantiles(latencies, n=20)[-1] if len(latencies) >= 20 else max(latencies)
        avg_chunks = statistics.mean(chunk_costs)

        # Trade-off score: (Sufficiency + Recall + Top1) / (MeanLatency + AvgChunks)
        composite_quality = (set_suff * 0.45 + recall * 0.35 + top1_acc * 0.20)
        cost_denom = (mean_lat * 0.5 + avg_chunks * 2.0)
        tradeoff = composite_quality / max(1.0, cost_denom)

        results_table.append({
            "Config": name,
            "Top-1 (%)": round(top1_acc, 1),
            "Recall (%)": round(recall, 1),
            "Set Sufficiency (%)": round(set_suff, 1),
            "Conflict Recall (%)": round(conflict_rec, 1),
            "Guard Active (%)": round(guard_rate, 1),
            "Mean Lat (ms)": round(mean_lat, 3),
            "P95 Lat (ms)": round(p95_lat, 3),
            "Avg Chunks": round(avg_chunks, 2),
            "Trade-off Score": round(tradeoff, 2),
        })

    # Print Summary Table
    print(f"\n{'Config':<32} | {'Top-1':<7} | {'Recall':<7} | {'Set Suff':<9} | {'Contra Rec':<11} | {'Guard %':<8} | {'Latency':<9} | {'Trade-off':<9}")
    print("-" * 105)
    for r in results_table:
        print(f"{r['Config']:<32} | {r['Top-1 (%)']:>6.1f}% | {r['Recall (%)']:>6.1f}% | {r['Set Sufficiency (%)']:>8.1f}% | {r['Conflict Recall (%)']:>10.1f}% | {r['Guard Active (%)']:>7.1f}% | {r['Mean Lat (ms)']:>7.3f}ms | {r['Trade-off Score']:>8.2f}")

    # Output JSON Results for Reports
    os.makedirs(os.path.join(DATA_DIR, "..", "s14"), exist_ok=True)
    out_path = os.path.join(DATA_DIR, "..", "s14", "s14_matrix_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_table, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    run_benchmark_matrix()
