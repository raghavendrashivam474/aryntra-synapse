"""
Aryntra Synapse - Sprint 12: Calibration Matrix Experiment (RQ2, RQ3)

Systematically tests priority weight combinations to find
optimal calibration for evidence selection quality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import logging
from typing import List, Dict, Any

from app.context.evidence_priority import EvidencePriorityEngine
from app.context.calibration import (
    PriorityCalibrationConfig,
    CalibrationMatrixGenerator,
    EvidenceSurvivalTracker,
)
from app.retrieval.embeddings import EmbeddingModel

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# =====================================================================
# Test Data
# =====================================================================

CORPUS = [
    {"chunk_id": "c1", "text": "Synapse uses priority score P = alpha * semantic + beta * lexical + gamma * reuse for evidence ranking."},
    {"chunk_id": "c2", "text": "The embedding cache is a bounded LRU store holding up to 4096 query and chunk vectors."},
    {"chunk_id": "c3", "text": "Progressive context expansion adds chunks incrementally until sufficiency threshold is met."},
    {"chunk_id": "c4", "text": "The lexical semantic gate uses Jaccard index overlap to bypass expensive embedding calls."},
    {"chunk_id": "c5", "text": "Evidence reuse in S7 fingerprints chunks with SHA-256 for cross-query deduplication."},
    {"chunk_id": "c6", "text": "Priority routing categorizes evidence into high medium and low tiers based on relevance."},
    {"chunk_id": "c7", "text": "Machine learning models require large datasets for effective training and validation."},
    {"chunk_id": "c8", "text": "Database indexing improves query performance by organizing data in B-tree structures."},
    {"chunk_id": "c9", "text": "Cloud computing provides scalable infrastructure for distributed application deployment."},
    {"chunk_id": "c10", "text": "Natural language processing encompasses tokenization parsing and sentiment analysis."},
]

ANSWER_BEARING = {"c1", "c2", "c3", "c4", "c5"}

QUERIES = [
    ("What is the priority score formula?", "c1"),
    ("How large is the embedding cache?", "c2"),
    ("How does progressive expansion work?", "c3"),
    ("How does the semantic gate bypass work?", "c4"),
    ("How does evidence reuse fingerprinting work?", "c5"),
]


def run_calibration_experiment() -> list:
    """Run all calibration configs against test queries."""
    print("=" * 78)
    print("  S12 - Calibration Matrix Experiment (RQ2, RQ3)")
    print("=" * 78)

    matrix = CalibrationMatrixGenerator.full_matrix()
    print(f"[*] Generated {len(matrix)} calibration configurations")

    embedder = EmbeddingModel()
    tracker = EvidenceSurvivalTracker()
    all_results = []

    for ci, config in enumerate(matrix):
        if not config.validate():
            print(f"  [{ci+1}/{len(matrix)}] SKIP (invalid): {config.label}")
            continue

        weights = config.to_weights()
        engine = EvidencePriorityEngine(embedding_model=embedder, weights=weights)

        config_results = {
            "config": config.to_dict(),
            "queries": [],
        }

        total_top1_hit = 0
        total_final_rate = 0.0

        for qi, (query, expected_id) in enumerate(QUERIES):
            qid = f"cal_{ci}_q{qi}"
            tracker.reset()
            tracker.mark_retrieved(qid, CORPUS, ANSWER_BEARING)

            t0 = time.perf_counter()
            ranked, metrics = engine.rank(query, CORPUS)
            latency = time.perf_counter() - t0

            tracker.mark_priority(qid, ranked)
            final_ids = {c.get("chunk_id", "") for c in ranked if c.get("state") == "active"}
            tracker.mark_final_context(qid, final_ids)

            rates = tracker.get_survival_rates(qid)

            top1_id = ranked[0].get("chunk_id", "") if ranked else ""
            top1_hit = top1_id == expected_id
            total_top1_hit += int(top1_hit)
            total_final_rate += rates["final_rate"]

            config_results["queries"].append({
                "query": query,
                "expected": expected_id,
                "top1_id": top1_id,
                "top1_hit": top1_hit,
                "latency_s": round(latency, 6),
                "high_count": metrics.high_priority_count,
                "final_rate": rates["final_rate"],
                "semantic_calls": metrics.semantic_calls,
            })

        n_q = len(QUERIES)
        config_results["aggregate"] = {
            "top1_accuracy": round(total_top1_hit / n_q, 4),
            "avg_final_rate": round(total_final_rate / n_q, 4),
        }
        all_results.append(config_results)

        print(
            f"  [{ci+1}/{len(matrix)}] {config.label:<35} "
            f"top1={total_top1_hit/n_q:.0%} "
            f"final={total_final_rate/n_q:.2f}"
        )

    return all_results


def print_summary(results: list):
    """Print top calibration configs."""
    print("\n" + "=" * 85)
    print("  S12 CALIBRATION SUMMARY (RQ2)")
    print("=" * 85)
    print(
        f"| {'Config':<35} | {'Top1Acc':<8} | {'AvgFinal':<9} | "
        f"{'S':<5} | {'L':<5} | {'R':<5} |"
    )
    print("|" + "-" * 83 + "|")

    sorted_results = sorted(
        results,
        key=lambda r: r["aggregate"]["top1_accuracy"],
        reverse=True,
    )

    for r in sorted_results[:15]:
        cfg = r["config"]
        agg = r["aggregate"]
        print(
            f"| {cfg['label']:<35} | {agg['top1_accuracy']:<8.1%} | "
            f"{agg['avg_final_rate']:<9.2f} | "
            f"{cfg['semantic_weight']:<5.2f} | "
            f"{cfg['lexical_weight']:<5.2f} | "
            f"{cfg['reuse_weight']:<5.2f} |"
        )
    print("=" * 85)


def main():
    results = run_calibration_experiment()
    print_summary(results)

    output = {
        "sprint": "S12",
        "experiment": "calibration_matrix",
        "research_questions": ["RQ2", "RQ3"],
        "results": results,
    }

    os.makedirs("experiments", exist_ok=True)
    out_path = "experiments/S12_calibration_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n[+] Results saved to {out_path}")


if __name__ == "__main__":
    main()
