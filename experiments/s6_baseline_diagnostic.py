"""
experiments/s6_baseline_diagnostic.py

Quick health check to verify the server is running with the
expected S6 context representation mode.
"""

import sys
try:
    import httpx
except ImportError:
    print("ERROR: httpx is required.")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"

def main():
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=10)
        r.raise_for_status()
        d = r.json()
        mode = d.get("context_representation", "unknown")
        print(f"Server: {d.get('app_name')} v{d.get('version')}")
        print(f"Mode:   {mode}")
        print(f"Model:  {d.get('llm_model')}")
        print(f"Chunks: {d.get('chunk_count')}")
        print(f"Ready:  {d.get('retriever_ready')}")

        valid = ("selective_v1", "semantic_v1", "blended_v1")
        if mode in valid:
            print(f"\nOK: Mode '{mode}' is valid for S6 experiments.")
        else:
            print(f"\nWARNING: Mode '{mode}' is not an S6 test mode.")
            print(f"Expected one of: {valid}")
    except Exception as e:
        print(f"Cannot reach server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
