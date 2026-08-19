"""
manual_test.py

Aryntra Synapse — Sprint 0.2
Manual baseline test script.

Run with:
    python manual_test.py

Requires:
    - Server running: uvicorn main:app --reload
    - Ollama running with mistral available
"""

import json
import time
import sys

try:
    import httpx2 as httpx
except ImportError:
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx2 or httpx required. Run: pip install httpx2")
        sys.exit(1)


BASE_URL = "http://127.0.0.1:8000"

QUESTIONS = [
    "What is retrieval-augmented generation?",
    "What is FAISS and what is it used for?",
    "What embedding model does Synapse use?",
    "What is Ollama?",
    "What is Mistral?",
    "How does chunking work?",
    "What is the purpose of a baseline in research?",
    "What is the capital of France?",
]

SEPARATOR = "=" * 70


def print_header():
    print()
    print(SEPARATOR)
    print("  ARYNTRA SYNAPSE — S0.2 BASELINE MANUAL TEST")
    print(SEPARATOR)
    print()


def test_health(client):
    print("[1/3] Health Check")
    print("-" * 40)

    try:
        r = client.get(f"{BASE_URL}/health")
        data = r.json()
        print(f"  Status:          {data['status']}")
        print(f"  App:             {data['app_name']} v{data['version']}")
        print(f"  Retriever ready: {data['retriever_ready']}")
        print(f"  Chunk count:     {data['chunk_count']}")
        print(f"  Embedding model: {data['embedding_model']}")
        print(f"  LLM model:       {data['llm_model']}")
        print()
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        print()
        print("  Is the server running?")
        print("  Start it with: uvicorn main:app --reload")
        print()
        return False


def test_edge_cases(client):
    print("[2/3] Edge Cases")
    print("-" * 40)

    # Empty question
    print("  Empty question... ", end="")
    try:
        r = client.post(f"{BASE_URL}/ask", json={"text": ""})
        if r.status_code == 400:
            print("PASS (400 returned)")
        else:
            print(f"UNEXPECTED ({r.status_code})")
    except Exception as e:
        print(f"FAIL ({e})")

    # Whitespace question
    print("  Whitespace question... ", end="")
    try:
        r = client.post(f"{BASE_URL}/ask", json={"text": "   "})
        if r.status_code == 400:
            print("PASS (400 returned)")
        else:
            print(f"UNEXPECTED ({r.status_code})")
    except Exception as e:
        print(f"FAIL ({e})")

    # top_k exceeds chunk count
    print("  top_k=9999... ", end="")
    try:
        r = client.post(f"{BASE_URL}/ask", json={"text": "test", "top_k": 9999})
        if r.status_code == 200:
            print("PASS (200 returned)")
        else:
            print(f"UNEXPECTED ({r.status_code})")
    except Exception as e:
        print(f"FAIL ({e})")

    # top_k = 1
    print("  top_k=1... ", end="")
    try:
        r = client.post(f"{BASE_URL}/ask", json={"text": "test", "top_k": 1})
        data = r.json()
        count = len(data.get("retrieved_chunks", []))
        if r.status_code == 200 and count == 1:
            print("PASS (1 chunk returned)")
        else:
            print(f"UNEXPECTED (status={r.status_code}, chunks={count})")
    except Exception as e:
        print(f"FAIL ({e})")

    print()


def test_questions(client):
    print("[3/3] Full Question Set")
    print("-" * 40)
    print()

    results = []
    total_retrieval = 0
    total_generation = 0

    for i, question in enumerate(QUESTIONS, start=1):
        print(f"  Q{i}: {question}")
        print(f"  {'.' * 50}")

        try:
            r = client.post(
                f"{BASE_URL}/ask",
                json={"text": question, "top_k": 3},
                timeout=120.0,
            )
            data = r.json()

            answer = data.get("answer", "NO ANSWER")
            chunks = data.get("num_chunks_retrieved", 0)
            r_lat = data.get("retrieval_latency", 0)
            g_lat = data.get("generation_latency", 0)
            t_lat = data.get("total_latency", 0)
            ctx_len = data.get("context_length", 0)

            # Truncate answer for display
            display_answer = answer[:200] + "..." if len(answer) > 200 else answer

            print(f"  Answer:      {display_answer}")
            print(f"  Chunks:      {chunks}")
            print(f"  Retrieval:   {r_lat}s")
            print(f"  Generation:  {g_lat}s")
            print(f"  Total:       {t_lat}s")
            print(f"  Context:     {ctx_len} chars")

            # Chunk details
            for j, chunk in enumerate(data.get("retrieved_chunks", []), start=1):
                chunk_preview = chunk["text"][:80].replace("\n", " ")
                print(f"    Chunk {j}: [{chunk['chunk_id']}] score={chunk['score']}  \"{chunk_preview}...\"")

            total_retrieval += r_lat
            total_generation += g_lat

            results.append({
                "question": question,
                "status": "PASS",
                "chunks": chunks,
                "retrieval": r_lat,
                "generation": g_lat,
                "total": t_lat,
                "context_length": ctx_len,
            })

        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({
                "question": question,
                "status": "FAIL",
            })

        print()

    return results, total_retrieval, total_generation


def print_summary(results, total_retrieval, total_generation):
    print(SEPARATOR)
    print("  SUMMARY")
    print(SEPARATOR)
    print()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    print(f"  Questions:         {len(results)}")
    print(f"  Passed:            {passed}")
    print(f"  Failed:            {failed}")
    print()
    print(f"  Total retrieval:   {round(total_retrieval, 4)}s")
    print(f"  Total generation:  {round(total_generation, 4)}s")
    print(f"  Avg retrieval:     {round(total_retrieval / max(passed, 1), 4)}s")
    print(f"  Avg generation:    {round(total_generation / max(passed, 1), 4)}s")
    print()

    print("  Per-question breakdown:")
    print(f"  {'No':<4} {'Status':<8} {'Chunks':<8} {'Retr(s)':<10} {'Gen(s)':<10} {'Total(s)':<10} {'Ctx':<8}")
    print(f"  {'-'*4} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")

    for i, r in enumerate(results, start=1):
        if r["status"] == "PASS":
            print(f"  {i:<4} {r['status']:<8} {r['chunks']:<8} {r['retrieval']:<10} {r['generation']:<10} {r['total']:<10} {r['context_length']:<8}")
        else:
            print(f"  {i:<4} {'FAIL':<8} {'-':<8} {'-':<10} {'-':<10} {'-':<10} {'-':<8}")

    print()
    print(SEPARATOR)
    print("  S0.2 BASELINE TEST COMPLETE")
    print(SEPARATOR)
    print()


def main():
    print_header()

    client = httpx.Client(timeout=120.0)

    # Health check
    if not test_health(client):
        sys.exit(1)

    # Edge cases
    test_edge_cases(client)

    # Full question set
    results, total_retrieval, total_generation = test_questions(client)

    # Summary
    print_summary(results, total_retrieval, total_generation)

    client.close()


if __name__ == "__main__":
    main()
