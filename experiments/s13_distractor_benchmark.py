"""
Aryntra Synapse - Sprint 13: Distractor Benchmark Deep-Dive (Optimized)

Evaluates calibrated Synapse against controlled distractor densities:
- Low (1 useful : 4 distractors)
- Moderate (1 useful : 9 distractors)
- High (1 useful : 24 distractors)
- Dense (1 useful : 49 distractors)
Across Distractor Taxonomy D1-D6:
- D1: Random
- D2: Topic
- D3: Lexical
- D4: Semantic
- D5: Partial Evidence
- D6: Contradictory Evidence
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.context.calibration import EvidenceSurvivalTracker
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.strategy.selector import AdaptiveSelector
from app.retrieval.embeddings import EmbeddingModel
from app.optimization.embedding_cache import EmbeddingCache
from experiments.s13_generalization_matrix import (
    load_distractor_pool,
    load_query_suite,
    generate_controlled_corpus,
    classify_failure,
    FailureSeverity,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def run_distractor_density_benchmark() -> Dict[str, Any]:
    print("=" * 80)
    print("  ARYNTRA SYNAPSE - SPRINT 13 DISTRACTOR DENSITY BENCHMARK")
    print("=" * 80)

    embedder = EmbeddingModel()
    cache = EmbeddingCache(max_entries=8192)
    weights = EvidencePriorityWeights(semantic_weight=0.50, lexical_weight=0.35, reuse_weight=0.15)
    engine = EvidencePriorityEngine(
        embedding_model=embedder,
        weights=weights,
        query_cache=cache,
        evidence_cache=cache
    )
    guard = ConfidenceGuard()
    selector = AdaptiveSelector()
    tracker = EvidenceSurvivalTracker()

    distractor_pool = load_distractor_pool()
    query_suite = load_query_suite()

    density_levels = {
        "low_1_to_4": 5,
        "moderate_1_to_9": 10,
        "high_1_to_24": 25,
        "dense_1_to_49": 50,
    }

    distractor_classes = ["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"]

    benchmark_results = {
        "metadata": {
            "sprint": "S13",
            "benchmark": "distractor_density_sweep",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "density_levels": density_levels,
            "distractor_classes": distractor_classes,
        },
        "records": [],
        "summary_by_density": {},
        "summary_by_class": {},
    }

    t0_all = time.perf_counter()

    for d_label, target_size in density_levels.items():
        for d_class in distractor_classes:
            for q_item in query_suite:
                chunks, answer_ids = generate_controlled_corpus(
                    query_item=q_item,
                    distractor_pool=distractor_pool,
                    target_size=target_size,
                    distractor_type=d_class,
                    seed=100 + target_size
                )

                qid = f"{q_item['id']}_{d_label}_{d_class}"
                tracker.reset()
                tracker.mark_retrieved(qid, chunks, answer_ids)

                q_text = q_item["query"]
                t0 = time.perf_counter()
                ranked, metrics = engine.rank(q_text, chunks)
                lat_ms = (time.perf_counter() - t0) * 1000

                guard_assess = guard.assess(q_text, ranked, metrics.to_dict())
                guard_trig = (guard_assess.decision != FallbackDecision.TRUST_PRIORITY)
                strat_dec = selector.select(q_text, ranked)

                tracker.mark_prefilter(qid, {c.get("chunk_id", "") for c in ranked})
                tracker.mark_priority(qid, ranked)
                final_ids = {c.get("chunk_id", "") for c in ranked if c.get("state") == "active"}
                tracker.mark_final_context(qid, final_ids)
                survival = tracker.get_survival_rates(qid)

                top1_id = ranked[0].get("chunk_id", "") if ranked else ""
                top1_bearing = top1_id in answer_ids
                top_k = min(len(answer_ids) + 2, len(ranked))
                top_k_bearing = sum(1 for c in ranked[:top_k] if c.get("chunk_id", "") in answer_ids)
                top_k_recall = top_k_bearing / max(1, len(answer_ids))

                is_contradictory_top = (d_class == "D6_contradictory" and top1_id.startswith("dist_D6"))

                severity = classify_failure(
                    top1_bearing=top1_bearing,
                    top_k_recall=top_k_recall,
                    survival_rate=survival.get("final_rate", 0.0),
                    guard_triggered=guard_trig,
                    is_contradictory_top=is_contradictory_top
                )

                rec = {
                    "density_label": d_label,
                    "target_size": target_size,
                    "distractor_class": d_class,
                    "query_id": q_item["id"],
                    "latency_ms": round(lat_ms, 2),
                    "top1_bearing": top1_bearing,
                    "top_k_recall": round(top_k_recall, 4),
                    "guard_triggered": guard_trig,
                    "guard_confidence": round(guard_assess.confidence_score, 4),
                    "selected_route": strat_dec.path.value,
                    "failure_severity": severity,
                }
                benchmark_results["records"].append(rec)

    benchmark_results["metadata"]["duration_s"] = round(time.perf_counter() - t0_all, 2)

    for d_label in density_levels.keys():
        subset = [r for r in benchmark_results["records"] if r["density_label"] == d_label]
        n = len(subset)
        benchmark_results["summary_by_density"][d_label] = {
            "count": n,
            "top1_acc": round(sum(1 for r in subset if r["top1_bearing"]) / n, 4),
            "avg_recall": round(sum(r["top_k_recall"] for r in subset) / n, 4),
            "guard_trig_rate": round(sum(1 for r in subset if r["guard_triggered"]) / n, 4),
            "f0_rate": round(sum(1 for r in subset if r["failure_severity"] == FailureSeverity.F0_NO_FAILURE) / n, 4),
            "f4_count": sum(1 for r in subset if r["failure_severity"] == FailureSeverity.F4_DANGEROUS_UNSUPPORTED),
        }

    for d_class in distractor_classes:
        subset = [r for r in benchmark_results["records"] if r["distractor_class"] == d_class]
        n = len(subset)
        benchmark_results["summary_by_class"][d_class] = {
            "count": n,
            "top1_acc": round(sum(1 for r in subset if r["top1_bearing"]) / n, 4),
            "avg_recall": round(sum(r["top_k_recall"] for r in subset) / n, 4),
            "guard_trig_rate": round(sum(1 for r in subset if r["guard_triggered"]) / n, 4),
            "f4_count": sum(1 for r in subset if r["failure_severity"] == FailureSeverity.F4_DANGEROUS_UNSUPPORTED),
        }

    out_file = os.path.join(os.path.dirname(__file__), "S13_distractor_benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)

    print(f"\nDistractor Benchmark completed in {benchmark_results['metadata']['duration_s']}s. Results saved to {out_file}")

    print("\n--- Summary By Distractor Density ---")
    for k, v in benchmark_results["summary_by_density"].items():
        print(f"  {k:<20}: Top-1={v['top1_acc']*100:5.1f}% | Recall={v['avg_recall']*100:5.1f}% | GuardTrigger={v['guard_trig_rate']*100:4.1f}% | F4={v['f4_count']}")

    print("\n--- Summary By Distractor Taxonomy ---")
    for k, v in benchmark_results["summary_by_class"].items():
        print(f"  {k:<20}: Top-1={v['top1_acc']*100:5.1f}% | Recall={v['avg_recall']*100:5.1f}% | GuardTrigger={v['guard_trig_rate']*100:4.1f}% | F4={v['f4_count']}")
    print("=" * 80)

    return benchmark_results


if __name__ == "__main__":
    run_distractor_density_benchmark()
