"""
Aryntra Synapse - Sprint 12: Corpus Scaling Experiment (RQ1)

Tests whether priority-based evidence selection becomes more
reliable as corpus size increases.

Corpus levels: 5, 25, 50, 100, 250 chunks
Each corpus preserves known answer-bearing evidence mixed with
distractors, near-matches, and irrelevant text.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import random
import logging
from typing import List, Dict, Any, Tuple, Set

from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.context.calibration import EvidenceSurvivalTracker
from app.retrieval.embeddings import EmbeddingModel

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# =====================================================================
# Synthetic Corpus Generator
# =====================================================================

ANSWER_BEARING_TEMPLATES = [
    "Synapse uses priority score P = alpha * semantic + beta * lexical + gamma * reuse for evidence ranking.",
    "The embedding cache is a bounded LRU store holding up to 4096 query and chunk vectors.",
    "Progressive context expansion adds chunks incrementally until sufficiency threshold is met.",
    "The lexical semantic gate uses Jaccard index overlap to bypass expensive embedding calls.",
    "Evidence reuse in S7 fingerprints chunks with SHA-256 for cross-query deduplication.",
]

PARTIALLY_RELEVANT_TEMPLATES = [
    "Priority routing categorizes evidence into high medium and low tiers based on relevance.",
    "Cache systems reduce redundant computation by storing previously computed embeddings.",
    "Context expansion handles token limits by progressively adding relevant information.",
    "Semantic gates evaluate whether chunks need full embedding computation.",
    "Evidence management tracks which chunks have been processed in prior queries.",
]

DISTRACTOR_TEMPLATES = [
    "The weather forecast predicts rain for the upcoming weekend in the metropolitan area.",
    "Machine learning models require large datasets for effective training and validation.",
    "Database indexing improves query performance by organizing data in B-tree structures.",
    "Cloud computing provides scalable infrastructure for distributed application deployment.",
    "Natural language processing encompasses tokenization parsing and sentiment analysis.",
    "Version control systems track changes to source code across collaborative development.",
    "Container orchestration manages deployment scaling and networking of applications.",
    "Neural networks consist of layers of interconnected nodes that process input data.",
    "API design follows RESTful principles including statelessness and resource naming.",
    "Security protocols encrypt data in transit using TLS certificates and key exchange.",
]

CONTRADICTORY_TEMPLATES = [
    "Synapse does not use any priority scoring mechanism for evidence selection.",
    "The embedding cache has no size limit and grows indefinitely without eviction.",
    "Context expansion processes all chunks simultaneously rather than incrementally.",
    "Semantic gates always require full embedding computation with no bypass option.",
    "Evidence reuse was removed in S7 because fingerprinting proved unreliable.",
]


def generate_corpus(
    target_size: int,
    n_answer_bearing: int = 3,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Generate a synthetic corpus with known answer-bearing chunks."""
    rng = random.Random(seed)
    chunks = []
    answer_ids = set()

    for i in range(min(n_answer_bearing, len(ANSWER_BEARING_TEMPLATES))):
        cid = f"ab_{i}"
        chunks.append({
            "chunk_id": cid,
            "text": ANSWER_BEARING_TEMPLATES[i],
            "source": "synthetic",
            "category": "answer_bearing",
        })
        answer_ids.add(cid)

    remaining = target_size - len(chunks)
    if remaining <= 0:
        return chunks[:target_size], answer_ids

    filler_pool = (
        PARTIALLY_RELEVANT_TEMPLATES * 3
        + DISTRACTOR_TEMPLATES * 5
        + CONTRADICTORY_TEMPLATES * 2
    )
    rng.shuffle(filler_pool)

    for i in range(remaining):
        text = filler_pool[i % len(filler_pool)]
        suffix = f" [variant {i}]"
        cid = f"filler_{i}"
        chunks.append({
            "chunk_id": cid,
            "text": text + suffix,
            "source": "synthetic",
            "category": "filler",
        })

    rng.shuffle(chunks)
    return chunks, answer_ids


# =====================================================================
# Experiment Runner
# =====================================================================

TEST_QUERIES = [
    "What is the priority score formula?",
    "How large is the embedding cache?",
    "How does progressive expansion work?",
]

CORPUS_SIZES = [5, 25, 50, 100, 250]


