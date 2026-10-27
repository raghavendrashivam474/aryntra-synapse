#!/usr/bin/env python3
"""
SC-S2 Synapse Experiment Runner.

Executes the actual Aryntra Synapse engine against the shared
SC-S1 scenario, prints a terminal dashboard, and writes a
machine-readable result JSON.

Usage (from repository root):
    python experiments/synapse_compare/sc_s2/run_synapse.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from synapse_adapter import (
    EXPERIMENT_ID,
    QUERY,
    EXPECTED_CURRENT_DOCUMENT,
    load_sc_s1_fixtures,
    map_to_synapse_format,
    run_synapse_engine,
    normalize_engine_result,
    build_error_result,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RESULT_DIR = SCRIPT_DIR / "results"
RESULT_FILE = RESULT_DIR / "sc_s2_result.json"

SEP = "=" * 57


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def print_dashboard(result: dict) -> None:
    """Print the terminal demonstration output for the Synapse run."""
    print()
    print(SEP)
    print("ARYNTRA SYNAPSE \u2014 SYNAPSE COMPARE")
    print("SC-S2: SYNAPSE ENTERS THE COMPARISON")
    print(SEP)
    print()
    print(f"Scenario: {result['experiment_id']}")
    print()
    print("Query:")
    print(f"  {result['query']}")
    print()

    exec_info = result.get("execution", {})
    print(f"Execution status: {exec_info.get('status', 'unknown')}")
    if exec_info.get("pipeline_time_ms") is not None:
        print(f"Pipeline latency: {exec_info['pipeline_time_ms']:.2f} ms")
    print()

    retrieval = result.get("retrieval", {})
    print("Selected evidence:")
    for eid in retrieval.get("selected_evidence", []):
        print(f"  - {eid}")
    if not retrieval.get("selected_evidence"):
        print("  (none)")
    print()

    decision = result.get("decision", {})
    print("Decision:")
    print(f"  Outcome: {decision.get('outcome')}")
    print(f"  Confidence: {decision.get('confidence')}")
    print()

    signals = result.get("signals", {})
    if signals:
        print("Intelligence signals:")
        tc = signals.get("temporal_context", {})
        print(f"  Temporal intent: {tc.get('query_intent')}")
        print(f"  Target date:     {tc.get('target_date')}")
        print(f"  Conflict score:  {signals.get('conflict_score')}")
        print(f"  Safety veto:     {signals.get('safety_veto')}")
        print(f"  Sufficiency:     {signals.get('sufficiency_score')}")
        print(f"  Adjudication:    {signals.get('adjudication_decision')}")
        print()

    evaluation = result.get("evaluation", {})
    print("Evaluation:")
    print(f"  Expected current: {evaluation.get('expected_current_document')}")
    print(f"  Selected current: {evaluation.get('selected_current_document')}")
    print(f"  Status: {evaluation.get('status')}")
    print()
    print(f"Result file: {RESULT_FILE}")
    print(SEP)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("Loading SC-S1 canonical fixtures...")
    sc_s1_docs = load_sc_s1_fixtures()
    corpus_ids = [d["document_id"] for d in sc_s1_docs]
    print(f"  Loaded {len(sc_s1_docs)} documents: {corpus_ids}")

    print("Mapping to Synapse engine format...")
    synapse_corpus = map_to_synapse_format(sc_s1_docs)

    print("Invoking UnifiedEvidenceEngine...")
    try:
        engine_result = run_synapse_engine(QUERY, synapse_corpus)
        result = normalize_engine_result(engine_result, sc_s1_docs)
        print("  Engine execution: SUCCESS")
    except Exception as exc:
        print(f"  Engine execution: FAILED ({type(exc).__name__}: {exc})")
        result = build_error_result(QUERY, exc)

    # Print dashboard
    print_dashboard(result)

    # Save result JSON
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Result saved to {RESULT_FILE}")


if __name__ == "__main__":
    main()
