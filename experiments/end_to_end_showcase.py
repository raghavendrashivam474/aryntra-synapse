"""
ARYNTRA SYNAPSE -- END-TO-END EVIDENCE INTELLIGENCE SHOWCASE

This showcase runs a complete end-to-end demonstration of the full Synapse stack.
It uses a deliberately messy, realistic evidence corpus containing:
  - 3 sequential document versions (v1.0, v2.0, v3.0) with conflicting rules
  - Highly relevant but obsolete/superseded files (semantic trap)
  - An active contradiction (MFA Mandatory vs MFA Optional on weekends)
  - Distractor documents with high semantic overlaps but zero applicability
  - Incomplete/unknown temporal metadata chunks

It executes three test cases:
  1. QUERY A (Current Policy): "What authentication policy should be followed now?" (Target: v3.0)
  2. QUERY B (Historical Policy): "What authentication policy applied in February 2025?" (Target: v2.0)
  3. QUERY C (Safety Trap): LLM tries to accept a superseded v1.0 document; deterministic veto blocks it.

Run:
  python experiments/end_to_end_showcase.py
"""

import sys
from pathlib import Path
import json

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evidence.unified import UnifiedEvidenceEngine, UnifiedEvidenceConfig
from app.evidence.adjudication import (
    MockAdjudicator,
    AdjudicationResult,
    AdjudicationDecision,
)


# ---------------------------------------------------------------------------
# 1. Deliberately Messy Corpus Definition
# ---------------------------------------------------------------------------

SHOWCASE_CORPUS = [
    {
        "chunk_id": "c1",
        "text": "Authentication policy version 1.0: MFA is optional for all corporate authentication systems. Effective 2024-01-01 to 2024-12-31.",
        "score": 0.96,
        "priority_score": 0.96,
        "relevance_score": 0.96,  # Semantic trap: Highest initial similarity, but obsolete!
        "document_id": "auth_policy",
        "version": "1.0",
        "effective_from": "2024-01-01",
        "effective_until": "2024-12-31",
        "superseded": True
    },
    {
        "chunk_id": "c2",
        "text": "Authentication policy version 2.0: MFA is recommended but optional for authentication. Effective from 2025-01-01 to 2025-12-31.",
        "score": 0.94,
        "priority_score": 0.94,
        "relevance_score": 0.94,  # Moderate semantic match, historically correct for 2025
        "document_id": "auth_policy",
        "version": "2.0",
        "supersedes": "c1",
        "effective_from": "2025-01-01",
        "effective_until": "2025-12-31",
        "superseded": True
    },
    {
        "chunk_id": "c3",
        "text": "Authentication policy version 3.0: Current authentication policy requires mandatory MFA across all systems. Effective from 2026-01-01.",
        "score": 0.91,
        "priority_score": 0.91,
        "relevance_score": 0.91,  # The only valid current authentication truth!
        "document_id": "auth_policy",
        "version": "3.0",
        "supersedes": "c2",
        "effective_from": "2026-01-01",
        "superseded": False
    },
    {
        "chunk_id": "c4",
        "text": "Operational guidance: Authentication is optional during scheduled weekend maintenance windows.",
        "score": 0.89,
        "priority_score": 0.89,
        "relevance_score": 0.89,  # Direct contradiction with c3 mandatory policy!
        "document_id": "ops_guidance",
        "version": "1.0",
        "effective_from": "2026-02-15",
        "superseded": False
    },
    {
        "chunk_id": "c5",
        "text": "The corporate parking fee policy is $50 per month, paid via payroll deduction.",
        "score": 0.20,
        "priority_score": 0.20,
        "relevance_score": 0.20,  # Pure distractor
        "document_id": "parking_manual",
        "version": "1.0",
        "effective_from": "2025-01-01"
    },
    {
        "chunk_id": "c6",
        "text": "Corporate cybersecurity authentication compliance standards follow strict access policies.",
        "score": 0.85,
        "priority_score": 0.85,
        "relevance_score": 0.85,  # Corroborating evidence
        "document_id": "cyber_compliance",
        "version": "3.2",
        "effective_from": "2026-01-01"
    },
    {
        "chunk_id": "c7",
        "text": "Database server configuration and infrastructure rules for authentication backends.",
        "score": 0.60,
        "priority_score": 0.60,
        "relevance_score": 0.60,  # Incomplete metadata record
        "document_id": "db_config"
    }
]


# ---------------------------------------------------------------------------
# 2. Output Decorator Functions
# ---------------------------------------------------------------------------

