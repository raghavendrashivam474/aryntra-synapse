import json
import sys
from pathlib import Path

CONTROL_FILE = Path("experiments/S2_results_v1.json")
EXPERIMENTAL_FILE = Path("experiments/S3_results_v1.json")


def load_data():
    if not CONTROL_FILE.exists():
        print(f"ERROR: Control file not found: {CONTROL_FILE}")
        sys.exit(1)
    if not EXPERIMENTAL_FILE.exists():
        print(f"ERROR: Experimental S3 file not found: {EXPERIMENTAL_FILE}")
        sys.exit(1)

    control = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
    experimental = json.loads(EXPERIMENTAL_FILE.read_text(encoding="utf-8"))
    return control, experimental


def main():
    control_data, experimental_data = load_data()

    c_results = {r["id"]: r for r in control_data.get("results", []) if r.get("status") == "PASS"}
    e_results = {r["id"]: r for r in experimental_data.get("results", []) if r.get("status") == "PASS"}

    shared_ids = sorted(list(set(c_results.keys()).intersection(e_results.keys())))

    if not shared_ids:
        print("No matching PASS queries found between Control and S3 results.")
        sys.exit(1)

    print("\n" + "=" * 90)
    print("  ARYNTRA SYNAPSE — S2 STATIC COMPRESSED VS S3 PROGRESSIVE COMPLEXITY COMPARISON")
    print("=" * 90)
    print(f"{'ID':<5} | {'Ctrl Ctx':<9} | {'S3 Init':<9} | {'S3 Peak':<9} | {'S3 Cum':<9} | {'Steps':<5} | {'Calls':<5} | {'Ctrl Lat':<8} | {'S3 Lat':<8}")
    print("-" * 90)

    total_ctrl_ctx = 0
    total_s3_init = 0
    total_s3_peak = 0
    total_s3_cum = 0
    total_steps = 0
    total_calls = 0
    total_ctrl_lat = 0.0
    total_s3_lat = 0.0

    steps_distribution = {0: 0, 1: 0, 2: 0}

    for qid in shared_ids:
        c = c_results[qid]
        e = e_results[qid]

        ctrl_ctx = c.get("context_length", 0)
        s3_init = e.get("initial_context_length", 0)
        s3_peak = e.get("peak_context_length", 0)
        s3_cum = e.get("cumulative_context_length", 0)
        steps = e.get("expansion_steps", 0)
        calls = e.get("total_model_calls", 1)
        ctrl_lat = c.get("total_latency", 0.0)
        s3_lat = e.get("total_latency", 0.0)

        steps_distribution[steps] = steps_distribution.get(steps, 0) + 1

        total_ctrl_ctx += ctrl_ctx
        total_s3_init += s3_init
        total_s3_peak += s3_peak
        total_s3_cum += s3_cum
        total_steps += steps
        total_calls += calls
        total_ctrl_lat += ctrl_lat
        total_s3_lat += s3_lat

        print(f"{qid:<5} | {ctrl_ctx:<9} | {s3_init:<9} | {s3_peak:<9} | {s3_cum:<9} | {steps:<5} | {calls:<5} | {ctrl_lat:<8.2f} | {s3_lat:<8.2f}")

    n = len(shared_ids)
    avg_ctrl_ctx = total_ctrl_ctx / n
    avg_s3_init = total_s3_init / n
    avg_s3_peak = total_s3_peak / n
    avg_s3_cum = total_s3_cum / n
    avg_steps = total_steps / n
    avg_calls = total_calls / n
    avg_ctrl_lat = total_ctrl_lat / n
    avg_s3_lat = total_s3_lat / n

    init_reduction = ((avg_ctrl_ctx - avg_s3_init) / avg_ctrl_ctx) * 100 if avg_ctrl_ctx > 0 else 0
    cum_overhead = ((avg_s3_cum - avg_ctrl_ctx) / avg_ctrl_ctx) * 100 if avg_ctrl_ctx > 0 else 0

    print("-" * 90)
    print(f"{'AVG':<5} | {avg_ctrl_ctx:<9.1f} | {avg_s3_init:<9.1f} | {avg_s3_peak:<9.1f} | {avg_s3_cum:<9.1f} | {avg_steps:<5.1f} | {avg_calls:<5.1f} | {avg_ctrl_lat:<8.2f} | {avg_s3_lat:<8.2f}")
    print("=" * 90)

    print("\n📊 RESEARCH METRICS SUMMARY:")
    print(f"  • Average Initial Context Reduction:  {init_reduction:.2f}% (Saved initial prompt budget)")
    print(f"  • Average Cumulative Prompt Overhead: {cum_overhead:.2f}% (Extra processed characters across all loops)")
    print(f"  • Context Sufficiency Distribution:")
    print(f"      - Stage 1 (1 Chunk Only):       {steps_distribution[0]} queries ({steps_distribution[0]/n*100:.1f}%)")
    print(f"      - Stage 2 (2 Chunks):            {steps_distribution[1]} queries ({steps_distribution[1]/n*100:.1f}%)")
    print(f"      - Stage 3 (3 Chunks Exposed):    {steps_distribution[2]} queries ({steps_distribution[2]/n*100:.1f}%)")
    print(f"  • Average LLM Invocations:           {avg_calls:.2f} calls per query (Baseline Control = 1.00)")
    print(f"  • Total Latency Ratio:               {avg_s3_lat/avg_ctrl_lat if avg_ctrl_lat > 0 else 1.00:.2f}x (S3 Progressive vs Control)")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()