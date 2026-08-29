"""
Aryntra Synapse — Sprint 15
Minimum Sufficient Evidence (MSE) Controller.

Determines whether the current assembled evidence set is sufficient
to answer a query, or whether Synapse should expand further.

Multi-signal evaluation (all deterministic, zero LLM calls):
  Signal 1 — Query coverage      (from CoverageAnalyzer)
  Signal 2 — Evidence support     (mean relevance of selected chunks)
  Signal 3 — Unresolved concepts  (missing facets from CoverageReport)
  Signal 4 — Conflict state       (from ContradictionDetector)
  Signal 5 — Redundancy           (inverse of best marginal gain)
  Signal 6 — Marginal gain        (best remaining candidate contribution)

Design invariant: This module NEVER calls an LLM or embedding model.
All signals are derived from S14's existing CoverageAnalyzer and
ContradictionDetector outputs plus chunk metadata.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

from app.evidence.coverage import CoverageAnalyzer, CoverageReport
from app.evidence.contradiction import ConflictReport

logger = logging.getLogger(__name__)


class SufficiencyDecision(str, Enum):
    """S15 sufficiency decision for the assembly control loop."""
    SUFFICIENT = "sufficient"      # STOP  — evidence set is adequate
    INSUFFICIENT = "insufficient"  # EXPAND — more evidence needed
    UNCERTAIN = "uncertain"        # CONSERVATIVE — defer to safe expansion


@dataclass
class SufficiencyResult:
    """Structured output of the sufficiency evaluation."""
    decision: SufficiencyDecision
    sufficiency_score: float  # 0.0 (clearly insufficient) to 1.0 (clearly sufficient)
    signals: Dict[str, float]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "sufficiency_score": round(self.sufficiency_score, 4),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "reason": self.reason,
        }


class SufficiencyEvaluator:
    """
    Minimum Sufficient Evidence evaluator.

    Combines six deterministic signals into a sufficiency score and
    returns a STOP / EXPAND / UNCERTAIN decision for the assembly loop.
    """

    def __init__(
        self,
        config: Optional["S15SufficiencyConfig"] = None,
        coverage_analyzer: Optional[CoverageAnalyzer] = None,
    ):
        from app.evidence.config import S15SufficiencyConfig
        self.config = config or S15SufficiencyConfig()
        self.coverage_analyzer = coverage_analyzer or CoverageAnalyzer()

    def evaluate(
        self,
        query: str,
        selected_chunks: List[Dict[str, Any]],
        remaining_candidates: List[Dict[str, Any]],
        coverage_report: CoverageReport,
        conflict_report: ConflictReport,
    ) -> SufficiencyResult:
        """
        Evaluate whether the current evidence set is sufficient.
        """
        if not selected_chunks:
            return SufficiencyResult(
                decision=SufficiencyDecision.INSUFFICIENT,
                sufficiency_score=0.0,
                signals=self._empty_signals(),
                reason="no_evidence_selected",
            )

        # ── Signal 1: Query coverage (0-1, higher = better) ──
        s_coverage = coverage_report.coverage_ratio

        # ── Signal 2: Evidence support (mean relevance, 0-1) ──
        scores = [
            c.get("priority_score", c.get("score", 0.5))
            for c in selected_chunks
        ]
        s_support = sum(scores) / len(scores) if scores else 0.0

        # ── Signal 3: Unresolved concepts (0-1, higher = fewer gaps) ──
        total_concepts = len(coverage_report.query_concepts)
        missing_count = len(coverage_report.missing_concepts)
        if total_concepts > 0:
            s_unresolved = 1.0 - (missing_count / total_concepts)
        else:
            s_unresolved = 1.0

        # ── Signal 4: Conflict state (0-1, higher = less conflict) ──
        s_conflict = 1.0 - conflict_report.conflict_score

        # ── Signals 5 & 6: Redundancy and Marginal gain ──
        s_marginal, s_redundancy = self._compute_marginal_signals(
            query, selected_chunks, remaining_candidates
        )

        # ── Weighted base combination ──
        score = (
            self.config.coverage_weight * s_coverage
            + self.config.support_weight * s_support
            + self.config.unresolved_weight * s_unresolved
            + self.config.conflict_weight * s_conflict
            + self.config.redundancy_weight * s_redundancy
            + self.config.marginal_gain_weight * s_marginal
        )

        # ── Special Rules & Priority Invariants ──
        has_severe_conflict = (
            conflict_report.detected
            and conflict_report.conflict_score >= self.config.conflict_veto_threshold
        )

        # Rule A: Redundancy / exhaustion boost ONLY if NO severe conflict
        if not has_severe_conflict:
            # No remaining candidates + adequate coverage → declare sufficient
            if not remaining_candidates and s_coverage >= self.config.sufficient_threshold:
                score = max(score, self.config.sufficient_threshold)
            # High redundancy + decent coverage → lean stop
            elif (
                s_redundancy >= 0.90
                and s_coverage >= self.config.sufficient_threshold * 0.85
            ):
                score = max(score, self.config.sufficient_threshold)

        # Rule B: Conflict Veto (Hard safety ceiling)
        # Severe conflict with incomplete coverage MUST NOT declare sufficient
        if has_severe_conflict and s_coverage < self.config.conflict_veto_coverage_floor:
            # Force score below sufficient threshold into uncertain/insufficient
            score = min(score, self.config.sufficient_threshold - 0.05)

        score = max(0.0, min(1.0, score))

        # ── Decision thresholds ──
        if score >= self.config.sufficient_threshold:
            decision = SufficiencyDecision.SUFFICIENT
            reason = "multi_signal_sufficient"
        elif score < self.config.insufficient_threshold:
            decision = SufficiencyDecision.INSUFFICIENT
            reason = "multi_signal_insufficient"
        else:
            decision = SufficiencyDecision.UNCERTAIN
            reason = "ambiguous_signals" if not has_severe_conflict else "conflict_veto_active"

        signals = {
            "coverage": s_coverage,
            "support": s_support,
            "unresolved": s_unresolved,
            "conflict": s_conflict,
            "redundancy": s_redundancy,
            "marginal_gain": s_marginal,
        }

        logger.debug(
            "SufficiencyEvaluator: score=%.3f → %s (%s)",
            score, decision.value, reason,
        )

        return SufficiencyResult(
            decision=decision,
            sufficiency_score=round(score, 4),
            signals={k: round(v, 4) for k, v in signals.items()},
            reason=reason,
        )

    # ── Internal helpers ──

    def _compute_marginal_signals(
        self,
        query: str,
        selected_chunks: List[Dict[str, Any]],
        remaining_candidates: List[Dict[str, Any]],
    ) -> tuple:
        """Compute marginal gain and redundancy signals from top remaining candidates."""
        if not remaining_candidates:
            return 0.0, 1.0  # no gain possible, fully redundant

        probe_limit = min(self.config.marginal_probe_count, len(remaining_candidates))
        best_gain = 0.0

        for candidate in remaining_candidates[:probe_limit]:
            gain = self.coverage_analyzer.marginal_coverage_gain(
                query, selected_chunks, candidate
            )
            best_gain = max(best_gain, gain)

        # Normalize: a gain of 0.20 maps to 1.0
        s_marginal = min(1.0, best_gain / max(self.config.marginal_gain_floor * 10, 0.01))
        s_redundancy = 1.0 - s_marginal

        return s_marginal, s_redundancy

    @staticmethod
    def _empty_signals() -> Dict[str, float]:
        return {
            "coverage": 0.0,
            "support": 0.0,
            "unresolved": 0.0,
            "conflict": 1.0,
            "redundancy": 1.0,
            "marginal_gain": 0.0,
        }
