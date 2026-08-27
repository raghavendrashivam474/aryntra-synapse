"""
experiments/run_s6_full.py

Aryntra Synapse — Sprint 6
Full automated experiment runner.

Starts the server in each mode, runs the query set, collects results,
then runs the comparative analysis. No manual server management needed.

Usage:
    .venv/Scripts/python experiments/run_s6_full.py
"""

import subprocess
import sys
import time
import os
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. Run: .venv\\Scripts\\pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
MODES = ["selective_v1", "semantic_v1", "blended_v1"]
TIMEOUT = 180.0
STARTUP_WAIT = 45  # seconds to wait for server startup (including embedding model load)


def wait_for_server(server_proc, max_wait=STARTUP_WAIT):
    """Poll /health until the server responds or process exits."""
    print(f"  Waiting for server (up to {max_wait}s)...", end="", flush=True)
    for i in range(max_wait):
        if server_proc.poll() is not None:
            # Process died prematurely
            stdout, stderr = server_proc.communicate()
            print(f" PROCESS EXITED with code {server_proc.returncode}")
            if stderr:
                print(f"  STDERR:\n{stderr.decode('utf-8', errors='ignore')}")
            return None

        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                print(f" ready ({i+1}s)")
                return r.json()
        except Exception:
            pass
        time.sleep(1)
        if (i + 1) % 5 == 0:
            print(f" {i+1}s...", end="", flush=True)
    print(" TIMEOUT")
    return None


def run_experiment_for_mode(mode):
    """Run the S6 experiment for a single mode."""
    print(f"\n{'='*70}")
    print(f"  MODE: {mode}")
    print(f"{'='*70}")

    env = os.environ.copy()
    env["CONTEXT_REPRESENTATION"] = mode
    env["PYTHONPATH"] = "."

    print(f"  Starting uvicorn (main:app) with CONTEXT_REPRESENTATION={mode}...")
    server_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-level", "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        health = wait_for_server(server_proc)
        if not health:
            print(f"  ERROR: Server failed to start for {mode}")
            server_proc.terminate()
            return False

        actual_mode = health.get("context_representation", "unknown")
        print(f"  Confirmed server mode: {actual_mode}")

        if actual_mode != mode:
            print(f"  WARNING: Expected {mode}, got {actual_mode}")

        # Run experiment
        print(f"\n  Running queries...")
        result = subprocess.run(
            [sys.executable, "experiments/s6_experiment.py"],
            env=env,
            capture_output=False,
            timeout=600,
        )

        if result.returncode != 0:
            print(f"  WARNING: Experiment exited with code {result.returncode}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("  ERROR: Experiment timed out (10 min)")
        return False
    finally:
        print(f"\n  Stopping server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        time.sleep(2)  # Let the port free up


def run_analysis():
    """Run the S6 comparative analysis."""
    print(f"\n{'='*70}")
    print(f"  RUNNING COMPARATIVE ANALYSIS")
    print(f"{'='*70}")

    result = subprocess.run(
        [sys.executable, "experiments/s6_analysis.py"],
        capture_output=False,
        timeout=60,
    )
    return result.returncode == 0


def main():
    print("\n" + "=" * 70)
    print("  ARYNTRA SYNAPSE — S6 FULL EXPERIMENT SUITE")
    print("  Modes: selective_v1 → semantic_v1 → blended_v1")
    print("=" * 70)

    # Run each mode
    results = {}
    for mode in MODES:
        success = run_experiment_for_mode(mode)
        results[mode] = success
        if not success:
            print(f"\n  WARNING: {mode} failed. Continuing with remaining modes.")

    # Summary
    print(f"\n{'='*70}")
    print("  EXPERIMENT SUMMARY")
    print(f"{'='*70}")
    for mode, ok in results.items():
        status = "OK" if ok else "FAILED"
        f = Path(f"experiments/S6_results_{mode}.json")
        exists = "file exists" if f.exists() else "no file"
        print(f"  {mode:<16} {status:<8} ({exists})")

    # Run analysis
    run_analysis()


if __name__ == "__main__":
    main()
