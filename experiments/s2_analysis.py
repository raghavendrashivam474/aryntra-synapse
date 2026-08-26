"""
Aryntra Synapse — S2 Analysis

Purpose:
    Reproducibly compare the frozen flat baseline results against
    the S2 context compression experiment results.

Inputs:
    experiments/S2_baseline_results_v1.json
    experiments/S2_results_v1.json

Run:
    python experiments/s2_analysis.py
"""

import json
from pathlib import Path

BASELINE_PATH = Path("experiments/S2_baseline_results_v1.json")
S2_PATH = Path("experiments/S2_results_v1.json")


def load_results(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def pct_change(base: float, exp: float) -> float:
    if base == 0:
        return 0.0
    return ((exp - base) / base) * 100


def main() -> None:
    if not BASELINE_PATH.exists():
        print(f"ERROR: {BASELINE_PATH} not found. Run s2_baseline_diagnostic.py first.")
        return
    if not S2_PATH.exists():
        print(f"ERROR: {S2_PATH} not found. Run s2_experiment.py first.")
        return

    baseline_data = load_results(BASELINE_PATH)
    s2_data = load_results(S2_PATH)

    b_results = baseline_data["results"]
    s_results = s2_data["results"]

    n = len(s_results)

    print("=" * 80)
    print("  ARYNTRA SYNAPSE — S2 CONTEXT COMPRESSION ANALYSIS")
    print("=" * 80)
    print(f"Baseline:          {baseline_data.get('context_representation', 'flat')}")
    print(f"S2 representation: {s2_data.get('context_representation', 'compressed_v1')}")
    print(f"Query set:         {s2_data.get('query_set', 'S2 Query Set v1')}")
    print(f"Total queries:     {n}")
    print()

    # Aggregate Context
    tot_b_ctx = sum(r.get("context_length", 0) for r in b_results)
    tot_s_ctx = sum(r.get("context_length", 0) for r in s_results)
    avg_b_ctx = tot_b_ctx / n
    avg_s_ctx = tot_s_ctx / n
    ctx_delta = pct_change(avg_b_ctx, avg_s_ctx)

    # Aggregate Generation Latency
    tot_b_gen = sum(r.get("generation_latency", 0.0) for r in b_results)
    tot_s_gen = sum(r.get("generation_latency", 0.0) for r in s_results)
    avg_b_gen = tot_b_gen / n
    avg_s_gen = tot_s_gen / n
    gen_delta = pct_change(tot_b_gen, tot_s_gen)

    # Aggregate Total Latency
    tot_b_lat = sum(r.get("total_latency", 0.0) for r in b_results)
    tot_s_lat = sum(r.get("total_latency", 0.0) for r in s_results)
    avg_b_lat = tot_b_lat / n
    avg_s_lat = tot_s_lat / n
    lat_delta = pct_change(tot_b_lat, tot_s_lat)

    # Rep Build Latency
    avg_s_rep = sum(r.get("representation_build_latency", 0.0) for r in s_results) / n

    # Summary table
    print(f"{'Metric':<35} | {'Baseline (flat)':>15} | {'S2 (compressed)':>15} | {'Delta (%)':>10}")
    print("-" * 85)
    print(f"{'Average Context Length (chars)':<35} | {avg_b_ctx:>15.1f} | {avg_s_ctx:>15.1f} | {ctx_delta:>+9.2f}%")
    print(f"{'Total Generation Latency (s)':<35} | {tot_b_gen:>15.3f} | {tot_s_gen:>15.3f} | {gen_delta:>+9.2f}%")
    print(f"{'Average Generation Latency (s)':<35} | {avg_b_gen:>15.3f} | {avg_s_gen:>15.3f} | {gen_delta:>+9.2f}%")
    print(f"{'Total Pipeline Latency (s)':<35} | {tot_b_lat:>15.3f} | {tot_s_lat:>15.3f} | {lat_delta:>+9.2f}%")
    print(f"{'Average Pipeline Latency (s)':<35} | {avg_b_lat:>15.3f} | {avg_s_lat:>15.3f} | {lat_delta:>+9.2f}%")
    print(f"{'Avg Rep Build Latency (s)':<35} | {'N/A':>15} | {avg_s_rep:>15.6f} | {'N/A':>10}")

    # Per-query table
    print()
    print("=" * 85)
    print("  PER-QUERY BREAKDOWN")
    print("=" * 85)
    print(f"{'ID':<5} | {'Base Ctx':<9} | {'S2 Ctx':<9} | {'Reduction':<10} | {'Base Gen (s)':<13} | {'S2 Gen (s)':<13} | {'Gen Delta':<10}")
    print("-" * 85)

    faster_count = 0
    slower_count = 0

    for b, s in zip(b_results, s_results):
        qid = s["id"]
        b_ctx = b.get("context_length", 0)
        s_ctx = s.get("context_length", 0)
        reduction = s.get("context_reduction_pct", 0.0)
        b_gen = b.get("generation_latency", 0.0)
        s_gen = s.get("generation_latency", 0.0)
        g_delta = pct_change(b_gen, s_gen)

        if s_gen < b_gen:
            faster_count += 1
        else:
            slower_count += 1

        print(f"{qid:<5} | {b_ctx:<9} | {s_ctx:<9} | {reduction:>8.1f}% | {b_gen:>13.3f} | {s_gen:>13.3f} | {g_delta:>+9.2f}%")

    print()
    print("=" * 85)
    print("  LATENCY DIRECTION")
    print("=" * 85)
    print(f"  S2 faster than baseline: {faster_count}/{n} queries")
    print(f"  S2 slower than baseline: {slower_count}/{n} queries")
    print("=" * 85)


if __name__ == "__main__":
    main()
