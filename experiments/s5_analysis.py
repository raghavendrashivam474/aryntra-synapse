import json
import sys
from pathlib import Path

S4_FILE = Path("experiments/S4_results_v1.json")
S5_FILE = Path("experiments/S5_results_v1.json")


def main():
    if not S4_FILE.exists() or not S5_FILE.exists():
        print("ERROR: Need both S4_results_v1.json and S5_results_v1.json")
        sys.exit(1)

    s4 = json.loads(S4_FILE.read_text(encoding="utf-8"))
    s5 = json.loads(S5_FILE.read_text(encoding="utf-8"))

    s4r = {r["id"]: r for r in s4.get("results", []) if r.get("status") == "PASS"}
    s5r = {r["id"]: r for r in s5.get("results", []) if r.get("status") == "PASS"}
    ids = sorted(set(s4r.keys()).intersection(s5r.keys()))

    if not ids:
        print("No matching queries.")
        sys.exit(1)

    print("\n" + "=" * 110)
    print("  S4 WORKSPACE vs S5 SELECTIVE PROMOTION COMPARISON")
    print("=" * 110)
    print(f"{'ID':<5} | {'S4 Calls':<8} | {'S5 Calls':<8} | {'S4 Cum':<8} | {'S5 Cum':<8} | {'S4 Lat':<8} | {'S5 Lat':<8} | {'Steps':<5} | {'Stop Reason':<25}")
    print("-" * 110)

    n = len(ids)
    sums = {"s4_calls": 0, "s5_calls": 0, "s4_cum": 0, "s5_cum": 0, "s4_lat": 0, "s5_lat": 0, "steps": 0}
    stop_counts = {}
    early_stops = 0

    for qid in ids:
        s, e = s4r[qid], s5r[qid]
        s4c = s.get("total_model_calls", 1)
        s5c = e.get("total_model_calls", 1)
        s4cum = s.get("cumulative_context_length", 0)
        s5cum = e.get("cumulative_context_length", 0)
        s4l = s.get("total_latency", 0)
        s5l = e.get("total_latency", 0)
        steps = e.get("expansion_steps", 0)
        stop = e.get("stop_reason", "unknown")

        stop_counts[stop] = stop_counts.get(stop, 0) + 1
        if stop == "evidence_sufficient":
            early_stops += 1

        sums["s4_calls"] += s4c
        sums["s5_calls"] += s5c
        sums["s4_cum"] += s4cum
        sums["s5_cum"] += s5cum
        sums["s4_lat"] += s4l
        sums["s5_lat"] += s5l
        sums["steps"] += steps

        print(f"{qid:<5} | {s4c:<8} | {s5c:<8} | {s4cum:<8} | {s5cum:<8} | {s4l:<8.2f} | {s5l:<8.2f} | {steps:<5} | {stop:<25}")

    print("-" * 110)
    print(f"{'AVG':<5} | {sums['s4_calls']/n:<8.1f} | {sums['s5_calls']/n:<8.1f} | {sums['s4_cum']/n:<8.1f} | {sums['s5_cum']/n:<8.1f} | {sums['s4_lat']/n:<8.2f} | {sums['s5_lat']/n:<8.2f} | {sums['steps']/n:<5.1f} |")
    print("=" * 110)

    call_change = ((sums["s5_calls"]/n - sums["s4_calls"]/n) / (sums["s4_calls"]/n)) * 100 if sums["s4_calls"] > 0 else 0
    cum_change = ((sums["s5_cum"]/n - sums["s4_cum"]/n) / (sums["s4_cum"]/n)) * 100 if sums["s4_cum"] > 0 else 0
    lat_change = ((sums["s5_lat"]/n - sums["s4_lat"]/n) / (sums["s4_lat"]/n)) * 100 if sums["s4_lat"] > 0 else 0

    print(f"\n  Model Call Reduction:     {call_change:+.2f}%")
    print(f"  Cumulative Context Change: {cum_change:+.2f}%")
    print(f"  Latency Change:            {lat_change:+.2f}%")
    print(f"  Early-Stop Rate:           {early_stops}/{n} ({early_stops/n*100:.1f}%)")
    print(f"  Stop Reason Distribution:  {stop_counts}")
    print("=" * 110 + "\n")


if __name__ == "__main__":
    main()