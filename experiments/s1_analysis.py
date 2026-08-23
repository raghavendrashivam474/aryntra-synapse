"""
Aryntra Synapse — S1 Analysis

Purpose:
    Reproducibly compare the frozen v0.2.0 baseline results against
    the S1 structured-context experiment results.

Inputs:
    experiments/S1_baseline_results_v1.json
    experiments/S1_results_v1.json

This script performs measurement and comparison only.
It does not modify experimental result files or research findings.

Run:
    python experiments/s1_analysis.py
"""

import json
from pathlib import Path


BASELINE_PATH = Path("experiments/S1_baseline_results_v1.json")
S1_PATH = Path("experiments/S1_results_v1.json")


def load_results(path: Path) -> dict:
    """Load an experiment result JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def percentage_change(baseline: float, experimental: float) -> float:
    """Calculate percentage change from baseline to experimental."""
    if baseline == 0:
        return 0.0
    return ((experimental - baseline) / baseline) * 100


def main() -> None:
    baseline_data = load_results(BASELINE_PATH)
    s1_data = load_results(S1_PATH)

    baseline_results = baseline_data["results"]
    s1_results = s1_data["results"]

    if len(baseline_results) != len(s1_results):
        raise ValueError(
            "Baseline and S1 result sets contain different numbers of queries."
        )

    print("=" * 100)
    print("  ARYNTRA SYNAPSE — S1 RESULT ANALYSIS")
    print("=" * 100)
    print()

    print(f"Baseline:             {baseline_data.get('baseline', 'unknown')}")
    print(f"S1 representation:    {s1_data.get('context_representation', 'unknown')}")
    print(f"Query set:             {s1_data.get('query_set', 'unknown')}")
    print(f"Queries:               {len(s1_results)}")
    print()

    # ------------------------------------------------------------------
    # Per-query comparison
    # ------------------------------------------------------------------

    print("-" * 100)
    print("PER-QUERY COMPARISON")
    print("-" * 100)

    header = (
        f"{'ID':<5}"
        f"{'Base Gen':>12}"
        f"{'S1 Gen':>12}"
        f"{'Gen Δ%':>10}"
        f"{'Base Ctx':>12}"
        f"{'S1 Ctx':>12}"
        f"{'Ctx Δ%':>10}"
        f"{'Base Total':>14}"
        f"{'S1 Total':>14}"
    )

    print(header)
    print("-" * len(header))

    generation_changes = []
    context_changes = []
    total_changes = []

    s1_faster_count = 0
    s1_slower_count = 0
    s1_same_count = 0

    for baseline, s1 in zip(baseline_results, s1_results):
        baseline_generation = float(
            baseline.get("generation_latency", 0.0)
        )
        s1_generation = float(
            s1.get("generation_latency", 0.0)
        )

        baseline_context = float(
            baseline.get("context_length", 0.0)
        )
        s1_context = float(
            s1.get("context_length", 0.0)
        )

        baseline_total = float(
            baseline.get("total_latency", 0.0)
        )
        s1_total = float(
            s1.get("total_latency", 0.0)
        )

        generation_delta = percentage_change(
            baseline_generation,
            s1_generation,
        )

        context_delta = percentage_change(
            baseline_context,
            s1_context,
        )

        total_delta = percentage_change(
            baseline_total,
            s1_total,
        )

        generation_changes.append(generation_delta)
        context_changes.append(context_delta)
        total_changes.append(total_delta)

        if s1_generation < baseline_generation:
            s1_faster_count += 1
        elif s1_generation > baseline_generation:
            s1_slower_count += 1
        else:
            s1_same_count += 1

        print(
            f"{baseline['id']:<5}"
            f"{baseline_generation:>12.3f}"
            f"{s1_generation:>12.3f}"
            f"{generation_delta:>9.1f}%"
            f"{baseline_context:>12.0f}"
            f"{s1_context:>12.0f}"
            f"{context_delta:>9.1f}%"
            f"{baseline_total:>14.3f}"
            f"{s1_total:>14.3f}"
        )

    # ------------------------------------------------------------------
    # Aggregate measurements
    # ------------------------------------------------------------------

    def average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    baseline_generation_total = sum(
        float(result.get("generation_latency", 0.0))
        for result in baseline_results
    )

    s1_generation_total = sum(
        float(result.get("generation_latency", 0.0))
        for result in s1_results
    )

    baseline_total_latency = sum(
        float(result.get("total_latency", 0.0))
        for result in baseline_results
    )

    s1_total_latency = sum(
        float(result.get("total_latency", 0.0))
        for result in s1_results
    )

    baseline_context_average = average(
        [
            float(result.get("context_length", 0.0))
            for result in baseline_results
        ]
    )

    s1_context_average = average(
        [
            float(result.get("context_length", 0.0))
            for result in s1_results
        ]
    )

    representation_latencies = [
        float(result.get("representation_build_latency", 0.0))
        for result in s1_results
    ]

    average_representation_latency = average(representation_latencies)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    print()
    print("-" * 100)
    print("AGGREGATE MEASUREMENTS")
    print("-" * 100)

    print(
        f"Baseline total generation latency: "
        f"{baseline_generation_total:.3f}s"
    )

    print(
        f"S1 total generation latency:       "
        f"{s1_generation_total:.3f}s"
    )

    print(
        f"Generation latency change:          "
        f"{percentage_change(baseline_generation_total, s1_generation_total):.2f}%"
    )

    print()

    print(
        f"Baseline total latency:             "
        f"{baseline_total_latency:.3f}s"
    )

    print(
        f"S1 total latency:                   "
        f"{s1_total_latency:.3f}s"
    )

    print(
        f"Total latency change:               "
        f"{percentage_change(baseline_total_latency, s1_total_latency):.2f}%"
    )

    print()

    print(
        f"Average baseline context:           "
        f"{baseline_context_average:.1f} chars"
    )

    print(
        f"Average S1 context:                 "
        f"{s1_context_average:.1f} chars"
    )

    print(
        f"Average context change:             "
        f"{percentage_change(baseline_context_average, s1_context_average):.2f}%"
    )

    print()

    print(
        f"Average S1 representation build:    "
        f"{average_representation_latency:.6f}s"
    )

    print()

    print(f"S1 faster on generation:            {s1_faster_count}")
    print(f"S1 slower on generation:            {s1_slower_count}")
    print(f"S1 same on generation:              {s1_same_count}")

    print()

    print(
        f"Average per-query generation Δ:     "
        f"{average(generation_changes):.2f}%"
    )

    print(
        f"Average per-query context Δ:        "
        f"{average(context_changes):.2f}%"
    )

    print(
        f"Average per-query total Δ:          "
        f"{average(total_changes):.2f}%"
    )

    # ------------------------------------------------------------------
    # Retrieval consistency
    # ------------------------------------------------------------------

    print()
    print("-" * 100)
    print("RETRIEVAL CONSISTENCY")
    print("-" * 100)

    retrieval_differences = 0

    for baseline, s1 in zip(baseline_results, s1_results):
        baseline_chunks = [
            chunk.get("chunk_id")
            for chunk in baseline.get("retrieved_chunks", [])
        ]

        s1_chunks = [
            chunk.get("chunk_id")
            for chunk in s1.get("retrieved_chunks", [])
        ]

        if baseline_chunks != s1_chunks:
            retrieval_differences += 1
            print(
                f"{baseline['id']}: retrieval differs"
            )

    if retrieval_differences == 0:
        print("Retrieved chunk ordering/selection is identical across all queries.")
    else:
        print(
            f"Retrieval differed on {retrieval_differences} "
            f"of {len(s1_results)} queries."
        )

    # ------------------------------------------------------------------
    # Answer status
    # ------------------------------------------------------------------

    print()
    print("-" * 100)
    print("RESULT STATUS")
    print("-" * 100)

    baseline_passed = sum(
        1 for result in baseline_results
        if result.get("status") == "PASS"
    )

    s1_passed = sum(
        1 for result in s1_results
        if result.get("status") == "PASS"
    )

    print(f"Baseline passed:                    {baseline_passed}/{len(baseline_results)}")
    print(f"S1 passed:                          {s1_passed}/{len(s1_results)}")

    print()
    print("=" * 100)
    print("  ANALYSIS COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()