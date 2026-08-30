"""
Aryntra Synapse — Sprint 14 + Sprint 15 + Sprint 16 + Sprint 17
Progressive Evidence Assembly Engine with Minimum Sufficient Evidence Control
and Evidence Relationship Graph.

S14: Bounded greedy assembly with conflict-aware selection.
S15: Multi-signal sufficiency evaluation replaces single coverage-ratio stopping.
S16: Temporal & version-aware evidence enrichment.
S17: Deterministic evidence relationship graph for structurally aware assembly.

The assembly loop now asks:
  "Would another evidence expansion materially improve my ability to answer?"
instead of:
  "Is coverage_ratio >= threshold?"

S17 adds:
  "How do these evidence chunks relate to one another?"
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
    # S15 additions (defaults preserve S14 backward compatibility)
    sufficiency_score: float = -1.0
    sufficiency_decision: str = "not_evaluated"
    # S16 additions
    temporal_score: float = -1.0
    query_temporal_intent: str = "not_evaluated"
    # S17 additions
    relationship_edges: int = 0
    relationship_nodes: int = 0

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
            "sufficiency_score": round(self.sufficiency_score, 4),
            "sufficiency_decision": self.sufficiency_decision,
            "temporal_score": round(self.temporal_score, 4),
            "query_temporal_intent": self.query_temporal_intent,
            "relationship_edges": self.relationship_edges,
            "relationship_nodes": self.relationship_nodes,
        }


@dataclass
class AssemblyResult:
    selected_chunks: List[Dict[str, Any]]
    relational_state: RelationalEvidenceState
    coverage_report: CoverageReport
    conflict_report: ConflictReport
    metrics: AssemblyMetrics
    # S17 addition
    evidence_graph: Optional[Any] = None  # EvidenceGraph or None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "selected_chunks": self.selected_chunks,
            "relational_state": self.relational_state.to_dict(),
            "coverage_report": self.coverage_report.to_dict(),
            "conflict_report": self.conflict_report.to_dict(),
            "metrics": self.metrics.to_dict(),
        }
        if self.evidence_graph is not None:
            d["evidence_graph"] = self.evidence_graph.to_dict()
        return d


class EvidenceAssembler:
    """
    Bounded progressive evidence assembler with optional S15 MSE control,
    S16 temporal awareness, and S17 relationship graph.

    When sufficiency_evaluator is None, behaves identically to S14.
    When provided, the evaluator's multi-signal decision replaces the
    single coverage-ratio check in the expansion loop.
    """

    def __init__(
        self,
        config: Optional[S14ResolutionConfig] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
        coverage_analyzer: Optional[CoverageAnalyzer] = None,
        sufficiency_evaluator: Optional[Any] = None,  # SufficiencyEvaluator
    ):
        self.config = config or S14ResolutionConfig.full_resolution()
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.coverage_analyzer = coverage_analyzer or CoverageAnalyzer(
            min_facet_coverage_threshold=self.config.min_coverage_target
        )
        self.sufficiency_evaluator = sufficiency_evaluator
        self.temporal_analyzer = None  # S16: set via with_temporal()
        self.relationship_analyzer = None  # S17: set via with_relationships()

    @classmethod
    def with_sufficiency(
        cls,
        s14_config: Optional[S14ResolutionConfig] = None,
        s15_config: Optional[Any] = None,
    ) -> "EvidenceAssembler":
        """Convenience factory: assembler with S15 MSE evaluator enabled."""
        from app.evidence.sufficiency import SufficiencyEvaluator
        from app.evidence.config import S15SufficiencyConfig

        s14 = s14_config or S14ResolutionConfig.full_resolution()
        ca = CoverageAnalyzer(min_facet_coverage_threshold=s14.min_coverage_target)
        evaluator = SufficiencyEvaluator(
            config=s15_config or S15SufficiencyConfig.balanced(),
            coverage_analyzer=ca,
        )
        return cls(
            config=s14,
            coverage_analyzer=ca,
            sufficiency_evaluator=evaluator,
        )

    @classmethod
    def with_temporal(
        cls,
        s14_config=None,
        s15_config=None,
        s16_config=None,
    ) -> "EvidenceAssembler":
        """S16: Assembler with sufficiency AND temporal awareness."""
        from app.evidence.temporal import TemporalAnalyzer
        from app.evidence.config import S16TemporalConfig

        assembler = cls.with_sufficiency(
            s14_config=s14_config, s15_config=s15_config
        )
        assembler.temporal_analyzer = TemporalAnalyzer(
            config=s16_config or S16TemporalConfig.balanced()
        )
        return assembler

    @classmethod
    def with_relationships(
        cls,
        s14_config=None,
        s15_config=None,
        s16_config=None,
        s17_config=None,
    ) -> "EvidenceAssembler":
        """S17: Assembler with sufficiency, temporal, AND relationship awareness."""
        from app.evidence.relationships import RelationshipAnalyzer
        from app.evidence.config import S17RelationshipConfig

        assembler = cls.with_temporal(
            s14_config=s14_config,
            s15_config=s15_config,
            s16_config=s16_config,
        )
        assembler.relationship_analyzer = RelationshipAnalyzer(
            config=s17_config or S17RelationshipConfig.balanced(),
            contradiction_detector=assembler.contradiction_detector,
            temporal_analyzer=assembler.temporal_analyzer,
        )
        return assembler

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
            from app.evidence.relationships import EvidenceGraph
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
                evidence_graph=EvidenceGraph(),
            )

        # S16: Enrich chunks with temporal scores before assembly
        if self.temporal_analyzer:
            ranked_chunks = self.temporal_analyzer.enrich_chunks(
                query, ranked_chunks
            )

        # S17: Build evidence relationship graph over candidate pool
        evidence_graph = None
        if self.relationship_analyzer:
            from app.evidence.config import S17RelationshipConfig
            r_cfg = self.relationship_analyzer.config
            if getattr(r_cfg, "relationship_enabled", True):
                evidence_graph = self.relationship_analyzer.build_graph(ranked_chunks)
                # S17: Relationship-aware candidate reordering
                ranked_chunks = self._relationship_aware_reorder(
                    ranked_chunks, evidence_graph
                )

        # Step 1: Start with strongest individual candidate
        selected: List[Dict[str, Any]] = [ranked_chunks[0]]
        remaining: List[Dict[str, Any]] = ranked_chunks[1:]
        iterations = 1

        # Check baseline coverage of top-1
        cov_report = self.coverage_analyzer.evaluate(query, selected)

        # S15: Initial sufficiency evaluation
        suff_result = self._evaluate_sufficiency(
            query, selected, remaining, cov_report
        )
        keep_going = self._should_continue(cov_report, suff_result)

        # Step 2: Bounded greedy complementary addition
        max_chunks = self.config.max_assembly_chunks
        max_iter = self.config.max_assembly_iterations

        while (
            len(selected) < max_chunks
            and iterations < max_iter
            and remaining
            and keep_going
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

                # S15: Re-evaluate sufficiency after expansion
                suff_result = self._evaluate_sufficiency(
                    query, selected, remaining, cov_report
                )
                keep_going = self._should_continue(cov_report, suff_result)
            else:
                # No further complementary gains available
                break

        # Step 3: Global contradiction check on assembled set + candidate pool context
        conflict_report = self.contradiction_detector.analyze(selected)
        pool_conflict = self.contradiction_detector.analyze(ranked_chunks[:max_chunks])
        if not conflict_report.detected and pool_conflict.detected and pool_conflict.conflict_score >= self.config.contradiction_threshold:
            conflict_report = pool_conflict

        # Step 4: Determine final relational evidence state
        state, decision = self._determine_final_state(
            cov_report, conflict_report, suff_result
        )

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

        # S15: Include sufficiency info in metrics
        suff_score = suff_result.sufficiency_score if suff_result else -1.0
        suff_decision = suff_result.decision.value if suff_result else "not_evaluated"

        # S16: Compute aggregate temporal metrics
        t_scores = [c.get("temporal_score", -1.0) for c in selected]
        avg_temporal = sum(t_scores) / len(t_scores) if t_scores else -1.0
        q_intent = selected[0].get("query_temporal_intent", "not_evaluated") if selected else "not_evaluated"

        # S17: Graph metrics
        r_edges = evidence_graph.edge_count if evidence_graph else 0
        r_nodes = evidence_graph.node_count if evidence_graph else 0

        metrics = AssemblyMetrics(
            total_candidates=len(ranked_chunks),
            selected_count=len(selected),
            iterations=iterations,
            final_coverage=cov_report.coverage_ratio,
            conflict_detected=conflict_report.detected,
            conflict_score=conflict_report.conflict_score,
            assembly_latency=latency,
            assembly_decision=decision,
            sufficiency_score=suff_score,
            sufficiency_decision=suff_decision,
            temporal_score=avg_temporal,
            query_temporal_intent=q_intent,
            relationship_edges=r_edges,
            relationship_nodes=r_nodes,
        )

        return AssemblyResult(
            selected_chunks=selected,
            relational_state=relational_state,
            coverage_report=cov_report,
            conflict_report=conflict_report,
            metrics=metrics,
            evidence_graph=evidence_graph,
        )

    # ── S17 helper methods ──

    def _relationship_aware_reorder(
        self,
        chunks: List[Dict[str, Any]],
        graph: Any,
    ) -> List[Dict[str, Any]]:
        """
        S17: Reorder candidates using relationship graph signals.

        - Demote chunks that are superseded by other candidates in the pool.
        - Boost chunks that are the current head of a version chain.
        - NEVER remove chunks (safety invariant).
        """
        from app.evidence.relationships import RelationshipType

        r_cfg = self.relationship_analyzer.config
        demotion = getattr(r_cfg, "superseded_candidate_demotion", 0.20)
        boost = getattr(r_cfg, "current_version_head_boost", 0.05)

        for chunk in chunks:
            cid = str(chunk.get("chunk_id", chunk.get("id", "")))
            if not cid:
                continue

            # Check if this chunk is superseded by another candidate
            superseded_by = graph.get_superseded_by(cid)
            if superseded_by:
                current_score = chunk.get("combined_score", chunk.get("priority_score", chunk.get("score", 0.5)))
                chunk["combined_score"] = round(current_score * (1.0 - demotion), 4)
                chunk["_s17_superseded"] = True

            # Check if this chunk supersedes others (version chain head)
            supersedes = graph.get_supersedes(cid)
            if supersedes and not chunk.get("_s17_superseded"):
                current_score = chunk.get("combined_score", chunk.get("priority_score", chunk.get("score", 0.5)))
                chunk["combined_score"] = round(
                    min(1.0, current_score + boost), 4
                )
                chunk["_s17_version_head"] = True

        # Stable re-sort by combined_score
        return sorted(
            chunks,
            key=lambda x: (x.get("combined_score", 0.0), x.get("priority_score", 0.0)),
            reverse=True,
        )

    # ── S15 helper methods ──

    def _evaluate_sufficiency(
        self,
        query: str,
        selected: List[Dict[str, Any]],
        remaining: List[Dict[str, Any]],
        cov_report: CoverageReport,
    ) -> Optional[Any]:
        """Run S15 sufficiency evaluation if evaluator is configured."""
        if not self.sufficiency_evaluator:
            return None

        # Lightweight conflict check on current selection for the evaluator
        conf_report = self.contradiction_detector.analyze(selected)

        return self.sufficiency_evaluator.evaluate(
            query=query,
            selected_chunks=selected,
            remaining_candidates=remaining,
            coverage_report=cov_report,
            conflict_report=conf_report,
        )

    def _should_continue(
        self,
        cov_report: CoverageReport,
        suff_result: Optional[Any],
    ) -> bool:
        """Determine whether the assembly loop should continue."""
        if suff_result is None:
            # S14 fallback: single coverage-ratio check
            return not cov_report.is_sufficient

        from app.evidence.sufficiency import SufficiencyDecision
        # S15: Continue if INSUFFICIENT or UNCERTAIN (conservative)
        return suff_result.decision in (
            SufficiencyDecision.INSUFFICIENT,
            SufficiencyDecision.UNCERTAIN,
        )

    def _determine_final_state(
        self,
        cov_report: CoverageReport,
        conflict_report: ConflictReport,
        suff_result: Optional[Any],
    ) -> tuple:
        """Determine final EvidenceState and decision string."""
        # Conflict always takes priority (S14 invariant)
        if conflict_report.detected and conflict_report.conflict_score >= self.config.contradiction_threshold:
            return EvidenceState.CONTRADICTORY, "conflict_detected_unresolved"

        # S15-aware state assignment
        if suff_result is not None:
            from app.evidence.sufficiency import SufficiencyDecision
            if suff_result.decision == SufficiencyDecision.SUFFICIENT:
                return EvidenceState.SUFFICIENT, "mse_sufficient"
            elif suff_result.decision == SufficiencyDecision.UNCERTAIN:
                if cov_report.coverage_ratio > 0.5:
                    return EvidenceState.PARTIAL, "mse_uncertain_partial"
                return EvidenceState.UNRESOLVED, "mse_uncertain"
            else:
                if cov_report.coverage_ratio > 0.0:
                    return EvidenceState.PARTIAL, "mse_insufficient_partial"
                return EvidenceState.INSUFFICIENT, "mse_insufficient"

        # S14 original logic (when no evaluator)
        if cov_report.is_sufficient:
            return EvidenceState.SUFFICIENT, "assembled_sufficient"
        elif cov_report.coverage_ratio > 0.0:
            return EvidenceState.PARTIAL, "partial_coverage"
        else:
            return EvidenceState.INSUFFICIENT, "insufficient"
