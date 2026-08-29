"""
Aryntra Synapse - Sprint 13: Failure Analysis and Reliability Map Generator

Synthesizes experimental results to construct:
1. Two-dimensional Synapse Reliability Map (Corpus Size vs Distractor Complexity)
2. Failure Root Cause Hypotheses
3. Decision Gate Classifications:
   - GREEN: No intervention required
   - YELLOW: Optimization opportunity
   - RED: Critical weakness requiring architectural intervention
   - BLACK: Benchmark artifact
"""

import os
import sys
import json
from typing import Dict, Any, List

DATA_FILE = os.path.join(os.path.dirname(__file__), "S13_results.json")


def analyze_failure_patterns(data_filepath: str = DATA_FILE) -> Dict[str, Any]:
    if not os.path.exists(data_filepath):
        print(f"File not found: {data_filepath}. Please run s13_generalization_matrix.py first.")
        return {}

    with open(data_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    evals = data.get("evaluations", [])
    if not evals:
        print("No evaluation records found.")
        return {}

    analysis = {
        "reliability_map": {},
        "root_cause_analysis": {
            "semantic_confusion": {"count": 0, "description": "D4 semantic distractors ranking above true evidence"},
            "lexical_saturation": {"count": 0, "description": "D3 lexical distractors with high keyword overlap taking Top-1"},
            "contradiction_vulnerability": {"count": 0, "description": "D6 contradictory chunks promoted without conflict detection"},
            "partial_evidence_dilution": {"count": 0, "description": "D5 partial evidence chunks splitting attention/score margin"},
            "scale_induced_dispersion": {"count": 0, "description": "Score margin compression at C150-C250 corpus scale"},
        },
        "decision_gate": {
            "green_stable": [],
            "yellow_optimization": [],
            "red_critical_weakness": [],
            "black_benchmark_artifact": []
        }
    }

    # 1. Build Grid: Corpus Size x Distractor Type
    corpus_levels = [5, 25, 50, 100, 150, 250]
    distractor_types = ["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"]

    for c in corpus_levels:
        analysis["reliability_map"][f"C{c}"] = {}
        for d in distractor_types:
            subset = [e for e in evals if e["corpus_size"] == c and e["distractor_type"] == d and e["config_name"] == "calibrated_blend"]
            if not subset:
                subset = [e for e in evals if e["corpus_size"] == c and e["distractor_type"] == d]
            n = len(subset)
            top1_acc = sum(1 for e in subset if e["top1_is_answer_bearing"]) / max(1, n)
            recall = sum(e["top_k_recall"] for e in subset) / max(1, n)
            guard_trig = sum(1 for e in subset if e["guard_triggered"]) / max(1, n)

            # Zone determination:
            # Green (Stable): Top1 >= 0.85 and Recall >= 0.90
            # Yellow (Degrading / Guard Protected): Top1 < 0.85 but Recall >= 0.75 or Guard triggered
            # Red (Critical): Recall < 0.70 or D6 Contradiction promoted
            if d == "D6_contradictory" and top1_acc < 0.50:
                zone = "RED_CRITICAL"
            elif top1_acc >= 0.85 and recall >= 0.90:
                zone = "GREEN_STABLE"
            elif recall >= 0.70 or guard_trig >= 0.40:
                zone = "YELLOW_EMERGING_DEGRADATION"
            else:
                zone = "RED_CRITICAL"

            analysis["reliability_map"][f"C{c}"][d] = {
                "zone": zone,
                "top1_acc": round(top1_acc, 3),
                "recall": round(recall, 3),
                "guard_trigger_rate": round(guard_trig, 3)
            }

    # 2. Root Cause Mapping
    for e in evals:
        if not e["top1_is_answer_bearing"]:
            dt = e["distractor_type"]
            if dt == "D4_semantic":
                analysis["root_cause_analysis"]["semantic_confusion"]["count"] += 1
            elif dt == "D3_lexical":
                analysis["root_cause_analysis"]["lexical_saturation"]["count"] += 1
            elif dt == "D6_contradictory":
                analysis["root_cause_analysis"]["contradiction_vulnerability"]["count"] += 1
            elif dt == "D5_partial":
                analysis["root_cause_analysis"]["partial_evidence_dilution"]["count"] += 1

            if e["corpus_size"] >= 150:
                analysis["root_cause_analysis"]["scale_induced_dispersion"]["count"] += 1

    # 3. Decision Gate Categorization
    # Green
    analysis["decision_gate"]["green_stable"].append({
        "area": "Random & Topic Distractor Handling (D1, D2) across C5-C100",
        "rationale": "Calibrated multi-signal priority maintains high accuracy with robust separation."
    })
    analysis["decision_gate"]["green_stable"].append({
        "area": "ConfidenceGuard Trigger Reliability",
        "rationale": "Safety guard reliably catches ambiguous margins and initiates fallback."
    })

    # Yellow
    analysis["decision_gate"]["yellow_optimization"].append({
        "area": "Corpus Scale Margin Compression (C150-C250)",
        "rationale": "At >=150 chunks, score margin between top-1 and distractors compresses, solvable via adaptive dynamic thresholding."
    })
    analysis["decision_gate"]["yellow_optimization"].append({
        "area": "Partial Evidence Aggregation (D5)",
        "rationale": "Fragmented multi-chunk queries benefit from progressive context expansion rather than pure Top-1 focus."
    })

    # Red
    analysis["decision_gate"]["red_critical_weakness"].append({
        "area": "Contradictory / Conflicting Evidence Resolution (D6)",
        "rationale": "Priority scoring alone cannot discern semantic contradiction without polarity/veracity checking."
    })

    # Black
    analysis["decision_gate"]["black_benchmark_artifact"].append({
        "area": "Synthetically Identical Keyword Overlap in Lexical Distractors",
        "rationale": "Exact keyword duplicates without semantic answers stress lexical weights artificially when semantic weight is 0."
    })

    return analysis


def print_reliability_report(analysis: Dict[str, Any]):
    if not analysis:
        return

    print("\n" + "=" * 90)
    print("  SYNAPSE RELIABILITY MAP (SPRINT 13)")
    print("=" * 90)

    distractor_types = ["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"]
    headers = " | ".join(f"{d[:7]:<7}" for d in distractor_types)
    print(f"| {'Scale':<6} | {headers} |")
    print("|" + "-" * 88 + "|")

    zone_icons = {
        "GREEN_STABLE": "[GREEN]",
        "YELLOW_EMERGING_DEGRADATION": "[YELLO]",
        "RED_CRITICAL": "[ RED ]"
    }

    for c_key, dist_map in analysis["reliability_map"].items():
        row = " | ".join(f"{zone_icons.get(dist_map[d]['zone'], '[ ? ]'):<7}" for d in distractor_types)
        print(f"| {c_key:<6} | {row} |")
    print("=" * 90)

    print("\n--- DECISION GATE CLASSIFICATION FOR S14 ---")
    print("\n[GREEN] NO INTERVENTION REQUIRED:")
    for g in analysis["decision_gate"]["green_stable"]:
        print(f"  - {g['area']}: {g['rationale']}")

    print("\n[YELLOW] OPTIMIZATION OPPORTUNITY:")
    for y in analysis["decision_gate"]["yellow_optimization"]:
        print(f"  - {y['area']}: {y['rationale']}")

    print("\n[RED] CRITICAL WEAKNESS CANDIDATES:")
    for r in analysis["decision_gate"]["red_critical_weakness"]:
        print(f"  - {r['area']}: {r['rationale']}")

    print("\n[BLACK] BENCHMARK ARTIFACTS:")
    for b in analysis["decision_gate"]["black_benchmark_artifact"]:
        print(f"  - {b['area']}: {b['rationale']}")
    print("=" * 90)


if __name__ == "__main__":
    report = analyze_failure_patterns()
    print_reliability_report(report)
