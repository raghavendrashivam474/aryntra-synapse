#!/usr/bin/env python3
"""
SC-S2 Comparison Runner.

Reads the SC-S1 baseline result and the SC-S2 Synapse result,
produces a side-by-side comparison report, and writes a
machine-readable comparison artifact.

Usage (from repository root):
    python experiments/synapse_compare/sc_s2/run_comparison.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from comparison import load_result, compare

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASELINE_RESULT = SCRIPT_DIR.parent / "sc_s1" / "results" / "sc_s1_result.json"
SYNAPSE_RESULT = SCRIPT_DIR / "results" / "sc_s2_result.json"
COMPARISON_RESULT = SCRIPT_DIR / "results" / "sc_s2_comparison.json"

SEP = "=" * 57
THIN = "-" * 57


# ---------------------------------------------------------------------------
# Terminal report
# ---------------------------------------------------------------------------
def print_report(comp) -> None:
    """Print the human-readable comparison dashboard."""
    print()
    print(SEP)
    print("ARYNTRA SYNAPSE \u2014 SYNAPSE COMPARE")
    print("SC-S2: SYNAPSE ENTERS THE COMPARISON")
    print(SEP)
    print()
    print(f"Scenario: {comp.experiment_id}")
    print()
    print("Query:")
    print(f"  {comp.query}")
    print()

    # --- Baseline ---
    print(THIN)
    print("BASELINE (Lexical Retrieval)")
    print(THIN)
    b = comp.baseline
    print(f"  Execution:    {b.execution_status}")
    print(f"  Selected:     {b.selected_evidence}")
    print(f"  Decision:     {b.decision_output}")
    print(f"  Confidence:   {'N/A' if b.confidence is None else b.confidence}")
    print(f"  Evaluation:   {b.evaluation_status}")
    print()

    # --- Synapse ---
    print(THIN)
    print("ARYNTRA SYNAPSE (Unified Evidence Engine)")
    print(THIN)
    s = comp.synapse
    print(f"  Execution:    {s.execution_status}")
    print(f"  Selected:     {s.selected_evidence}")
    print(f"  Decision:     {s.decision_output}")
    print(f"  Confidence:   {s.confidence}")
    if s.temporal_intent is not None:
        print(f"  Temporal:     intent={s.temporal_intent}")
    if s.conflict_score is not None:
        print(f"  Conflict:     score={s.conflict_score}")
    if s.sufficiency_score is not None:
        print(f"  Sufficiency:  score={s.sufficiency_score}")
    print(f"  Evaluation:   {s.evaluation_status}")
    print()

    # --- Comparison ---
    print(THIN)
    print("COMPARISON")
    print(THIN)
    print(f"  Input integrity:      {comp.input_integrity}")
    print(f"  Evidence match:       {comp.evidence_selection_match}")
    print(f"  Baseline correct:     {comp.baseline_selected_current}")
    print(f"  Synapse correct:      {comp.synapse_selected_current}")
    print(f"  Decision comparison:  {comp.decision_comparison}")
    print()

    if comp.notes:
        print("  Observations:")
        for note in comp.notes:
            print(f"    \u2022 {note}")
        print()

    print(f"Result file: {COMPARISON_RESULT}")
    print(SEP)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("Loading baseline result...")
    baseline = load_result(BASELINE_RESULT)
    print(f"  {BASELINE_RESULT}")

    print("Loading Synapse result...")
    synapse = load_result(SYNAPSE_RESULT)
    print(f"  {SYNAPSE_RESULT}")

    print("Running comparison...")
    comp = compare(baseline, synapse)

    print_report(comp)

    # Save comparison JSON
    COMPARISON_RESULT.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPARISON_RESULT, "w", encoding="utf-8") as f:
        f.write(comp.to_json())
    print(f"Comparison saved to {COMPARISON_RESULT}")


if __name__ == "__main__":
    main()
