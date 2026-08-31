import sys
import os

# BOOTSTRAP: Ensure the project root is in the python path
sys.path.append(os.getcwd())

import json
from app.evidence.unified import UnifiedEvidenceEngine

SHOWCASE_CORPUS = [
    {"id": "c1", "text": "Auth policy v1: Optional.", "metadata": {"version": "1.0", "date": "2025-01-01"}},
    {"id": "c2", "text": "Auth policy v2: Mandatory.", "metadata": {"version": "2.0", "date": "2025-02-01"}},
    {"id": "c3", "text": "Auth policy v3: Mandatory + MFA.", "metadata": {"version": "3.0", "date": "2025-03-01"}},
    {"id": "c4", "text": "Draft policy: Biometric.", "metadata": {"version": "4.0-alpha", "date": "2025-04-01"}},
    {"id": "c5", "text": "Archived: No password.", "metadata": {"version": "0.9", "date": "2024-12-01"}},
    {"id": "c6", "text": "Global Override: Mandatory for all.", "metadata": {"version": "3.1", "date": "2025-03-15"}},
    {"id": "c7", "text": "Guest policy: MFA exempt.", "metadata": {"version": "1.1", "date": "2025-01-15"}}
]

def print_dashboard(title, res):
    print("="*80)
    print(f"  {title}")
    print("="*80)
    print(f"Query: {res.query}")
    print(f"Decision: {res.decision} (Confidence: {res.confidence:.2f})")
    print(f"Latency: {res.pipeline_time_ms:.2f} ms")
    print(f"Selected: {[e['chunk_id'] for e in res.selected_evidence]}")
    print("-"*40)
    print("  INTELLIGENCE DASHBOARD")
    print(f"  - Temporal Intent: {res.temporal_context.get('query_intent')}")
    print(f"  - Target Date:     {res.temporal_context.get('target_date')}")
    print(f"  - Graph Nodes:     {res.relationships.get('node_count')}")
    print(f"  - Graph Edges:     {res.relationships.get('edge_count')}")
    print(f"  - Conflict Score:  {res.signals.get('conflict_score'):.2f}")
    print(f"  - Safety Veto:     {res.signals.get('safety_veto')}")
    print(f"  - Sufficiency:     {res.signals.get('sufficiency_score'):.2f}")
    print("\n")

def run():
    # Instantiate the engine verified in S21
    engine = UnifiedEvidenceEngine()
    
    # Case 1: Current (Should be calibrated)
    res_a = engine.process("What authentication policy is active now?", SHOWCASE_CORPUS)
    print_dashboard("CASE 1: CURRENT QUERY", res_a)
    
    # Case 2: Historical (S20 had 0.0 confidence, S21 should be calibrated)
    res_b = engine.process("What policy applied in Feb 2025?", SHOWCASE_CORPUS)
    print_dashboard("CASE 2: HISTORICAL QUERY", res_b)
    
    # Case 3: Safety Trap (Must remain 0.0 confidence)
    res_c = engine.process("Is authentication optional?", SHOWCASE_CORPUS)
    print_dashboard("CASE 3: SAFETY VETO CHECK", res_c)

if __name__ == "__main__":
    run()