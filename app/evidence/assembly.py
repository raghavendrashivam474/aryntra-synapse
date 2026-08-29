"""
Aryntra Synapse — Sprint 14
Progressive Evidence Assembly Engine (Bounded Greedy Assembly).

Constructs the optimal evidence set rather than single Top-1 chunk:
- Ranks candidates individually
- Selects strongest seed candidate
- Evaluates multi-concept coverage & contradiction presence
- Progressively incorporates complementary non-contradictory chunks
- Halts when sufficient, budget exhausted, or contradiction unresolved
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.evidence.contradiction import ContradictionDetector, ConflictReport
from app.evidence.coverage import CoverageAnalyzer, CoverageReport
from app.evidence.state import EvidenceState, RelationalEvidenceState
from app.evidence.config import S14ResolutionConfig

logger = logging.getLogger(__name__)


@dataclass
class AssemblyMetrics:
    total_candidates: int
    selected_count: int
    iterations: int
    final_coverage: float
    conflict_detected: bool
    conflict_score: float
    assembly_latency: float
    assembly_decision: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_candidates": self.total_candidates,
            "selected_count": self.selected_count,
            "iterations": self.iterations,
            "final_coverage": round(self.final_coverage, 4),
            "conflict_detected": self.conflict_detected,
            "conflict_score": round(self.conflict_score, 4),
            "assembly_latency": round(self.assembly_latency, 6),
            "assembly_decision": self.assembly_decision,
        }


@dataclass
class AssemblyResult:
    selected_chunks: List[Dict[str, Any]]
    relational_state: RelationalEvidenceState
    coverage_report: CoverageReport
    conflict_report: ConflictReport
    metrics: AssemblyMetrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_chunks": self.selected_chunks,
            "relational_state": self.relational_state.to_dict(),
            "coverage_report": self.coverage_report.to_dict(),
            "conflict_report": self.conflict_report.to_dict(),
            "metrics": self.metrics.to_dict(),
        }


class EvidenceAssembler:
    """
    Bounded progressive evidence assembler.
    Assembles a coherent, sufficient evidence set without combinatorial explosion.
    """

    def __init__(
        self,
        config: Optional[S14ResolutionConfig] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
        coverage_analyzer: Optional[CoverageAnalyzer] = None,
    ):
        self.config = config or S14ResolutionConfig.full_resolution()
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.coverage_analyzer = coverage_analyzer or CoverageAnalyzer(
            min_facet_coverage_threshold=self.config.min_coverage_target
        )

    def assemble(
        self,
        query: str,
        ranked_chunks: List[Dict[str, Any]],
    ) -> AssemblyResult:
        """
        Assemble the best coherent, multi-concept evidence set from ranked candidates.
        """
        t0 = time.perf_counter()

        if not ranked_chunks:
            empty_cov = self.coverage_analyzer.evaluate(query, [])
            empty_conf = ConflictReport(detected=False, conflict_score=0.0)
            latency = time.perf_counter() - t0
            return AssemblyResult(
                selected_chunks=[],
                relational_state=RelationalEvidenceState(
                    state=EvidenceState.INSUFFICIENT,
                    relevance_score=0.0,
                    coverage_ratio=0.0,
                    conflict_score=0.0,
                ),
                coverage_report=empty_cov,
                conflict_report=empty_conf,
                metrics=AssemblyMetrics(
                    total_candidates=0,
                    selected_count=0,
                    iterations=0,
                    final_coverage=0.0,
                    conflict_detected=False,
                    conflict_score=0.0,
                    assembly_latency=latency,
                    assembly_decision="no_candidates",
                ),
            )

        # Step 1: Start with strongest individual candidate
        selected: List[Dict[str, Any]] = [ranked_chunks[0]]
        remaining: List[Dict[str, Any]] = ranked_chunks[1:]
        iterations = 1

        # Check baseline coverage of top-1
        cov_report = self.coverage_analyzer.evaluate(query, selected)

        # Step 2: Bounded greedy complementary addition
        max_chunks = self.config.max_assembly_chunks
        max_iter = self.config.max_assembly_iterations

        while (
            len(selected) < max_chunks
            and iterations < max_iter
            and remaining
            and not cov_report.is_sufficient
        ):
            iterations += 1
            best_candidate_idx = -1
            best_gain = 0.0
            best_penalty = 1.0

            for idx, candidate in enumerate(remaining):
                gain = self.coverage_analyzer.marginal_coverage_gain(
                    query, selected, candidate
                )
                if gain <= 0.0:
                    continue

                # Check if adding candidate introduces severe contradiction
                test_set = selected + [candidate]
                conf_test = self.contradiction_detector.analyze(test_set)
                penalty = conf_test.conflict_score if conf_test.detected else 0.0

                effective_value = gain - (self.config.contradiction_penalty_weight * penalty)

                if effective_value > best_gain:
                    best_gain = effective_value
                    best_candidate_idx = idx
                    best_penalty = penalty

            if best_candidate_idx >= 0 and best_gain > 0.0:
                selected.append(remaining.pop(best_candidate_idx))
                cov_report = self.coverage_analyzer.evaluate(query, selected)
            else:
                # No further complementary gains available
                break

        # Step 3: Global contradiction check on assembled set + candidate pool context
        conflict_report = self.contradiction_detector.analyze(selected)
        pool_conflict = self.contradiction_detector.analyze(ranked_chunks[:max_chunks])
        if not conflict_report.detected and pool_conflict.detected and pool_conflict.conflict_score >= self.config.contradiction_threshold:
            # Candidate pool has direct conflict on top items
            conflict_report = pool_conflict

        # Step 4: Determine final relational evidence state
        if conflict_report.detected and conflict_report.conflict_score >= self.config.contradiction_threshold:
            state = EvidenceState.CONTRADICTORY
            decision = "conflict_detected_unresolved"
        elif cov_report.is_sufficient:
            state = EvidenceState.SUFFICIENT
            decision = "assembled_sufficient"
        elif cov_report.coverage_ratio > 0.0:
            state = EvidenceState.PARTIAL
            decision = "partial_coverage"
        else:
            state = EvidenceState.INSUFFICIENT
            decision = "insufficient"

        latency = time.perf_counter() - t0

        relational_state = RelationalEvidenceState(
            state=state,
            relevance_score=selected[0].get("priority_score", selected[0].get("score", 0.5)),
            coverage_ratio=cov_report.coverage_ratio,
            conflict_score=conflict_report.conflict_score,
            conflicting_with=list(conflict_report.conflicted_chunk_ids),
            covered_concepts=cov_report.covered_concepts,
            missing_concepts=cov_report.missing_concepts,
        )

        metrics = AssemblyMetrics(
            total_candidates=len(ranked_chunks),
            selected_count=len(selected),
            iterations=iterations,
            final_coverage=cov_report.coverage_ratio,
            conflict_detected=conflict_report.detected,
            conflict_score=conflict_report.conflict_score,
            assembly_latency=latency,
            assembly_decision=decision,
        )

        return AssemblyResult(
            selected_chunks=selected,
            relational_state=relational_state,
            coverage_report=cov_report,
            conflict_report=conflict_report,
            metrics=metrics,
        )
