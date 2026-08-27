"""
experiments/s6_diagnostic_sweep.py

Analyzes per-chunk vs concatenated similarity distributions
and tests candidate thresholds per §19 of the S6 brief.
"""

import json
from pathlib import Path

SEM_FILE = Path("experiments/S6_results_semantic_v1.json")
BL_FILE = Path("experiments/S6_results_blended_v1.json")

def main():
    if not SEM_FILE.exists():
        print("S6 results not found.")
        return

    data = json.loads(SEM_FILE.read_text(encoding="utf-8"))
    
    print("\n" + "=" * 90)
    print("  S6 SEMANTIC SIMILARITY DISTRIBUTION ACROSS STAGES")
    print("=" * 90)
    print(f"{'ID':<5} | {'Question':<45} | {'Concatenated':<12} | {'Max Chunk':<10} | {'Mean Chunk':<10}")
    print("-" * 90)

    records = []
    for r in data.get("results", []):
        qid = r["id"]
        q = r["question"][:43] + ".." if len(r["question"]) > 45 else r["question"]
        slog = r.get("sufficiency_log", [])
        if not slog:
            continue
        first_stage = slog[0]
        c_score = first_stage.get("semantic_score", 0.0)
        max_chunk = first_stage.get("max_chunk_similarity", 0.0)
        mean_chunk = first_stage.get("mean_chunk_similarity", 0.0)
        records.append((qid, q, c_score, max_chunk, mean_chunk))
        print(f"{qid:<5} | {q:<45} | {c_score:<12.4f} | {max_chunk:<10.4f} | {mean_chunk:<10.4f}")

    print("-" * 90)

    # Threshold Sweep Simulation (Stage 1 / 1 Chunk)
    print("\n" + "=" * 90)
    print("  SIMULATION: EARLY-STOPPING AT STAGE 1 BY THRESHOLD (MAX CHUNK)")
    print("=" * 90)
    thresholds = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    
    for th in thresholds:
        stopped_qids = [qid for qid, _, _, max_c, _ in records if max_c >= th]
        is_q9_stopped = "Q9" in stopped_qids
        is_q10_stopped = "Q10" in stopped_qids
        safety = "SAFE" if not (is_q9_stopped or is_q10_stopped) else "UNSAFE (False Stop on Unanswerable)"
        print(f"  Threshold {th:.2f} -> Early Stops: {len(stopped_qids):<2}/10 {stopped_qids} | Safety: {safety}")

    print("=" * 90 + "\n")

if __name__ == "__main__":
    main()
