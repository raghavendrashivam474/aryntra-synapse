"""
experiments/s7_analysis.py

Aryntra Synapse — Sprint 7
Comparative analysis of S7 evidence reuse results.

Reads S7_results_v1.json and produces a summary comparison.
"""

import json
from pathlib import Path


def load_results(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: {path} not found.")
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def analyze_workload(name: str, results: list) -> dict:
    passed = [r for r in results if r.get("status") == "PASS"]
    if not passed:
        return {"name": name, "passed": 0, "total": len(results)}

    total_candidates = sum(r.get("total_evidence_candidates", 0) for r in passed)
    total_reused = sum(r.get("reused_evidence_count", 0) for r in passed)
    total_new = sum(r.get("new_evidence_count", 0) for r in passed)
    avg_latency = sum(r.get("total_latency", 0) for r in passed) / len(passed)
    avg_fp_latency = sum(r.get("fingerprinting_latency", 0) for r in passed) / len(passed)
    avg_lookup_latency = sum(r.get("workspace_lookup_latency", 0) for r in passed) / len(passed)
    reuse_rate = total_reused / total_candidates if total_candidates > 0 else 0.0

    return {
        "name": name,
        "passed": len(passed),
        "total": len(results),
        "total_candidates": total_candidates,
        "total_reused": total_reused,
        "total_new": total_new,
        "reuse_rate": round(reuse_rate, 4),
        "avg_total_latency": round(avg_latency, 4),
        "avg_fingerprinting_latency": round(avg_fp_latency, 6),
        "avg_lookup_latency": round(avg_lookup_latency, 6),
    }


def main():
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE — S7 EVIDENCE REUSE ANALYSIS")
    print("=" * 70)

    data = load_results("experiments/S7_results_v1.json")
    if not data:
        return

    workloads = data.get("workloads", {})
    analyses = {}

    print(f"\n{'Workload':<16} {'Candidates':>10} {'Reused':>8} {'New':>6} "
          f"{'Reuse%':>8} {'AvgLat':>8} {'FPLat':>10} {'LookupLat':>10}")
    print("-" * 80)

    for name, results in workloads.items():
        a = analyze_workload(name, results)
        analyses[name] = a
        print(
            f"{a['name']:<16} {a.get('total_candidates', 0):>10} "
            f"{a.get('total_reused', 0):>8} {a.get('total_new', 0):>6} "
            f"{a.get('reuse_rate', 0):>7.2%} "
            f"{a.get('avg_total_latency', 0):>8.4f} "
            f"{a.get('avg_fingerprinting_latency', 0):>10.6f} "
            f"{a.get('avg_lookup_latency', 0):>10.6f}"
        )

    # Key findings
    print("\n" + "=" * 70)
    print("  KEY FINDINGS")
    print("=" * 70)

    a_repeated = analyses.get("A_repeated", {})
    b_distinct = analyses.get("B_distinct", {})
    c_mixed = analyses.get("C_mixed", {})

    print(f"\n  Repeated workload reuse rate:  {a_repeated.get('reuse_rate', 0):.2%}")
    print(f"  Distinct workload reuse rate:  {b_distinct.get('reuse_rate', 0):.2%}")
    print(f"  Mixed workload reuse rate:     {c_mixed.get('reuse_rate', 0):.2%}")

    fp_overhead = a_repeated.get("avg_fingerprinting_latency", 0)
    lookup_overhead = a_repeated.get("avg_lookup_latency", 0)
    print(f"\n  Avg fingerprinting overhead:   {fp_overhead:.6f}s")
    print(f"  Avg lookup overhead:           {lookup_overhead:.6f}s")
    print(f"  Total S7 overhead per query:   {fp_overhead + lookup_overhead:.6f}s")

    if fp_overhead + lookup_overhead < 0.01:
        print("\n  VERDICT: S7 overhead is negligible (<10ms per query).")
    else:
        print("\n  VERDICT: S7 overhead may be significant. Investigate.")

    print("\n" + "=" * 70)

    # Save analysis
    analysis_file = Path("experiments/S7_analysis_v1.json")
    analysis_file.write_text(
        json.dumps({"experiment": "S7", "analyses": analyses}, indent=2),
        encoding="utf-8",
    )
    print(f"  Analysis saved to: {analysis_file}")


if __name__ == "__main__":
    main()
