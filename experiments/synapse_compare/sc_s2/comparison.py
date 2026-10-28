"""
SC-S2 Comparison Logic.

Reads the SC-S1 baseline result and the SC-S2 Synapse result,
validates input integrity, and produces a structured comparison.

This module does NOT reimplement either system. It compares
their recorded outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Comparison result structure
# ---------------------------------------------------------------------------
@dataclass
class SystemSummary:
    """Summary of one system's result for comparison display."""

    system: str
    execution_status: str
    selected_evidence: list[str]
    decision_output: str
    confidence: Optional[float]
    temporal_intent: Optional[str] = None
    conflict_score: Optional[float] = None
    sufficiency_score: Optional[float] = None
    evaluation_status: str = "NOT_EVALUATED"


@dataclass
class ComparisonResult:
    """Structured comparison of baseline vs Synapse."""

    experiment_id: str
    query: str
    input_integrity: str  # "MATCH" or description of mismatch
    baseline: SystemSummary
    synapse: SystemSummary
    evidence_selection_match: bool
    both_selected_current: bool
    baseline_selected_current: bool
    synapse_selected_current: bool
    decision_comparison: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def _summarize(s: SystemSummary) -> dict:
            d = {
                "system": s.system,
                "execution_status": s.execution_status,
                "selected_evidence": s.selected_evidence,
                "decision_output": s.decision_output,
                "confidence": s.confidence,
                "evaluation_status": s.evaluation_status,
            }
            if s.temporal_intent is not None:
                d["temporal_intent"] = s.temporal_intent
            if s.conflict_score is not None:
                d["conflict_score"] = s.conflict_score
            if s.sufficiency_score is not None:
                d["sufficiency_score"] = s.sufficiency_score
            return d

        return {
            "experiment_id": self.experiment_id,
            "query": self.query,
            "input_integrity": self.input_integrity,
            "baseline": _summarize(self.baseline),
            "synapse": _summarize(self.synapse),
            "evidence_selection_match": self.evidence_selection_match,
            "both_selected_current": self.both_selected_current,
            "baseline_selected_current": self.baseline_selected_current,
            "synapse_selected_current": self.synapse_selected_current,
            "decision_comparison": self.decision_comparison,
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------
def load_result(path: Path) -> dict:
    """Load a JSON result file. Raises on missing or invalid files."""
    if not path.is_file():
        raise FileNotFoundError(f"Result file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------
def check_integrity(baseline: dict, synapse: dict) -> str:
    """Verify both results refer to the same experiment.

    Returns 'MATCH' or a description of the first mismatch found.
    """
    if baseline.get("experiment_id") != synapse.get("experiment_id"):
        return f"experiment_id mismatch: {baseline.get('experiment_id')} vs {synapse.get('experiment_id')}"
    if baseline.get("query") != synapse.get("query"):
        return "query mismatch between baseline and synapse results"

    b_docs = sorted(baseline.get("corpus", {}).get("documents", []))
    s_docs = sorted(synapse.get("corpus", {}).get("documents", []))
    if b_docs != s_docs:
        return f"corpus mismatch: {b_docs} vs {s_docs}"

    return "MATCH"


# ---------------------------------------------------------------------------
# Comparison builder
# ---------------------------------------------------------------------------
def compare(baseline: dict, synapse: dict) -> ComparisonResult:
    """Build a structured comparison from two result dicts."""
    integrity = check_integrity(baseline, synapse)

    # --- Baseline summary ---
    b_eval = baseline.get("evaluation", {})
    b_decision = baseline.get("decision", {})
    b_selected = b_decision.get("selected_evidence", [])
    b_baseline_sel = b_eval.get("selected_current_document", False)

    baseline_summary = SystemSummary(
        system=baseline.get("system", "baseline"),
        execution_status="success",
        selected_evidence=b_selected,
        decision_output=b_decision.get("output", ""),
        confidence=None,
        evaluation_status=b_eval.get("status", "NOT_EVALUATED"),
    )

    # --- Synapse summary ---
    s_eval = synapse.get("evaluation", {})
    s_decision = synapse.get("decision", {})
    s_exec = synapse.get("execution", {})
    s_signals = synapse.get("signals", {})
    s_retrieval = synapse.get("retrieval", {})
    s_selected = s_retrieval.get(
        "selected_evidence",
        s_decision.get("selected_evidence", []),
    )
    s_synapse_sel = s_eval.get("selected_current_document", False)

    tc = s_signals.get("temporal_context", {})

    synapse_summary = SystemSummary(
        system=synapse.get("system", "synapse"),
        execution_status=s_exec.get("status", "unknown"),
        selected_evidence=s_selected,
        decision_output=s_decision.get("output", ""),
        confidence=s_decision.get("confidence"),
        temporal_intent=tc.get("query_intent"),
        conflict_score=s_signals.get("conflict_score"),
        sufficiency_score=s_signals.get("sufficiency_score"),
        evaluation_status=s_eval.get("status", "NOT_EVALUATED"),
    )

    # --- Comparison dimensions ---
    evidence_match = sorted(b_selected) == sorted(s_selected)

    # Decision comparison narrative
    notes: list[str] = []
    if integrity != "MATCH":
        notes.append(f"Input integrity check failed: {integrity}")

    if b_baseline_sel and not s_synapse_sel:
        decision_comp = "Baseline selected current policy; Synapse did not."
    elif s_synapse_sel and not b_baseline_sel:
        decision_comp = "Synapse selected current policy; Baseline did not."
    elif b_baseline_sel and s_synapse_sel:
        decision_comp = "Both systems selected the current policy."
    else:
        decision_comp = "Neither system selected the current policy."

    # Add analytical notes
    if not s_synapse_sel and s_decision.get("outcome") == "UNCERTAIN":
        notes.append("Synapse returned UNCERTAIN rather than confidently selecting outdated evidence.")
    if tc.get("query_intent") == "current":
        notes.append("Synapse detected temporal intent 'current' from the query.")
    rel = s_signals.get("relationships", {})
    if rel.get("edge_count", 0) > 0:
        notes.append(
            f"Synapse built a relationship graph ({rel.get('node_count')} nodes, {rel.get('edge_count')} edges)."
        )
    if s_signals.get("sufficiency_score", 0) == 0.0:
        notes.append(
            "Synapse sufficiency score was 0.0, indicating it recognized "
            "the evidence as insufficient for a definitive answer."
        )

    return ComparisonResult(
        experiment_id=baseline.get("experiment_id", "unknown"),
        query=baseline.get("query", ""),
        input_integrity=integrity,
        baseline=baseline_summary,
        synapse=synapse_summary,
        evidence_selection_match=evidence_match,
        both_selected_current=b_baseline_sel and s_synapse_sel,
        baseline_selected_current=b_baseline_sel,
        synapse_selected_current=s_synapse_sel,
        decision_comparison=decision_comp,
        notes=notes,
    )
