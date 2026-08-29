"""
Aryntra Synapse — Sprint 15 Benchmark
Minimum Sufficient Evidence Controller — Comparative Evaluation.

Strategies compared:
  A: Top-1 baseline (single best chunk)
  B: Fixed Top-k (k=3)
  C: S14 progressive assembly (coverage-ratio stopping)
  D: S15 MSE controller (multi-signal stopping)

Query types: simple, multi-concept, fragmented, contradictory, distractor-heavy.
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

from app.evidence.assembly import EvidenceAssembler, AssemblyResult
from app.evidence.config import S14ResolutionConfig, S15SufficiencyConfig
from app.evidence.sufficiency import SufficiencyEvaluator
from app.evidence.coverage import CoverageAnalyzer
from app.evidence.state import EvidenceState


# ── Test corpus ──

def _c(cid, text, score=0.5):
    return {"chunk_id": cid, "text": text, "priority_score": score}


TEST_CASES = [
    # ── Simple (one concept, one answer chunk) ──
    {
        "id": "simple_1",
        "type": "simple",
        "query": "What caused the server outage?",
        "chunks": [
            _c("s1", "The server outage was caused by a memory leak in the authentication service.", 0.92),
            _c("s2", "The datacenter temperature was within normal range.", 0.30),
            _c("s3", "Network latency remained stable throughout the incident.", 0.25),
        ],
        "expected_min_chunks": 1,
    },
    # ── Multi-concept (cause + time) ──
    {
        "id": "multi_1",
        "type": "multi_concept",
        "query": "What caused the outage and when was it resolved?",
        "chunks": [
            _c("m1", "The cause of the outage was a database failover event.", 0.88),
            _c("m2", "The resolution occurred at 2024-03-15 03:00 UTC.", 0.75),
            _c("m3", "Customer support received 200 tickets during the incident.", 0.40),
            _c("m4", "The quarterly report was published on schedule.", 0.15),
        ],
        "expected_min_chunks": 2,
    },
    # ── Fragmented (3 concepts spread across chunks) ──
    {
        "id": "frag_1",
        "type": "fragmented",
        "query": "What was the cause, impact, and resolution of the datacenter failure?",
        "chunks": [
            _c("f1", "The cause of the datacenter failure was a cooling system malfunction.", 0.85),
            _c("f2", "The impact included 4 hours of downtime for 10,000 users.", 0.70),
            _c("f3", "The resolution involved replacing the primary cooling unit.", 0.65),
            _c("f4", "The datacenter is located in the US-East region.", 0.35),
            _c("f5", "Staff training was completed the following week.", 0.15),
        ],
        "expected_min_chunks": 3,
    },
    # ── Contradictory ──
    {
        "id": "contra_1",
        "type": "contradictory",
        "query": "When was the system restored?",
        "chunks": [
            _c("x1", "The system was restored on 2024-06-15 after the patch.", 0.80),
            _c("x2", "The system was not restored until 2024-07-01 due to complications.", 0.78),
            _c("x3", "Monitoring confirmed full recovery by end of June.", 0.50),
        ],
        "expected_min_chunks": 2,
    },
    # ── Distractor-heavy ──
    {
        "id": "distract_1",
        "type": "distractor",
        "query": "What caused the API failure?",
        "chunks": [
            _c("d1", "The API failure was caused by a rate-limiting misconfiguration.", 0.90),
            _c("d2", "The marketing team launched a new campaign on Monday.", 0.12),
            _c("d3", "Employee satisfaction scores improved by 15% this quarter.", 0.08),
            _c("d4", "The cafeteria menu was updated for the summer season.", 0.05),
            _c("d5", "Cloud storage costs decreased by 8% after optimization.", 0.10),
            _c("d6", "The API failure impacted 300 enterprise customers.", 0.45),
        ],
        "expected_min_chunks": 1,
    },
]


# ── Strategy runners ──

def run_top1(query: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Strategy A: Single best chunk."""
    t0 = time.perf_counter()
    selected = chunks[:1] if chunks else []
    latency = time.perf_counter() - t0
    return {
        "strategy": "A_top1",
        "selected_count": len(selected),
        "chunks": selected,
        "latency": latency,
        "iterations": 1,
    }


