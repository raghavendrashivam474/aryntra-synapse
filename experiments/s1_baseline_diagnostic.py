"""
Aryntra Synapse — S1 Baseline Diagnostic

Purpose:
    Run the frozen v0.2.0 baseline against the canonical S1 Query Set v1.

Requirements:
    - Synapse API running:
        uvicorn main:app --reload
    - Ollama running with Mistral available
    - httpx installed
"""

import json
import re
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required.")
    print("Run: pip install httpx")
    sys.exit(1)


BASE_URL = "http://127.0.0.1:8000"

QUERY_FILE = Path("docs/experiments/S1/QUERY_SET.md")
RESULT_FILE = Path("experiments/S1_baseline_results_v1.json")

TOP_K = 3
TIMEOUT = 120.0


def load_queries():
    """Load Q1-Q10 directly from the canonical QUERY_SET.md."""
    if not QUERY_FILE.exists():
        raise FileNotFoundError(f"Query set not found: {QUERY_FILE}")

    text = QUERY_FILE.read_text(encoding="utf-8")

    pattern = re.compile(
        r"\|\s*(Q\d+)\s*\|[^|]+\|\s*(.*?)\s*\|"
    )

    queries = []

    for match in pattern.finditer(text):
        query_id = match.group(1)
        question = match.group(2).strip()

        if query_id.startswith("Q"):
            queries.append({
                "id": query_id,
                "question": question,
            })

    if len(queries) != 10:
        raise ValueError(
            f"Expected 10 queries, found {len(queries)}."
        )

    return queries


def health_check(client):
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE — S1 BASELINE DIAGNOSTIC")
    print("=" * 70)

    print("\n[1/3] Health Check")
    print("-" * 40)

    response = client.get(
        f"{BASE_URL}/health",
        timeout=TIMEOUT,
    )

    response.raise_for_status()
    data = response.json()

    print(f"  Status:          {data.get('status')}")
    print(f"  App:             {data.get('app_name')}")
    print(f"  Version:         {data.get('version')}")
    print(f"  Retriever ready: {data.get('retriever_ready')}")
    print(f"  Chunk count:     {data.get('chunk_count')}")
    print(f"  Embedding model: {data.get('embedding_model')}")
    print(f"  LLM model:       {data.get('llm_model')}")

    return data


def run_queries(client, queries):
    print("\n[2/3] Running S1 Query Set v1")
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
                json={
                    "text": question,
                    "top_k": TOP_K,
                },
                timeout=TIMEOUT,
            )

            elapsed = time.perf_counter() - started

            response.raise_for_status()
            data = response.json()

            retrieved_chunks = data.get(
                "retrieved_chunks",
                []
            )

            result = {
                "id": query_id,
                "question": question,
                "status": "PASS",
                "answer": data.get("answer"),
                "num_chunks_retrieved": data.get(
                    "num_chunks_retrieved",
                    len(retrieved_chunks),
                ),
                "retrieval_latency": data.get(
                    "retrieval_latency"
                ),
                "generation_latency": data.get(
                    "generation_latency"
                ),
                "total_latency": data.get(
                    "total_latency",
                    round(elapsed, 4),
                ),
                "context_length": data.get(
                    "context_length"
                ),
                "retrieved_chunks": retrieved_chunks,
            }

            print(
                f"  Chunks:     "
                f"{result['num_chunks_retrieved']}"
            )
            print(
                f"  Retrieval:  "
                f"{result['retrieval_latency']}s"
            )
            print(
                f"  Generation: "
                f"{result['generation_latency']}s"
            )
            print(
                f"  Total:      "
                f"{result['total_latency']}s"
            )
            print(
                f"  Context:    "
                f"{result['context_length']} chars"
            )

            for i, chunk in enumerate(
                retrieved_chunks,
                start=1,
            ):
                print(
                    f"    Chunk {i}: "
                    f"[{chunk.get('chunk_id')}] "
                    f"score={chunk.get('score')}"
                )

            results.append(result)

        except Exception as exc:
            print(f"  FAILED: {exc}")

            results.append({
                "id": query_id,
                "question": question,
                "status": "FAIL",
                "error": str(exc),
            })

    return results


def save_results(health, results):
    """Save the complete diagnostic record as JSON."""

    output = {
        "experiment": "S1",
        "phase": "baseline-diagnostic",
        "query_set": "S1 Query Set v1",
        "baseline": "v0.2.0",
        "top_k": TOP_K,
        "health": health,
        "results": results,
    }

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"\nResults saved to: {RESULT_FILE}"
    )


def print_summary(results):
    passed = sum(
        1
        for result in results
        if result["status"] == "PASS"
    )

    failed = len(results) - passed

    retrieval_times = [
        result["retrieval_latency"]
        for result in results
        if result["status"] == "PASS"
        and result.get("retrieval_latency") is not None
    ]

    generation_times = [
        result["generation_latency"]
        for result in results
        if result["status"] == "PASS"
        and result.get("generation_latency") is not None
    ]

    print("\n[3/3] Summary")
    print("-" * 40)

    print(f"  Questions:        {len(results)}")
    print(f"  Passed:           {passed}")
    print(f"  Failed:           {failed}")

    if retrieval_times:
        print(
            f"  Avg retrieval:    "
            f"{sum(retrieval_times) / len(retrieval_times):.4f}s"
        )

    if generation_times:
        print(
            f"  Avg generation:   "
            f"{sum(generation_times) / len(generation_times):.4f}s"
        )

    print("\n" + "=" * 70)
    print("  S1 BASELINE DIAGNOSTIC COMPLETE")
    print("=" * 70)


def main():
    try:
        queries = load_queries()
    except Exception as exc:
        print(f"ERROR loading query set: {exc}")
        sys.exit(1)

    print(
        f"Loaded {len(queries)} queries "
        f"from {QUERY_FILE}"
    )

    try:
        with httpx.Client() as client:
            health = health_check(client)

            if health.get("status") != "ok":
                print("\nERROR: Synapse health check failed.")
                sys.exit(1)

            results = run_queries(
                client,
                queries,
            )

    except Exception as exc:
        print(f"\nERROR communicating with Synapse: {exc}")
        print(
            "\nMake sure the server is running with:"
        )
        print(
            "  uvicorn main:app --reload"
        )
        sys.exit(1)

    save_results(
        health,
        results,
    )

    print_summary(results)


if __name__ == "__main__":
    main()