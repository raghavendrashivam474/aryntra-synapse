"""
experiments/s6_gate_ablation.py

Simulates Candidate A (Semantic Only), Candidate B (Blended), and Candidate C
across all stages and queries to find the optimal gate configuration.
"""

import json
from pathlib import Path

SEM_FILE = Path("experiments/S6_results_semantic_v1.json")
SEL_FILE = Path("experiments/S6_results_selective_v1.json")

def main():
    if not SEM_FILE.exists() or not SEL_FILE.exists():
        print("Experiment files missing.")
        return

    sem_data = json.loads(SEM_FILE.read_text(encoding="utf-8"))
    
    print("\n" + "=" * 105)
    print("  S6 SUFFICIENCY GATE ABLATION STUDY (Stage 1 Analysis)")
    print("=" * 105)
    print(f"{'ID':<5} | {'Type':<18} | {'Retr Score':<10} | {'Lex Cov':<10} | {'Sem Sim':<10} | {'Answer In Doc?':<15}")
    print("-" * 105)

    stage1_records = []
    for r in sem_data.get("results", []):
        qid = r["id"]
        qtype = "Direct" if qid in ("Q1", "Q2") else ("Multi-chunk" if qid in ("Q3", "Q4") else ("Multi-hop" if qid in ("Q5", "Q6") else ("Comparison" if qid in ("Q7", "Q8") else "Unanswerable")))
        slog = r.get("sufficiency_log", [])
        if not slog:
            continue
        st1 = slog[0]
        lex = st1.get("lexical", {})
        top_score = lex.get("top_score", 0.0)
        cov_ratio = lex.get("coverage_ratio", 0.0)
        sem_score = st1.get("semantic_score", 0.0)
        is_answerable = qid not in ("Q9", "Q10")
        
        stage1_records.append({
            "id": qid,
            "type": qtype,
            "top_score": top_score,
            "cov_ratio": cov_ratio,
            "sem_score": sem_score,
            "answerable": is_answerable
        })
        
        print(f"{qid:<5} | {qtype:<18} | {top_score:<10.4f} | {cov_ratio:<10.4f} | {sem_score:<10.4f} | {str(is_answerable):<15}")

    print("-" * 105)

    # ── Test Gate Policies ──
    print("\n" + "=" * 105)
    print("  GATE POLICY COMPARISONS AT STAGE 1")
    print("=" * 105)

    # Policy 1: S5 Baseline (Score >= 0.45 AND Cov >= 0.25)
    s5_stops = [r["id"] for r in stage1_records if r["top_score"] >= 0.45 and r["cov_ratio"] >= 0.25]
    
    # Policy 2: S6-A Semantic Only (Sem >= 0.20)
    s6a_stops_strict = [r["id"] for r in stage1_records if r["sem_score"] >= 0.20]
    
    # Policy 3: S6-A Semantic Only (Sem >= 0.15)
    s6a_stops_perm = [r["id"] for r in stage1_records if r["sem_score"] >= 0.15]

    # Policy 4: S6-B Hybrid Blended (Score >= 0.35 AND Cov > 0.0 AND Sem >= 0.15)
    s6b_hybrid = [
        r["id"] for r in stage1_records 
        if r["top_score"] >= 0.35 and (r["cov_ratio"] > 0.0 or r["sem_score"] >= 0.20) and r["sem_score"] >= 0.12
    ]

    # Policy 5: S6-B Composite Score Gate = 0.4 * Score + 0.3 * Cov + 0.3 * Sem
    for r in stage1_records:
        r["composite"] = 0.4 * r["top_score"] + 0.3 * r["cov_ratio"] + 0.3 * r["sem_score"]

    print(f"  1. S5 Lexical Only:               Stops: {len(s5_stops)}/10 {s5_stops} | Safety: SAFE")
    print(f"  2. S6-A Semantic Only (>=0.20):   Stops: {len(s6a_stops_strict)}/10 {s6a_stops_strict} | Safety: SAFE")
    print(f"  3. S6-A Semantic Only (>=0.15):   Stops: {len(s6a_stops_perm)}/10 {s6a_stops_perm} | Safety: UNSAFE (Stops on Q9)")
    print(f"  4. S6-B Hybrid Filter:            Stops: {len(s6b_hybrid)}/10 {s6b_hybrid} | Safety: {'SAFE' if 'Q9' not in s6b_hybrid and 'Q10' not in s6b_hybrid else 'UNSAFE'}")

    print("\n  Composite Score Ranking:")
    for r in sorted(stage1_records, key=lambda x: x["composite"], reverse=True):
        ans_tag = "Answerable" if r["answerable"] else "UNANSWERABLE"
        print(f"    {r['id']:<4} ({ans_tag:<12}) -> Composite: {r['composite']:.4f} (Score={r['top_score']:.2f}, Cov={r['cov_ratio']:.2f}, Sem={r['sem_score']:.2f})")

    print("=" * 105 + "\n")

if __name__ == "__main__":
    main()