def print_banner(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_story(title, result):
    print(f"\n--- {title} ---")
    print(f"Query: \"{result.query}\"")
    print(f"Pipeline Decision: {result.decision} (Confidence: {result.confidence:.2f})")
    print(f"Execution Latency: {result.pipeline_time_ms:.2f} ms")
    
    # 1. Selected / Rejected Evidence
    sel_ids = [c["chunk_id"] for c in result.selected_evidence]
    rej_ids = [c["chunk_id"] for c in result.rejected_evidence]
    print(f"Selected Chunks:  {sel_ids}")
    print(f"Rejected Chunks:  {rej_ids}")
    
    # 2. Key Phase Summaries
    print("\n  INTELLIGENCE DASHBOARD")
    print(f"  ├─ Temporal State:  Intent={result.temporal_context.get('query_intent')}, Target={result.temporal_context.get('target_date')}")
    print(f"  ├─ Graph Structure: Nodes={result.relationships.get('node_count')}, Edges={result.relationships.get('edge_count')}")
    print(f"  ├─ Contradictions:  Detected={result.conflicts.get('detected')}, Conflict Score={result.conflicts.get('conflict_score')}")
    print(f"  ├─ Adjudication:   Triggered={result.adjudication.get('triggered')}, Decision={result.adjudication.get('decision')}, Vetoed={result.adjudication.get('veto_applied')}")
    print(f"  └─ Safety Veto:     Applied={result.safety.get('deterministic_veto')}, Reason={result.safety.get('veto_reason')}")

    # 3. Archaeology Explain Record
    if result.provenance:
        print("\n  DECISION NARRATIVE (ARCHAEOLOGY)")
        lines = result.provenance.explain().split("\n")
        for line in lines[:8]:
            if line.strip():
                print(f"    {line.strip()}")
        if len(lines) > 8:
            print("    ...")


# ---------------------------------------------------------------------------
# 3. Run Showcase Harness
# ---------------------------------------------------------------------------

def run_showcase():
    print_banner("ARYNTRA SYNAPSE -- END-TO-END EVIDENCE INTELLIGENCE SHOWCASE")
    print(f"Corpus Loaded: {len(SHOWCASE_CORPUS)} chunks from {len(set(c['document_id'] for c in SHOWCASE_CORPUS if 'document_id' in c))} different manuals.")
    print("Testing pipeline convergence on multi-signal constraints...")

    showcase_results = {}

    # -----------------------------------------------------------------------
    # TEST 1: Query A -- Current policy verification
    # -----------------------------------------------------------------------
    print_banner("CASE 1: CURRENT SYSTEM QUERY")
    engine_current = UnifiedEvidenceEngine()
    res_a = engine_current.process(
        query="What current authentication policy should be followed now?",
        candidates=SHOWCASE_CORPUS
    )
    print_story("PHASE MAP -- CASE 1 (CURRENT)", res_a)
    
    # Assert correct current selection (c3 is present, c1 and c2 are pruned as obsolete)
    sel_ids_a = {c["chunk_id"] for c in res_a.selected_evidence}
    has_c3 = "c3" in sel_ids_a
    has_no_c1 = "c1" not in sel_ids_a
    has_no_c2 = "c2" not in sel_ids_a
    case_1_ok = has_c3 and has_no_c1 and has_no_c2
    showcase_results["Case 1: Current Query Temporal + Version Lineage"] = "PASS" if case_1_ok else "FAIL"


    # -----------------------------------------------------------------------
    # TEST 2: Query B -- Historical query verification
    # -----------------------------------------------------------------------
    print_banner("CASE 2: HISTORICAL SYSTEM QUERY")
    engine_historical = UnifiedEvidenceEngine()
    res_b = engine_historical.process(
        query="What authentication policy applied in February 2025?",
        candidates=SHOWCASE_CORPUS
    )
    print_story("PHASE MAP -- CASE 2 (HISTORICAL)", res_b)
    
    # Assert correct historical selection (c2 is selected for 2025, c3 is pruned as future)
    sel_ids_b = {c["chunk_id"] for c in res_b.selected_evidence}
    has_c2 = "c2" in sel_ids_b
    has_no_c3 = "c3" not in sel_ids_b
    case_2_ok = has_c2 and has_no_c3
    showcase_results["Case 2: Historical Policy Targeting (2025-02)"] = "PASS" if case_2_ok else "FAIL"


    # -----------------------------------------------------------------------
    # TEST 3: Query C -- Safety Trap (LLM prefers obsolete document)
    # -----------------------------------------------------------------------
    print_banner("CASE 3: SEMANTIC SAFETY TRAP & DETERMINISTIC VETO")
    mock_adjudicator = MockAdjudicator()
    mock_adjudicator.set_response(AdjudicationResult(
        decision=AdjudicationDecision.ACCEPT,
        confidence=0.96,
        selected_evidence_ids=("c1",),  # Obsolete chunk!
        rationale="Chunk c1 has the highest relevance score and clearly allows optional password entry.",
        adjudication_time_ms=1.5
    ))
    
    engine_safe = UnifiedEvidenceEngine(adjudicator=mock_adjudicator)
    res_c = engine_safe.process(
        query="Is authentication optional or mandatory?",
        candidates=SHOWCASE_CORPUS
    )
    print_story("PHASE MAP -- CASE 3 (SAFETY OVERRIDE)", res_c)
    
    # Assert deterministic veto was applied
    veto_applied = res_c.safety.get("deterministic_veto") is True
    decision_uncertain = res_c.decision == "UNCERTAIN"
    case_3_ok = veto_applied and decision_uncertain
    showcase_results["Case 3: Deterministic Veto on Superseded Accept"] = "PASS" if case_3_ok else "FAIL"


    # -----------------------------------------------------------------------
    # 4. Final Scoreboard Verification
    # -----------------------------------------------------------------------
    print_banner("SHOWCASE SYSTEM CAPABILITY SCOREBOARD")
    all_passed = True
    for cap, status in showcase_results.items():
        print(f"  [{status}] {cap}")
        if status != "PASS":
            all_passed = False

    # Save artifacts
    results_path = REPO_ROOT / "experiments" / "end_to_end_showcase_results.json"
    trace_path = REPO_ROOT / "experiments" / "end_to_end_showcase_trace.json"
    
    try:
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in showcase_results.items()}, f, indent=2)
        if res_a.provenance:
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(res_a.provenance.to_dict(), f, indent=2)
        print(f"\nShowcase artifacts saved successfully to '{results_path.name}' and '{trace_path.name}'.")
    except Exception as exc:
        print(f"\nWarning: could not save artifacts: {exc}")

    print("\n" + "=" * 80)
    if all_passed:
        print("  OVERALL SYSTEM SHOWCASE STATUS: SUCCESS")
    else:
        print("  OVERALL SYSTEM SHOWCASE STATUS: FAILURE")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = run_showcase()
    sys.exit(0 if success else 1)
