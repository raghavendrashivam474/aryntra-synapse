import json
import sys
from pathlib import Path

S3_FILE = Path("experiments/S3_results_v1.json")
S4_FILE = Path("experiments/S4_results_v1.json")


def main():
    if not S3_FILE.exists() or not S4_FILE.exists():
        print("ERROR: Need both S3_results_v1.json and S4_results_v1.json")
        sys.exit(1)

    s3 = json.loads(S3_FILE.read_text(encoding="utf-8"))
    s4 = json.loads(S4_FILE.read_text(encoding="utf-8"))

    s3r = {r["id"]: r for r in s3.get("results", []) if r.get("status") == "PASS"}
    s4r = {r["id"]: r for r in s4.get("results", []) if r.get("status") == "PASS"}
    ids = sorted(set(s3r.keys()).intersection(s4r.keys()))

    if not ids:
        print("No matching queries.")
        sys.exit(1)

    print("\n" + "=" * 100)
    print("  S3 PROGRESSIVE vs S4 EVIDENCE WORKSPACE COMPARISON")
    print("=" * 100)
    print(f"{'ID':<5} | {'S3 Cum':<8} | {'S4 Cum':<8} | {'S4 New':<8} | {'S4 Rep':<8} | {'S3 Lat':<8} | {'S4 Lat':<8} | {'Steps':<5} | {'Calls':<5}")
    print("-" * 100)

    n = len(ids)
    sums = {"s3_cum": 0, "s4_cum": 0, "s4_new": 0, "s4_rep": 0, "s3_lat": 0, "s4_lat": 0, "steps": 0, "calls": 0}

    for qid in ids:
        s, e = s3r[qid], s4r[qid]
        s3c = s.get("cumulative_context_length", 0)
        s4c = e.get("cumulative_context_length", 0)
        s4n = e.get("new_context_length", 0)
        s4r_ = e.get("repeated_context_length", 0)
        s3l = s.get("total_latency", 0)
        s4l = e.get("total_latency", 0)
        steps = e.get("expansion_steps", 0)
        calls = e.get("total_model_calls", 1)

        sums["s3_cum"] += s3c
        sums["s4_cum"] += s4c
        sums["s4_new"] += s4n
        sums["s4_rep"] += s4r_
        sums["s3_lat"] += s3l
        sums["s4_lat"] += s4l
        sums["steps"] += steps
        sums["calls"] += calls

        print(f"{qid:<5} | {s3c:<8} | {s4c:<8} | {s4n:<8} | {s4r_:<8} | {s3l:<8.2f} | {s4l:<8.2f} | {steps:<5} | {calls:<5}")

    print("-" * 100)
    print(f"{'AVG':<5} | {sums['s3_cum']/n:<8.1f} | {sums['s4_cum']/n:<8.1f} | {sums['s4_new']/n:<8.1f} | {sums['s4_rep']/n:<8.1f} | {sums['s3_lat']/n:<8.2f} | {sums['s4_lat']/n:<8.2f} | {sums['steps']/n:<5.1f} | {sums['calls']/n:<5.1f}")
    print("=" * 100)

    cum_change = ((sums["s4_cum"]/n - sums["s3_cum"]/n) / (sums["s3_cum"]/n)) * 100 if sums["s3_cum"] > 0 else 0
    lat_change = ((sums["s4_lat"]/n - sums["s3_lat"]/n) / (sums["s3_lat"]/n)) * 100 if sums["s3_lat"] > 0 else 0

    print(f"\n  Cumulative Context Change: {cum_change:+.2f}%")
    print(f"  Latency Change:            {lat_change:+.2f}%")
    print(f"  New vs Repeated Ratio:     {sums['s4_new']/n:.0f} new / {sums['s4_rep']/n:.0f} repeated per query")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()