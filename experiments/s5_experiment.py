import json
import re
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
QUERY_FILE = Path("docs/experiments/S2/QUERY_SET.md")
RESULT_FILE = Path("experiments/S5_results_v1.json")
TOP_K = 3
TIMEOUT = 180.0


def load_queries():
    if not QUERY_FILE.exists():
        alt = Path("docs/experiments/S5/QUERY_SET.md")
        if not alt.exists():
            raise FileNotFoundError("Query set not found.")
        text = alt.read_text(encoding="utf-8")
    else:
        text = QUERY_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*(Q\d+)\s*\|[^|]+\|\s*(.*?)\s*\|")
    queries = []
    for m in pattern.finditer(text):
        qid, q = m.group(1), m.group(2).strip()
        if qid.startswith("Q"):
            queries.append({"id": qid, "question": q})
    if len(queries) != 10:
        raise ValueError(f"Expected 10 queries, found {len(queries)}.")
    return queries


def health_check(client):
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE - S5 SELECTIVE PROMOTION EXPERIMENT")
    print("=" * 70)
    print("\n[1/3] Health Check")
    print("-" * 40)
    r = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    for k in ["status", "app_name", "version", "retriever_ready",
              "chunk_count", "llm_model", "context_representation"]:
        print(f"  {k}: {d.get(k)}")
    return d


def run_queries(client, queries):
    print("\n[2/3] Running S5 Query Set (selective_v1)")
    print("-" * 40)
    results = []
    for item in queries:
        qid, q = item["id"], item["question"]
        print(f"\n{qid}: {q}")
        started = time.perf_counter()
        try:
            r = client.post(f"{BASE_URL}/ask", json={"text": q, "top_k": TOP_K}, timeout=TIMEOUT)
            elapsed = time.perf_counter() - started
            r.raise_for_status()
            d = r.json()
            result = {
                "id": qid, "question": q, "status": "PASS",
                "answer": d.get("answer"),
                "retrieval_latency": d.get("retrieval_latency"),
                "generation_latency": d.get("generation_latency"),
                "total_latency": d.get("total_latency", round(elapsed, 4)),
                "expansion_steps": d.get("expansion_steps", 0),
                "total_model_calls": d.get("total_model_calls", 1),
                "initial_context_length": d.get("initial_context_length", 0),
                "final_context_length": d.get("final_context_length", 0),
                "cumulative_context_length": d.get("cumulative_context_length", 0),
                "workspace_active_chunks": d.get("workspace_active_chunks", 0),
                "stop_reason": d.get("stop_reason", "unknown"),
                "sufficiency_log": d.get("sufficiency_log", []),
            }
            print(f"  Stop: {result['stop_reason']} | Steps: {result['expansion_steps']} | Calls: {result['total_model_calls']}")
            print(f"  Active: {result['workspace_active_chunks']} | Final Ctx: {result['final_context_length']} | Latency: {result['total_latency']}s")
            results.append(result)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({"id": qid, "question": q, "status": "FAIL", "error": str(exc)})
    return results


def save_results(health, results):
    output = {
        "experiment": "S5", "phase": "selective-promotion-evaluation",
        "query_set": "S5 Query Set v1",
        "context_representation": "selective_v1",
        "top_k": TOP_K, "health": health, "results": results,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {RESULT_FILE}")


def print_summary(results):
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n[3/3] Summary: {passed}/{len(results)} passed")
    print("=" * 70)


def main():
    queries = load_queries()
    with httpx.Client() as client:
        try:
            health = health_check(client)
        except Exception:
            print(f"ERROR: Cannot reach {BASE_URL}. Start uvicorn first.")
            sys.exit(1)
        results = run_queries(client, queries)
        save_results(health, results)
        print_summary(results)


if __name__ == "__main__":
    main()