def run_corpus_scaling_experiment() -> dict:
    """Run priority evaluation across corpus sizes."""
    print("=" * 78)
    print("  S12 - Corpus Scaling Experiment (RQ1)")
    print("=" * 78)

    embedder = EmbeddingModel()
    weights = EvidencePriorityWeights()
    engine = EvidencePriorityEngine(embedding_model=embedder, weights=weights)
    tracker = EvidenceSurvivalTracker()

    results = {}

    for size in CORPUS_SIZES:
        print(f"\n--- Corpus size: {size} ---")
        chunks, answer_ids = generate_corpus(size)
        size_results = []

        for qi, query in enumerate(TEST_QUERIES):
            qid = f"q{qi}_s{size}"
            tracker.reset()
            tracker.mark_retrieved(qid, chunks, answer_ids)

            t0 = time.perf_counter()
            ranked, metrics = engine.rank(query, chunks)
            latency = time.perf_counter() - t0

            tracker.mark_prefilter(qid, {c.get("chunk_id", "") for c in ranked})
            tracker.mark_priority(qid, ranked)
            final_ids = {c.get("chunk_id", "") for c in ranked if c.get("state") == "active"}
            tracker.mark_final_context(qid, final_ids)

            survival = tracker.get_answer_bearing_stats(qid)
            rates = tracker.get_survival_rates(qid)

            top_is_ab = False
            if ranked:
                top_id = ranked[0].get("chunk_id", "")
                top_is_ab = top_id in answer_ids

            top3_ab = sum(
                1 for c in ranked[:3]
                if c.get("chunk_id", "") in answer_ids
            )

            record = {
                "query": query,
                "corpus_size": size,
                "latency_s": round(latency, 6),
                "high_count": metrics.high_priority_count,
                "medium_count": metrics.medium_priority_count,
                "low_count": metrics.low_priority_count,
                "avg_score": metrics.average_priority_score,
                "answer_bearing_stats": survival,
                "survival_rates": rates,
                "top1_is_answer_bearing": top_is_ab,
                "top3_answer_bearing_count": top3_ab,
                "semantic_calls": metrics.semantic_calls,
            }
            size_results.append(record)

            print(
                f"  [{qi+1}/{len(TEST_QUERIES)}] "
                f"lat={latency:.4f}s "
                f"H={metrics.high_priority_count} "
                f"top1_ab={top_is_ab} "
                f"top3_ab={top3_ab} "
                f"final_rate={rates['final_rate']:.2f}"
            )

        results[f"C{size}"] = size_results

    return results


def print_summary(results: dict):
    """Print corpus scaling summary table."""
    print("\n" + "=" * 95)
    print("  S12 CORPUS SCALING SUMMARY (RQ1)")
    print("=" * 95)
    print(
        f"| {'Corpus':<8} | {'AvgLat(s)':<10} | {'AvgTop1AB':<10} | "
        f"{'AvgTop3AB':<10} | {'AvgFinalRate':<13} | {'AvgHigh':<8} |"
    )
    print("|" + "-" * 93 + "|")

    for corpus_key in sorted(results.keys(), key=lambda x: int(x[1:])):
        records = results[corpus_key]
        n = len(records)
        avg_lat = sum(r["latency_s"] for r in records) / n
        avg_top1 = sum(r["top1_is_answer_bearing"] for r in records) / n
        avg_top3 = sum(r["top3_answer_bearing_count"] for r in records) / n
        avg_final = sum(r["survival_rates"]["final_rate"] for r in records) / n
        avg_high = sum(r["high_count"] for r in records) / n

        print(
            f"| {corpus_key:<8} | {avg_lat:<10.4f} | {avg_top1:<10.2f} | "
            f"{avg_top3:<10.2f} | {avg_final:<13.2f} | {avg_high:<8.1f} |"
        )
    print("=" * 95)


def main():
    results = run_corpus_scaling_experiment()
    print_summary(results)

    output = {
        "sprint": "S12",
        "experiment": "corpus_scaling",
        "research_question": "RQ1",
        "results": results,
    }

    os.makedirs("experiments", exist_ok=True)
    out_path = "experiments/S12_corpus_scaling_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n[+] Results saved to {out_path}")


if __name__ == "__main__":
    main()
