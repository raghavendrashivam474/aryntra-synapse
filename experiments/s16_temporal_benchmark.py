"""
Aryntra Synapse — Sprint 16 Benchmark
Temporal & Version-Aware Evidence Selection Evaluation.

Compares:
  - S15 Baseline Assembler (multi-signal stopping, no temporal awareness)
  - S16 Temporal-Aware Assembler (S15 + Temporal compatibility scoring and enrichment)

Evaluates scenarios T1 to T8 to measure exact research metrics.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import time
import statistics
from typing import List, Dict, Any

from app.evidence.assembly import EvidenceAssembler
from app.evidence.config import S15SufficiencyConfig, S16TemporalConfig


# ── Test Corpus Definition ──────────────────────────────────────────

def _c(cid: str, text: str, score: float = 0.8, **kwargs) -> Dict[str, Any]:
    chunk = {
        "chunk_id": cid,
        "text": text,
        "score": score,
        "priority_score": score,
    }
    chunk.update(kwargs)
    return chunk


BENCHMARK_CASES = [
    # ── T1: Current information ──
    {
        "id": "T1_current_info",
        "category": "T1_current",
        "query": "What is the company's current pricing for the Pro plan?",
        "chunks": [
            _c("T1_c1", "In 2026, the Pro plan is $30/month.", 0.85, timestamp="2026-01-01"),
            _c("T1_c2", "In 2022, the Pro plan was $20/month.", 0.90), # higher semantic score, older info
        ],
        "expected_top_1": "T1_c1",
        "expected_target_ids": ["T1_c1"],
    },
    # ── T2: Historical information ──
    {
        "id": "T2_historical_info",
        "category": "T2_historical",
        "query": "What was the pricing back in 2022?",
        "chunks": [
            _c("T2_c1", "In 2026, the Pro plan is $30/month.", 0.95, timestamp="2026-01-01"),
            _c("T2_c2", "In 2022, the Pro plan was $20/month.", 0.80), # lower semantic, older info (correct match)
        ],
        "expected_top_1": "T2_c2",
        "expected_target_ids": ["T2_c2"],
    },
    # ── T3: Version chains ──
    {
        "id": "T3_version_chain",
        "category": "T3_versions",
        "query": "What is the latest product refund policy?",
        "chunks": [
            _c("T3_c1", "Product policy v1.0 (2023): refund in 7 days.", 0.75, version="1.0"),
            _c("T3_c2", "Product policy v2.0 (2024): refund in 14 days.", 0.80, version="2.0", supersedes="1.0"),
            _c("T3_c3", "Product policy v3.0 (2025): refund in 30 days.", 0.85, version="3.0", supersedes="2.0"),
        ],
        "expected_top_1": "T3_c3",
        "expected_target_ids": ["T3_c3"],
    },
    # ── T4: Superseded evidence ──
    {
        "id": "T4_superseded",
        "category": "T4_supersession",
        "query": "What is the active policy on remote work?",
        "chunks": [
            _c("T4_c1", "Remote work policy v2 (2025) replaces v1. Remote work is fully approved.", 0.82, version="2", supersedes="1"),
            _c("T4_c2", "Remote work policy v1 (2023). Remote work requires senior VP approval.", 0.90), # higher semantic, superseded
        ],
        "expected_top_1": "T4_c1",
        "expected_target_ids": ["T4_c1"],
    },
    # ── T5: Effective-date mismatch ──
    {
        "id": "T5_effective_date",
        "category": "T5_effective_date",
        "query": "What policy was in effect during February 2026?",
        "chunks": [
            _c("T5_c1", "Policy published January 2026. Effective from 2026-03-01 the rate increases.", 0.88),
            _c("T5_c2", "Policy valid from 2025-01-01 until 2026-02-28. The rate remains standard.", 0.82), # correct for Feb 2026
        ],
        "expected_top_1": "T5_c2",
        "expected_target_ids": ["T5_c2"],
    },
    # ── T6: Unknown timestamps ──
    {
        "id": "T6_unknown_timestamp",
        "category": "T6_unknown",
        "query": "Explain how the server authentication protocol works.",
        "chunks": [
            _c("T6_c1", "Authentication uses SHA-256 signatures with a timestamp validation window.", 0.85), # missing temporal metadata (must not be suppressed)
            _c("T6_c2", "Older servers used MD5 hashes which are now deprecated.", 0.80, timestamp="2018-05-12"),
        ],
        "expected_top_1": "T6_c1",
        "expected_target_ids": ["T6_c1"],
    },
    # ── T7: Mixed corpus ──
    {
        "id": "T7_mixed_corpus",
        "category": "T7_mixed",
        "query": "What is the active pricing tier today?",
        "chunks": [
            _c("T7_c1", "Active pricing for Pro is $30/month as of 2025.", 0.85, timestamp="2025-01-01"), # target
            _c("T7_c2", "In 2020, Pro pricing was $15/month.", 0.80), # old
            _c("T7_c3", "The server room temperature must be kept at 20C.", 0.15), # irrelevant
            _c("T7_c4", "Active pricing for Pro is $25/month.", 0.82, version="1", superseded="yes"), # superseded
        ],
        "expected_top_1": "T7_c1",
        "expected_target_ids": ["T7_c1"],
    },
    # ── T8: Temporal distractors ──
    {
        "id": "T8_temporal_distractor",
        "category": "T8_distractor",
        "query": "What is the current system API endpoint?",
        "chunks": [
            _c("T8_c1", "The active API endpoint is now /v2/api.", 0.80, timestamp="2026-01-01"), # target
            _c("T8_c2", "The legacy API endpoint was /v1/api.", 0.90), # distractor (higher semantic, past tense)
        ],
        "expected_top_1": "T8_c1",
        "expected_target_ids": ["T8_c1"],
    },
]


# ── Runners ──────────────────────────────────────────────────────────

def run_s15_baseline(query: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Run S15 baseline progressive assembler (no temporal awareness)."""
    # Clone chunks to avoid side effects
    cloned_chunks = [dict(c) for c in chunks]
    assembler = EvidenceAssembler.with_sufficiency()
    
    t0 = time.perf_counter()
    result = assembler.assemble(query, cloned_chunks)
    latency = time.perf_counter() - t0

    return {
        "selected_ids": [c["chunk_id"] for c in result.selected_chunks],
        "top_1_id": result.selected_chunks[0]["chunk_id"] if result.selected_chunks else None,
        "latency_ms": latency * 1000,
        "iterations": result.metrics.iterations,
        "sufficiency_score": result.metrics.sufficiency_score,
    }


