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
RESULT_FILE = Path("experiments/S3_results_v1.json")
CONTROL_FILE = Path("experiments/S2_results_v1.json")
TOP_K = 3
TIMEOUT = 120.0


def load_queries():
    if not QUERY_FILE.exists():
        # Fallback to S3 query set if S2 isn't present
        QUERY_FILE_ALT = Path("docs/experiments/S3/QUERY_SET.md")
        if not QUERY_FILE_ALT.exists():
            raise FileNotFoundError(f"Query set not found at S2 or S3 paths.")
        text = QUERY_FILE_ALT.read_text(encoding="utf-8")
    else:
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
    print("  ARYNTRA SYNAPSE — S3 PROGRESSIVE CONTEXT EXPERIMENT (progressive_v1)")
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
    
    if data.get("context_representation") != "progressive_v1":
        print("\nWARNING: context_representation is not set to 'progressive_v1'!")
        print("Please check your .env or app/core/config.py settings before proceeding.")
    return data


def run_queries(client, queries):
    print("\n[2/3] Running Canonical S3 Query Set v1 (progressive_v1)")
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

            results.append({
                "id": query_id,
                "question": question,
                "status": "PASS",
                "answer": data.get("answer"),
                "num_chunks_retrieved": data.get("num_chunks_retrieved"),
                "representation_type": data.get("representation_type"),
                "retrieval_latency": data.get("retrieval_latency"),
                "sufficiency_latency": data.get("sufficiency_latency", 0.0),
                "generation_latency": data.get("generation_latency"),
                "total_latency": data.get("total_latency", round(elapsed, 4)),
                "expansion_steps": data.get("expansion_steps", 0),
                "total_model_calls": data.get("total_model_calls", 1),
                "initial_context_length": data.get("initial_context_length", 0),
                "final_context_length": data.get("final_context_length", 0),
                "peak_context_length": data.get("peak_context_length", 0),
                "cumulative_context_length": data.get("cumulative_context_length", 0),
                "representation_metadata": data.get("representation_metadata", {}),
                "retrieved_chunks": data.get("retrieved_chunks", []),
            })

            r = results[-1]
            print(f"  Steps:        {r['expansion_steps']} (Model Calls: {r['total_model_calls']})")
            print(f"  Init Context: {r['initial_context_length']} chars | Final Context: {r['final_context_length']} chars")
            print(f"  Peak Context: {r['peak_context_length']} chars | Cumulative Exposure: {r['cumulative_context_length']} chars")
            print(f"  Latencies:    Retrieval: {r['retrieval_latency']}s | Sufficiency: {r['sufficiency_latency']}s | Gen: {r['generation_latency']}s")
            print(f"  Total Time:   {r['total_latency']}s")

        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({"id": query_id, "question": question, "status": "FAIL", "error": str(exc)})

    return results


def save_results(health, results):
    output = {
        "experiment": "S3",
        "phase": "progressive-evaluation",
        "query_set": "S3 Query Set v1",
        "context_representation": "progressive_v1",
        "top_k": TOP_K,
        "health": health,
        "results": results,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults successfully written to: {RESULT_FILE}")


def print_summary(results):
    passed = sum(1 for r in results if r["status"] == "PASS")
    print("\n[3/3] S3 Execution Summary")
    print("-" * 40)
    print(f"  Total Queries: {len(results)}")
    print(f"  Passed:        {passed}")
    print(f"  Failed:        {len(results) - passed}")
    print("=" * 70)


def main():
    try:
        queries = load_queries()
    except Exception as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    with httpx.Client() as client:
        try:
            health = health_check(client)
        except Exception as e:
            print(f"\nERROR: Could not communicate with server at {BASE_URL}. Ensure uvicorn is running.")
            sys.exit(1)
            
        results = run_queries(client, queries)
        save_results(health, results)
        print_summary(results)


if __name__ == "__main__":
    main()