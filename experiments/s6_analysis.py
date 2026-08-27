import json
import sys
from pathlib import Path

S5_FILE = Path("experiments/S5_results_v1.json")
S6_SEL_FILE = Path("experiments/S6_results_selective_v1.json")
S6_SEM_FILE = Path("experiments/S6_results_semantic_v1.json")
S6_BL_FILE = Path("experiments/S6_results_blended_v1.json")


def load_results(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def extract_passing(data):
    if not data:
        return {}
    return {
        r["id"]: r for r in data.get("results", [])
        if r.get("status") == "PASS"
    }


def compute_stats(results_dict, ids):
    n = len(ids)
    if n == 0:
        return {}
    sums = {
        "calls": 0, "cum_ctx": 0, "latency": 0,
        "steps": 0, "active": 0, "early_stops": 0,
        "semantic_scores": [],
    }
    stop_counts = {}
    for qid in ids:
        r = results_dict[qid]
        sums["calls"] += r.get("total_model_calls", 1)
        sums["cum_ctx"] += r.get("cumulative_context_length", 0)
        sums["latency"] += r.get("total_latency", 0)
        sums["steps"] += r.get("expansion_steps", 0)
        sums["active"] += r.get("workspace_active_chunks", 0)
        stop = r.get("stop_reason", "unknown")
        stop_counts[stop] = stop_counts.get(stop, 0) + 1
        if stop == "evidence_sufficient":
            sums["early_stops"] += 1

        slog = r.get("sufficiency_log", [])
        if slog and "semantic_score" in slog[-1]:
            sums["semantic_scores"].append(slog[-1]["semantic_score"])

    return {
        "n": n,
        "avg_calls": sums["calls"] / n,
        "avg_cum_ctx": sums["cum_ctx"] / n,
        "avg_latency": sums["latency"] / n,
        "avg_steps": sums["steps"] / n,
        "avg_active": sums["active"] / n,
        "early_stop_rate": sums["early_stops"] / n * 100,
        "stop_counts": stop_counts,
        "avg_semantic_score": (
            sum(sums["semantic_scores"]) / len(sums["semantic_scores"])
            if sums["semantic_scores"] else None
        ),
    }


def main():
    s5_data = load_results(S6_SEL_FILE) or load_results(S5_FILE)
    s6a_data = load_results(S6_SEM_FILE)
    s6b_data = load_results(S6_BL_FILE)

    if not s5_data:
        print("ERROR: Need S5 baseline results.")
        sys.exit(1)

    s5r = extract_passing(s5_data)
    s6ar = extract_passing(s6a_data) if s6a_data else {}
    s6br = extract_passing(s6b_data) if s6b_data else {}

    all_ids = sorted(set(s5r.keys()))
    if not all_ids:
        print("No matching queries found.")
        sys.exit(1)

    s5_stats = compute_stats(s5r, all_ids)
    s6a_stats = compute_stats(s6ar, all_ids) if s6ar else None
    s6b_stats = compute_stats(s6br, all_ids) if s6br else None

    print("\n" + "=" * 120)
    print("  S6 SEMANTIC SUFFICIENCY ANALYSIS")
    print("=" * 120)

    header = f"{'ID':<5} | {'S5 Stop':<22} | {'S5 Steps':<8} | {'S5 Ctx':<8}"
    if s6a_stats:
        header += f" | {'S6A Stop':<22} | {'S6A Sem':<7}"
    if s6b_stats:
        header += f" | {'S6B Stop':<22} | {'S6B Sem':<7}"
    print(header)
    print("-" * 120)

    for qid in all_ids:
        s5 = s5r[qid]
        row = (
            f"{qid:<5} | "
            f"{s5.get('stop_reason', '?'):<22} | "
            f"{s5.get('expansion_steps', 0):<8} | "
            f"{s5.get('cumulative_context_length', 0):<8}"
        )
        if s6ar and qid in s6ar:
            s6a = s6ar[qid]
            sem_a = "N/A"
            slog = s6a.get("sufficiency_log", [])
            if slog and "semantic_score" in slog[-1]:
                sem_a = f"{slog[-1]['semantic_score']:.3f}"
            row += f" | {s6a.get('stop_reason', '?'):<22} | {sem_a:<7}"
        if s6br and qid in s6br:
            s6b = s6br[qid]
            sem_b = "N/A"
            slog = s6b.get("sufficiency_log", [])
            if slog and "semantic_score" in slog[-1]:
                sem_b = f"{slog[-1]['semantic_score']:.3f}"
            row += f" | {s6b.get('stop_reason', '?'):<22} | {sem_b:<7}"
        print(row)

    print("-" * 120)

    print("\n  AGGREGATE STATISTICS")
    print("-" * 60)
    print(f"  {'Metric':<30} | {'S5':<12}", end="")
    if s6a_stats:
        print(f" | {'S6-A':<12}", end="")
    if s6b_stats:
        print(f" | {'S6-B':<12}", end="")
    print()
    print("-" * 60)

    def fmt(val, decimals=1):
        if val is None:
            return "N/A"
        return f"{val:.{decimals}f}"

    metrics = [
        ("Avg Model Calls", "avg_calls", 1),
        ("Avg Cumulative Context", "avg_cum_ctx", 0),
        ("Avg Latency (s)", "avg_latency", 2),
        ("Avg Expansion Steps", "avg_steps", 1),
        ("Avg Active Chunks", "avg_active", 1),
        ("Early Stop Rate (%)", "early_stop_rate", 1),
        ("Avg Semantic Score", "avg_semantic_score", 3),
    ]

    for label, key, dec in metrics:
        row = f"  {label:<30} | {fmt(s5_stats.get(key), dec):<12}"
        if s6a_stats:
            row += f" | {fmt(s6a_stats.get(key), dec):<12}"
        if s6b_stats:
            row += f" | {fmt(s6b_stats.get(key), dec):<12}"
        print(row)

    print("-" * 60)

    print("\n  STOP REASON DISTRIBUTIONS")
    print("-" * 60)
    print(f"  S5:  {s5_stats.get('stop_counts', {})}")
    if s6a_stats:
        print(f"  S6-A: {s6a_stats.get('stop_counts', {})}")
    if s6b_stats:
        print(f"  S6-B: {s6b_stats.get('stop_counts', {})}")

    print("\n  SAFETY CHECK (Unanswerable Queries Q9-Q10)")
    print("-" * 60)
    for qid in ["Q9", "Q10"]:
        if qid not in s5r:
            continue
        s5_stop = s5r[qid].get("stop_reason", "?")
        s6a_stop = s6ar[qid].get("stop_reason", "?") if s6ar and qid in s6ar else "N/A"
        s6b_stop = s6br[qid].get("stop_reason", "?") if s6br and qid in s6br else "N/A"
        safe_a = "SAFE" if s6a_stop != "evidence_sufficient" else "WARNING: FALSE STOP"
        safe_b = "SAFE" if s6b_stop != "evidence_sufficient" else "WARNING: FALSE STOP"
        print(
            f"  {qid}: S5={s5_stop:<22} "
            f"S6-A={s6a_stop:<22} [{safe_a}] "
            f"S6-B={s6b_stop:<22} [{safe_b}]"
        )

    print("\n" + "=" * 120 + "\n")


if __name__ == "__main__":
    main()