def run_s16_temporal(query: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Run S16 temporal progressive assembler (temporal-aware)."""
    # Clone chunks to avoid side effects
    cloned_chunks = [dict(c) for c in chunks]
    assembler = EvidenceAssembler.with_temporal()
    
    t0 = time.perf_counter()
    result = assembler.assemble(query, cloned_chunks)
    latency = time.perf_counter() - t0

    return {
        "selected_ids": [c["chunk_id"] for c in result.selected_chunks],
        "top_1_id": result.selected_chunks[0]["chunk_id"] if result.selected_chunks else None,
        "latency_ms": latency * 1000,
        "iterations": result.metrics.iterations,
        "sufficiency_score": result.metrics.sufficiency_score,
        "temporal_score": result.metrics.temporal_score,
        "query_temporal_intent": result.metrics.query_temporal_intent,
    }


# ── Benchmark Evaluation ──────────────────────────────────────────────

def run_benchmark():
    s15_results = {}
    s16_results = {}

    print("\n" + "=" * 90)
    print("S16 TEMPORAL & VERSION-AWARE BENCHMARK — Head-to-Head Comparison")
    print("=" * 90)
    print(f"{'Scenario':<25} {'S15 Top-1':<12} {'S16 Top-1':<12} {'Target':<10} {'S15 Lat':<10} {'S16 Lat':<10}")
    print("-" * 90)

    for case in BENCHMARK_CASES:
        cid = case["id"]
        q = case["query"]
        chunks = case["chunks"]
        target = case["expected_top_1"]

        # Run S15
        r15 = run_s15_baseline(q, chunks)
        s15_results[cid] = r15

        # Run S16
        r16 = run_s16_temporal(q, chunks)
        s16_results[cid] = r16

        print(
            f"{case['category']:<25} "
            f"{r15['top_1_id'] or 'None':<12} "
            f"{r16['top_1_id'] or 'None':<12} "
            f"{target:<10} "
            f"{r15['latency_ms']:>7.3f}ms  "
            f"{r16['latency_ms']:>7.3f}ms"
        )

    # Calculate Research Metrics
    total_cases = len(BENCHMARK_CASES)
    
    # 1. Top-1 Selection Accuracy
    s15_top1_correct = sum(1 for c in BENCHMARK_CASES if s15_results[c["id"]]["top_1_id"] == c["expected_top_1"])
    s16_top1_correct = sum(1 for c in BENCHMARK_CASES if s16_results[c["id"]]["top_1_id"] == c["expected_top_1"])
    
    # 2. Current-State Query Accuracy (T1, T4, T7, T8)
    current_cases = ["T1_current_info", "T4_superseded", "T7_mixed_corpus", "T8_temporal_distractor"]
    s15_current_correct = sum(1 for cid in current_cases if s15_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))
    s16_current_correct = sum(1 for cid in current_cases if s16_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))

    # 3. Historical Query Accuracy (T2, T5)
    historical_cases = ["T2_historical_info", "T5_effective_date"]
    s15_hist_correct = sum(1 for cid in historical_cases if s15_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))
    s16_hist_correct = sum(1 for cid in historical_cases if s16_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))

    # 4. Supersession accuracy (T3, T4)
    supersession_cases = ["T3_version_chain", "T4_superseded"]
    s15_super_correct = sum(1 for cid in supersession_cases if s15_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))
    s16_super_correct = sum(1 for cid in supersession_cases if s16_results[cid]["top_1_id"] == next(c["expected_top_1"] for c in BENCHMARK_CASES if c["id"] == cid))

    # 5. False suppression count (Check T6 - unknown timestamp should not suppress T6_c1)
    s15_t6_selected = "T6_c1" in s15_results["T6_unknown_timestamp"]["selected_ids"]
    s16_t6_selected = "T6_c1" in s16_results["T6_unknown_timestamp"]["selected_ids"]
    
    s15_false_suppression = 0 if s15_t6_selected else 1
    s16_false_suppression = 0 if s16_t6_selected else 1

    # 6. Latency Analysis
    avg_s15_latency = statistics.mean([r["latency_ms"] for r in s15_results.values()])
    avg_s16_latency = statistics.mean([r["latency_ms"] for r in s16_results.values()])
    added_latency = avg_s16_latency - avg_s15_latency

    # Output metrics
    print("\n" + "=" * 90)
    print("RESEARCH METRICS COMPARISON")
    print("=" * 90)
    print(f"  Metric                           S15 Baseline      S16 Temporal-Aware")
    print("-" * 90)
    print(f"  Overall Top-1 Accuracy:          {s15_top1_correct / total_cases * 100:>14.1f}%     {s16_top1_correct / total_cases * 100:>14.1f}%")
    print(f"  Current-Query Accuracy:          {s15_current_correct / len(current_cases) * 100:>14.1f}%     {s16_current_correct / len(current_cases) * 100:>14.1f}%")
    print(f"  Historical-Query Accuracy:       {s15_hist_correct / len(historical_cases) * 100:>14.1f}%     {s16_hist_correct / len(historical_cases) * 100:>14.1f}%")
    print(f"  Supersession Accuracy:           {s15_super_correct / len(supersession_cases) * 100:>14.1f}%     {s16_super_correct / len(supersession_cases) * 100:>14.1f}%")
    print(f"  False Suppression:               {s15_false_suppression:>14d}      {s16_false_suppression:>14d}")
    print(f"  Average Execution Latency:       {avg_s15_latency:>12.3f}ms    {avg_s16_latency:>12.3f}ms")
    print(f"  Temporal Decision Overhead:                   —      {added_latency:>12.3f}ms")
    print("=" * 90)

    # Prepare JSON artifact
    artifact = {
        "metadata": {
            "sprint": "S16",
            "version": "v1.7.0",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_scenarios": total_cases,
        },
        "metrics": {
            "s15_top1_accuracy": s15_top1_correct / total_cases,
            "s16_top1_accuracy": s16_top1_correct / total_cases,
            "s15_current_accuracy": s15_current_correct / len(current_cases),
            "s16_current_accuracy": s16_current_correct / len(current_cases),
            "s15_historical_accuracy": s15_hist_correct / len(historical_cases),
            "s16_historical_accuracy": s16_hist_correct / len(historical_cases),
            "s15_supersession_accuracy": s15_super_correct / len(supersession_cases),
            "s16_supersession_accuracy": s16_super_correct / len(supersession_cases),
            "s15_false_suppression_count": s15_false_suppression,
            "s16_false_suppression_count": s16_false_suppression,
            "s15_avg_latency_ms": avg_s15_latency,
            "s16_avg_latency_ms": avg_s16_latency,
            "temporal_decision_overhead_ms": added_latency,
        },
        "scenarios": [
            {
                "case_id": case["id"],
                "category": case["category"],
                "query": case["query"],
                "target": case["expected_top_1"],
                "s15_output": s15_results[case["id"]],
                "s16_output": s16_results[case["id"]],
            }
            for case in BENCHMARK_CASES
        ],
    }

    out_path = Path("experiments/S16_temporal_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, default=str)
    print(f"\nArtifact saved cleanly to {out_path}")


if __name__ == "__main__":
    run_benchmark()
