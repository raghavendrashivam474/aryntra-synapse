"""
experiments/s7_experiment.py

Aryntra Synapse — Sprint 7
Evidence Reuse experiment.

Runs three workloads against the live server:
  A. Repeated evidence (same query 3x)
  B. Non-repeated evidence (3 distinct queries)
  C. Mixed workload (5 queries with overlap)

Compares S7 reuse metrics across workloads.
Requires: uvicorn running on 127.0.0.1:8000 with evidence_reuse_enabled=True
"""

import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
TOP_K = 3
TIMEOUT = 180.0

# Workload definitions
WORKLOAD_A_REPEATED = [
    {"id": "A1", "question": "What is the capital of France?"},
    {"id": "A2", "question": "What is the capital of France?"},
    {"id": "A3", "question": "What is the capital of France?"},
]

WORKLOAD_B_DISTINCT = [
    {"id": "B1", "question": "What is the capital of France?"},
    {"id": "B2", "question": "Who developed the theory of relativity?"},
    {"id": "B3", "question": "How does photosynthesis work?"},
]

WORKLOAD_C_MIXED = [
    {"id": "C1", "question": "What is the capital of France?"},
    {"id": "C2", "question": "Who developed the theory of relativity?"},
    {"id": "C3", "question": "What is the capital of France?"},
    {"id": "C4", "question": "How does photosynthesis work?"},
    {"id": "C5", "question": "Who developed the theory of relativity?"},
]


def health_check(client):
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE - S7 EVIDENCE REUSE EXPERIMENT")
    print("=" * 70)
    print("\n[1/4] Health Check")
    print("-" * 40)
    r = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    for k in ["status", "app_name", "version", "retriever_ready",
              "chunk_count", "llm_model", "evidence_reuse_enabled",
              "evidence_store_size"]:
        print(f"  {k}: {d.get(k)}")
    if not d.get("evidence_reuse_enabled"):
        print("\n  WARNING: evidence_reuse_enabled is False!")
    return d


def run_workload(client, name, queries):
    print(f"\n[{name}] Running {len(queries)} queries")
    print("-" * 40)
    results = []
    for item in queries:
        qid, q = item["id"], item["question"]
        print(f"\n  {qid}: {q}")
        try:
            r = client.post(
                f"{BASE_URL}/ask",
                json={"text": q, "top_k": TOP_K},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            d = r.json()
            result = {
                "id": qid,
                "question": q,
                "status": "PASS",
                "answer": d.get("answer", "")[:100],
                "total_latency": d.get("total_latency"),
                "retrieval_latency": d.get("retrieval_latency"),
                "total_evidence_candidates": d.get("total_evidence_candidates", 0),
                "unique_evidence_candidates": d.get("unique_evidence_candidates", 0),
                "reused_evidence_count": d.get("reused_evidence_count", 0),
                "new_evidence_count": d.get("new_evidence_count", 0),
                "reuse_rate": d.get("reuse_rate", 0.0),
                "fingerprinting_latency": d.get("fingerprinting_latency", 0.0),
                "workspace_lookup_latency": d.get("workspace_lookup_latency", 0.0),
                "evidence_store_size": d.get("evidence_store_size", 0),
                "total_model_calls": d.get("total_model_calls", 1),
                "stop_reason": d.get("stop_reason", "unknown"),
                "final_context_length": d.get("final_context_length", 0),
            }
            print(
                f"    Reuse: {result['reused_evidence_count']}/{result['total_evidence_candidates']} "
                f"(rate={result['reuse_rate']:.2%}) | "
                f"Store: {result['evidence_store_size']} | "
                f"Latency: {result['total_latency']}s"
            )
            results.append(result)
        except Exception as exc:
            print(f"    FAILED: {exc}")
            results.append({"id": qid, "question": q, "status": "FAIL", "error": str(exc)})
    return results


def save_results(health, workloads):
    result_file = Path("experiments/S7_results_v1.json")
    output = {
        "experiment": "S7",
        "phase": "evidence-reuse-evaluation",
        "health": health,
        "workloads": workloads,
    }
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to: {result_file}")


def print_summary(workloads):
    print(f"\n[4/4] Summary")
    print("=" * 70)
    for name, results in workloads.items():
        passed = sum(1 for r in results if r["status"] == "PASS")
        avg_reuse = 0.0
        if passed > 0:
            avg_reuse = sum(r.get("reuse_rate", 0) for r in results if r["status"] == "PASS") / passed
        print(f"  {name}: {passed}/{len(results)} passed, avg reuse rate: {avg_reuse:.2%}")
    print("=" * 70)


def main():
    with httpx.Client() as client:
        try:
            health = health_check(client)
        except Exception:
            print(f"ERROR: Cannot reach {BASE_URL}. Start uvicorn first.")
            sys.exit(1)

        workloads = {}
        for name, queries in [
            ("A_repeated", WORKLOAD_A_REPEATED),
            ("B_distinct", WORKLOAD_B_DISTINCT),
            ("C_mixed", WORKLOAD_C_MIXED),
        ]:
            workloads[name] = run_workload(client, name, queries)

        save_results(health, workloads)
        print_summary(workloads)


if __name__ == "__main__":
    main()