def run_fixed_k(query: str, chunks: List[Dict], k: int = 3) -> Dict[str, Any]:
    """Strategy B: Fixed Top-k."""
    t0 = time.perf_counter()
    selected = chunks[:k]
    latency = time.perf_counter() - t0
    return {
        "strategy": f"B_top{k}",
        "selected_count": len(selected),
        "chunks": selected,
        "latency": latency,
        "iterations": 1,
    }


def run_s14(query: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Strategy C: S14 progressive assembly (no S15 evaluator)."""
    assembler = EvidenceAssembler(config=S14ResolutionConfig.full_resolution())
    t0 = time.perf_counter()
    result = assembler.assemble(query, chunks)
    latency = time.perf_counter() - t0
    return {
        "strategy": "C_s14_assembly",
        "selected_count": result.metrics.selected_count,
        "chunks": result.selected_chunks,
        "latency": latency,
        "iterations": result.metrics.iterations,
        "coverage": result.metrics.final_coverage,
        "decision": result.metrics.assembly_decision,
    }


def run_s15(query: str, chunks: List[Dict]) -> Dict[str, Any]:
    """Strategy D: S15 MSE controller."""
    assembler = EvidenceAssembler.with_sufficiency()
    t0 = time.perf_counter()
    result = assembler.assemble(query, chunks)
    latency = time.perf_counter() - t0
    return {
        "strategy": "D_s15_mse",
        "selected_count": result.metrics.selected_count,
        "chunks": result.selected_chunks,
        "latency": latency,
        "iterations": result.metrics.iterations,
        "coverage": result.metrics.final_coverage,
        "decision": result.metrics.assembly_decision,
        "sufficiency_score": result.metrics.sufficiency_score,
        "sufficiency_decision": result.metrics.sufficiency_decision,
    }


# ── Main benchmark ──

def run_benchmark():
    results = []

    for tc in TEST_CASES:
        query = tc["query"]
        chunks = tc["chunks"]
        expected = tc["expected_min_chunks"]

        for runner in [run_top1, lambda q, c: run_fixed_k(q, c, 3), run_s14, run_s15]:
            r = runner(query, chunks)
            r["query_id"] = tc["id"]
            r["query_type"] = tc["type"]
            r["expected_min"] = expected
            r["over_expansion"] = max(0, r["selected_count"] - expected)
            results.append(r)

    # Print summary
    print("\n" + "=" * 90)
    print("S15 SUFFICIENCY BENCHMARK — Strategy Comparison")
    print("=" * 90)
    print(f"{'Query':<12} {'Type':<14} {'Strategy':<18} {'Sel':>3} {'Exp':>3} {'Iter':>4} {'Lat(ms)':>8}")
    print("-" * 90)

    for r in results:
        print(
            f"{r['query_id']:<12} {r['query_type']:<14} {r['strategy']:<18} "
            f"{r['selected_count']:>3} {r['over_expansion']:>3} "
            f"{r.get('iterations', 1):>4} {r['latency']*1000:>8.3f}"
        )

    # Aggregate by strategy
    print("\n" + "=" * 90)
    print("AGGREGATE BY STRATEGY")
    print("=" * 90)
    strategies = ["A_top1", "B_top3", "C_s14_assembly", "D_s15_mse"]
    for strat in strategies:
        strat_results = [r for r in results if r["strategy"] == strat]
        if not strat_results:
            continue
        avg_sel = statistics.mean([r["selected_count"] for r in strat_results])
        avg_exp = statistics.mean([r["over_expansion"] for r in strat_results])
        avg_lat = statistics.mean([r["latency"] for r in strat_results]) * 1000
        print(f"  {strat:<18}  avg_chunks={avg_sel:.1f}  avg_over_exp={avg_exp:.1f}  avg_lat={avg_lat:.3f}ms")

    # Save results
    out_path = Path("experiments/S15_sufficiency_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    return results


if __name__ == "__main__":
    run_benchmark()
