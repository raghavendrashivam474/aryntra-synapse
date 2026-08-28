"""
experiments/s8_experiment.py

Aryntra Synapse — Sprint 8
Evidence Relevance & Priority Management live server experiment.

Runs evaluation queries against the live server:
  A. Baseline / Control Workload
  B. Complex Query Workload
  C. Multi-candidate Workload

Compares S8 priority routing metrics across workloads.
Requires: uvicorn running on 127.0.0.1:8000
"""

import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
TOP_K = 3
TIMEOUT = 180.0

WORKLOAD_QUERIES = [
    {"id": "W1", "question": "What is the core architecture of Aryntra Synapse?"},
    {"id": "W2", "question": "How does context compression reduce token usage?"},
    {"id": "W3", "question": "What is the role of the evidence workspace in managing context?"},
    {"id": "W4", "question": "How does deterministic sufficiency evaluate keyword coverage?"},
    {"id": "W5", "question": "What are the benefits of cross-query evidence reuse and fingerprinting?"},
]


def health_check(client):
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE - S8 EVIDENCE PRIORITY EXPERIMENT")
    print("=" * 70)
    print("\n[1/4] Health Check")
    print("-" * 40)
    r = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    for k in ["status", "app_name", "version", "retriever_ready",
              "chunk_count", "llm_model", "evidence_reuse_enabled",
              "enable_priority_routing", "evidence_store_size"]:
        print(f"  {k}: {d.get(k)}")
    return d


def run_workload(client, queries):
    print(f"\n[2/4] Running {len(queries)} queries with S8 Priority Routing")
    print("-" * 70)
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
                "priority_latency": d.get("priority_latency", 0.0),
                "high_priority_count": d.get("high_priority_count", 0),
                "medium_priority_count": d.get("medium_priority_count", 0),
                "low_priority_count": d.get("low_priority_count", 0),
                "active_evidence_count": d.get("active_evidence_count", 0),
                "retained_evidence_count": d.get("retained_evidence_count", 0),
                "average_priority_score": d.get("average_priority_score", 0.0),
                "total_model_calls": d.get("total_model_calls", 1),
                "stop_reason": d.get("stop_reason", "unknown"),
                "final_context_length": d.get("final_context_length", 0),
            }
            print(
                f"    Priority: High={result['high_priority_count']}, Med={result['medium_priority_count']}, Low={result['low_priority_count']} | "
                f"AvgScore={result['average_priority_score']:.4f} | "
                f"PriLatency={result['priority_latency']*1000:.2f}ms | "
                f"TotalLatency={result['total_latency']}s"
            )
            results.append(result)
        except Exception as exc:
            print(f"    FAILED: {exc}")
            results.append({"id": qid, "question": q, "status": "FAIL", "error": str(exc)})
    return results


def save_results(health, results):
    result_file = Path("experiments/S8_live_results_v1.json")
    output = {
        "experiment": "S8",
        "phase": "evidence-priority-evaluation",
        "health": health,
        "results": results,
    }
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to: {result_file}")


def main():
    with httpx.Client() as client:
        try:
            health = health_check(client)
        except Exception:
            print(f"ERROR: Cannot reach {BASE_URL}. Start uvicorn first.")
            sys.exit(1)

        results = run_workload(client, WORKLOAD_QUERIES)
        save_results(health, results)


if __name__ == "__main__":
    main()
