"""
Aryntra Synapse — S2 Context Compression Experiment Runner

Purpose:
    Execute the canonical S2 Query Set v1 against the active compressed
    configuration (CONTEXT_REPRESENTATION=compressed_v1) and output S2_results_v1.json.
"""

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
RESULT_FILE = Path("experiments/S2_results_v1.json")
BASELINE_FILE = Path("experiments/S2_baseline_results_v1.json")
TOP_K = 3
TIMEOUT = 120.0


def load_queries():
    if not QUERY_FILE.exists():
        raise FileNotFoundError(f"Query set not found: {QUERY_FILE}")
    text = QUERY_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*(Q\d+)\s*\|[^|]+\|\s*(.*?)\s*\|")
    queries = []
    for match in pattern.finditer(text):
        query_id = match.group(1)
        question = match.group(2).strip()
        if query_id.startswith("Q"):
            queries.append({"id": query_id, "question": question})
    if len(queries) != 10:
        raise ValueError(f"Expected 10 queries, found {len(queries)}.")
    return queries


def health_check(client):
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE — S2 COMPRESSION EXPERIMENT (compressed_v1)")
    print("=" * 70)
    print("\n[1/3] Health Check")
    print("-" * 40)
    response = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    print(f"  Status:                 {data.get('status')}")
    print(f"  App:                    {data.get('app_name')}")
    print(f"  Version:                {data.get('version')}")
    print(f"  Retriever ready:        {data.get('retriever_ready')}")
    print(f"  Chunk count:            {data.get('chunk_count')}")
    print(f"  Embedding model:        {data.get('embedding_model')}")
    print(f"  LLM model:              {data.get('llm_model')}")
    print(f"  Context representation: {data.get('context_representation')}")
    return data


def run_queries(client, queries):
    print("\n[2/3] Running S2 Query Set v1 (compressed_v1)")
    print("-" * 40)
    results = []

    for item in queries:
        query_id = item["id"]
        question = item["question"]
        print(f"\n{query_id}: {question}")
        print("." * 70)

        started = time.perf_counter()
        try:
            response = client.post(
                f"{BASE_URL}/ask",
                json={"text": question, "top_k": TOP_K},
                timeout=TIMEOUT,
            )
            elapsed = time.perf_counter() - started
            response.raise_for_status()
            data = response.json()

            retrieved_chunks = data.get("retrieved_chunks", [])
            meta = data.get("representation_metadata", {})

            result = {
                "id": query_id,
                "question": question,
                "status": "PASS",
                "answer": data.get("answer"),
                "num_chunks_retrieved": data.get("num_chunks_retrieved", len(retrieved_chunks)),
                "representation_type": data.get("representation_type", "compressed_v1"),
                "representation_build_latency": data.get("representation_build_latency", 0.0),
                "retrieval_latency": data.get("retrieval_latency"),
                "generation_latency": data.get("generation_latency"),
                "total_latency": data.get("total_latency", round(elapsed, 4)),
                "context_length": data.get("context_length"),
                "context_reduction_pct": meta.get("reduction_pct", 0.0),
                "compression_ratio": meta.get("compression_ratio", 1.0),
                "retrieved_chunks": retrieved_chunks,
                "representation_metadata": meta,
            }

            print(f"  Representation: {result['representation_type']} (build: {result['representation_build_latency']}s)")
            print(f"  Retrieval:      {result['retrieval_latency']}s")
            print(f"  Generation:     {result['generation_latency']}s")
            print(f"  Total:          {result['total_latency']}s")
            print(f"  Context:        {result['context_length']} chars (Reduction: {result['context_reduction_pct']}%)")
            results.append(result)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({"id": query_id, "question": question, "status": "FAIL", "error": str(exc)})

    return results


def save_results(health, results):
    output = {
        "experiment": "S2",
        "phase": "experimental-evaluation",
        "query_set": "S2 Query Set v1",
        "context_representation": health.get("context_representation"),
        "top_k": TOP_K,
        "health": health,
        "results": results,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {RESULT_FILE}")


def print_summary(results):
    passed = sum(1 for r in results if r["status"] == "PASS")
    print("\n[3/3] Summary")
    print("-" * 40)
    print(f"  Questions:      {len(results)}")
    print(f"  Passed:         {passed}")
    print(f"  Failed:         {len(results) - passed}")

    if BASELINE_FILE.exists():
        try:
            baseline_data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
            b_results = {r["id"]: r for r in baseline_data.get("results", [])}
            print("\n" + "=" * 80)
            print("  BASELINE (FLAT) vs S2 (COMPRESSED_V1) COMPARISON")
            print("=" * 80)
            print(f"{'ID':<5} | {'Base Gen (s)':<13} | {'S2 Gen (s)':<13} | {'Base Ctx':<10} | {'S2 Ctx':<10} | {'Reduction':<10}")
            print("-" * 80)
            for r in results:
                qid = r["id"]
                b = b_results.get(qid, {})
                b_gen = f"{b.get('generation_latency', 0.0):.2f}"
                s_gen = f"{r.get('generation_latency', 0.0):.2f}"
                b_ctx = str(b.get('context_length', 0))
                s_ctx = str(r.get('context_length', 0))
                red = f"{r.get('context_reduction_pct', 0.0):.1f}%"
                print(f"{qid:<5} | {b_gen:<13} | {s_gen:<13} | {b_ctx:<10} | {s_ctx:<10} | {red:<10}")
        except Exception as e:
            print(f"Could not load baseline comparison: {e}")

    print("\n" + "=" * 80)
    print("  S2 EXPERIMENT COMPLETE")
    print("=" * 80)


def main():
    queries = load_queries()
    print(f"Loaded {len(queries)} queries from {QUERY_FILE}")
    with httpx.Client() as client:
        health = health_check(client)
        if health.get("status") != "ok":
            print("\nERROR: Synapse health check failed.")
            sys.exit(1)
        results = run_queries(client, queries)
        save_results(health, results)
        print_summary(results)


if __name__ == "__main__":
    main()
