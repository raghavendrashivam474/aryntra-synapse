"""
Aryntra Synapse - Sprint 12: Robustness & Ablation Framework (RQ4, RQ5)

Compares configurations:
  A - Frozen baseline (no priority, no adaptive)
  B - Full priority (always deep)
  C - Existing adaptive (S10)
  D - Calibrated adaptive (S12 calibrated weights + fallback)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import logging
from typing import List, Dict, Any

from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.context.calibration import (
    PriorityCalibrationConfig,
    EvidenceSurvivalTracker,
)
from app.strategy.selector import AdaptiveSelector
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.retrieval.embeddings import EmbeddingModel

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# =====================================================================
# Test Data
# =====================================================================

def build_test_corpus(n: int = 25):
    """Build a test corpus with known answer-bearing chunks."""
    from experiments.s12_corpus_scaling import generate_corpus
    return generate_corpus(n, n_answer_bearing=3, seed=42)


QUERIES = [
    "What is the priority score formula?",
    "How large is the embedding cache?",
    "How does progressive expansion work?",
    "How does the semantic gate bypass work?",
    "How does evidence reuse fingerprinting work?",
]


def run_ablation_experiment() -> dict:
    """Run all ablation configurations."""
    print("=" * 78)
    print("  S12 - Robustness & Ablation Framework (RQ4, RQ5)")
    print("=" * 78)

    embedder = EmbeddingModel()
    tracker = EvidenceSurvivalTracker()
    chunks, answer_ids = build_test_corpus(25)

    best_config = PriorityCalibrationConfig(
        semantic_weight=0.50,
        lexical_weight=0.30,
        reuse_weight=0.20,
        label="s12_calibrated",
    )

    configs = {
        "A_frozen": {
            "priority": False,
            "adaptive": False,
            "fallback": False,
            "weights": None,
        },
        "B_full_priority": {
            "priority": True,
            "adaptive": False,
            "fallback": False,
            "weights": EvidencePriorityWeights(),
        },
        "C_adaptive": {
            "priority": True,
            "adaptive": True,
            "fallback": False,
            "weights": EvidencePriorityWeights(),
        },
        "D_calibrated": {
            "priority": True,
            "adaptive": True,
            "fallback": True,
            "weights": best_config.to_weights(),
        },
    }

    results = {}

    for cfg_name, cfg in configs.items():
        print(f"\n--- Config: {cfg_name} ---")
        cfg_results = []

        engine = None
        if cfg["priority"]:
            engine = EvidencePriorityEngine(
                embedding_model=embedder,
                weights=cfg["weights"],
            )

        selector = None
        if cfg["adaptive"]:
            selector = AdaptiveSelector(mode="adaptive")

        guard = ConfidenceGuard() if cfg["fallback"] else None

        for qi, query in enumerate(QUERIES):
            qid = f"{cfg_name}_q{qi}"
            tracker.reset()
            tracker.mark_retrieved(qid, chunks, answer_ids)

            t0 = time.perf_counter()

            if not cfg["priority"]:
                processed = chunks
                pm_dict = {"semantic_calls": 0, "priority_latency": 0.0}
                path = "none"
            elif not cfg["adaptive"]:
                ranked, pm = engine.rank(query, chunks)
                processed = ranked
                pm_dict = pm.to_dict()
                path = "deep_always"
            else:
                decision = selector.select(query, chunks)
                processed, pm_dict = selector.execute_path(
                    decision, query, chunks, engine,
                )
                path = decision.path.value

                if guard and processed:
                    assessment = guard.assess(query, processed, pm_dict)
                    if assessment.decision == FallbackDecision.FALLBACK_BROAD:
                        processed = chunks
                        path = f"{path}+fallback_broad"
                    elif assessment.decision == FallbackDecision.FALLBACK_SKIP:
                        processed = chunks
                        path = f"{path}+fallback_skip"

            latency = time.perf_counter() - t0

            tracker.mark_prefilter(qid, {c.get("chunk_id", "") for c in processed})
            if (cfg["priority"] and isinstance(processed, list)
                    and processed and "priority_score" in processed[0]):
                tracker.mark_priority(qid, processed)
            final_ids = {c.get("chunk_id", "") for c in processed[:5]}
            tracker.mark_final_context(qid, final_ids)

            rates = tracker.get_survival_rates(qid)

            top3_ab = sum(
                1 for c in processed[:3]
                if c.get("chunk_id", "") in answer_ids
            )

            record = {
                "query": query,
                "path": path,
                "latency_s": round(latency, 6),
                "num_chunks_processed": len(processed),
                "top3_answer_bearing": top3_ab,
                "survival_rates": rates,
                "semantic_calls": pm_dict.get("semantic_calls", 0),
            }
            cfg_results.append(record)

            print(
                f"  [{qi+1}/{len(QUERIES)}] "
                f"path={path:<25} "
                f"lat={latency:.4f}s "
                f"top3ab={top3_ab} "
                f"final={rates['final_rate']:.2f}"
            )

        results[cfg_name] = cfg_results

    return results


def print_summary(results: dict):
    """Print ablation comparison table."""
    print("\n" + "=" * 100)
    print("  S12 ABLATION SUMMARY (RQ4, RQ5)")
    print("=" * 100)
    print(
        f"| {'Config':<20} | {'AvgLat(s)':<10} | {'AvgTop3AB':<10} | "
        f"{'AvgFinalRate':<13} | {'AvgSemCalls':<12} | {'AvgChunks':<10} |"
    )
    print("|" + "-" * 98 + "|")

    for cfg_name in ["A_frozen", "B_full_priority", "C_adaptive", "D_calibrated"]:
        records = results.get(cfg_name, [])
        if not records:
            continue
        n = len(records)
        avg_lat = sum(r["latency_s"] for r in records) / n
        avg_top3 = sum(r["top3_answer_bearing"] for r in records) / n
        avg_final = sum(r["survival_rates"]["final_rate"] for r in records) / n
        avg_sem = sum(r["semantic_calls"] for r in records) / n
        avg_chunks = sum(r["num_chunks_processed"] for r in records) / n

        print(
            f"| {cfg_name:<20} | {avg_lat:<10.4f} | {avg_top3:<10.2f} | "
            f"{avg_final:<13.2f} | {avg_sem:<12.1f} | {avg_chunks:<10.1f} |"
        )
    print("=" * 100)


def main():
    results = run_ablation_experiment()
    print_summary(results)

    output = {
        "sprint": "S12",
        "experiment": "robustness_ablation",
        "research_questions": ["RQ4", "RQ5"],
        "results": results,
    }

    os.makedirs("experiments", exist_ok=True)
    out_path = "experiments/S12_robustness_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n[+] Results saved to {out_path}")


if __name__ == "__main__":
    main()
