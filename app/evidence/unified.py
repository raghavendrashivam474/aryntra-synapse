"""
S20 — Unified Evidence Intelligence Pipeline

Orchestrates S14-S19 into a single deterministic-first evidence
decision pipeline with complete provenance.

This module does NOT reimplement any intelligence subsystem.
It connects existing S14-S19 components into one coherent flow
and produces a single inspectable result.

Safety invariant (preserved from S18):
    Deterministic safety > Deterministic intelligence >
    Semantic adjudication > Final decision > Provenance record
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.evidence.state import EvidenceState, RelationalEvidenceState
from app.evidence.config import (
    S14ResolutionConfig,
    S15SufficiencyConfig,
    S16TemporalConfig,
    S17RelationshipConfig,
)
from app.evidence.assembly import EvidenceAssembler, AssemblyResult
from app.evidence.sufficiency import SufficiencyDecision, SufficiencyEvaluator
from app.evidence.temporal import TemporalAnalyzer, QueryTemporalIntent
from app.evidence.relationships import (
    RelationshipAnalyzer,
    RelationshipType,
    EvidenceGraph,
)
from app.evidence.adjudication import (
    AdjudicationCandidate,
    AdjudicationController,
    AdjudicationControllerConfig,
    AdjudicationDecision,
    ControlledAdjudicationResult,
    EvidenceAdjudicator,
    MockAdjudicator,
)
from app.evidence.provenance import (
    DecisionRecorder,
    DecisionRecord,
    NullDecisionRecorder,
    FinalStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class UnifiedEvidenceConfig:
    """S20 configuration surface.

    All defaults preserve existing S14-S19 behavior.
    Disabling a layer degrades gracefully — it does not crash.
    """
    temporal_enabled: bool = True
    relationship_enabled: bool = True
    sufficiency_enabled: bool = True
    adjudication_enabled: bool = True
    provenance_enabled: bool = True
    max_candidates: int = 50

    s14_config: Optional[S14ResolutionConfig] = None
    s15_config: Optional[S15SufficiencyConfig] = None
    s16_config: Optional[S16TemporalConfig] = None
    s17_config: Optional[S17RelationshipConfig] = None
    adjudication_config: Optional[AdjudicationControllerConfig] = None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class UnifiedEvidenceResult:
    """Single coherent result from the full S20 pipeline.

    Consumers receive this instead of interrogating seven subsystems.
    """
    query: str
    selected_evidence: List[Dict[str, Any]]
    rejected_evidence: List[Dict[str, Any]]
    confidence: float
    decision: str          # "SUFFICIENT" | "INSUFFICIENT" | "UNCERTAIN"
    relationships: Dict[str, Any]
    conflicts: Dict[str, Any]
    temporal_context: Dict[str, Any]
    sufficiency: Dict[str, Any]
    adjudication: Dict[str, Any]
    provenance: Optional[DecisionRecord]
    safety: Dict[str, Any]
    pipeline_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "selected_evidence": self.selected_evidence,
            "rejected_evidence": self.rejected_evidence,
            "confidence": round(self.confidence, 4),
            "decision": self.decision,
            "relationships": self.relationships,
            "conflicts": self.conflicts,
            "temporal_context": self.temporal_context,
            "sufficiency": self.sufficiency,
            "adjudication": self.adjudication,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "safety": self.safety,
            "pipeline_time_ms": round(self.pipeline_time_ms, 2),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class UnifiedEvidenceEngine:
    """S20 orchestration layer.

    Connects S14-S19 into one bounded, deterministic-first pipeline.
    Does NOT reimplement any subsystem algorithm.
    """

    def __init__(
        self,
        config: Optional[UnifiedEvidenceConfig] = None,
        adjudicator: Optional[EvidenceAdjudicator] = None,
    ):
        self.config = config or UnifiedEvidenceConfig()

        # ── S16 Temporal ──
        self._temporal: Optional[TemporalAnalyzer] = None
        if self.config.temporal_enabled:
            try:
                self._temporal = TemporalAnalyzer(config=self.config.s16_config)
            except Exception as exc:
                logger.warning("S20: TemporalAnalyzer init failed: %s", exc)

        # ── S17 Relationships ──
        self._relationships: Optional[RelationshipAnalyzer] = None
        if self.config.relationship_enabled:
            try:
                self._relationships = RelationshipAnalyzer(
                    config=self.config.s17_config,
                    temporal_analyzer=self._temporal,
                )
            except Exception as exc:
                logger.warning("S20: RelationshipAnalyzer init failed: %s", exc)

        # ── S14 + S15 Assembly ──
        self._assembler: Optional[EvidenceAssembler] = None
        try:
            self._assembler = EvidenceAssembler(config=self.config.s14_config)
            if self.config.sufficiency_enabled:
                try:
                    self._assembler.sufficiency_evaluator = SufficiencyEvaluator(
                        config=self.config.s15_config,
                        coverage_analyzer=self._assembler.coverage_analyzer,
                    )
                except Exception as exc:
                    logger.warning("S20: SufficiencyEvaluator attachment failed: %s", exc)
            if self._temporal is not None:
                self._assembler.temporal_analyzer = self._temporal
            if self._relationships is not None:
                self._assembler.relationship_analyzer = self._relationships
        except Exception as exc:
            logger.error("S20: EvidenceAssembler init failed: %s", exc)

        # ── S18 Adjudication ──
        self._adjudicator = adjudicator
        self._adjudication_controller: Optional[AdjudicationController] = None
        if self.config.adjudication_enabled:
            if self._adjudicator is None:
                self._adjudicator = MockAdjudicator()
            try:
                self._adjudication_controller = AdjudicationController(
                    adjudicator=self._adjudicator,
                    config=self.config.adjudication_config,
                )
            except Exception as exc:
                logger.warning(
                    "S20: AdjudicationController init failed: %s", exc,
                )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> UnifiedEvidenceResult:
        """Run the full S20 pipeline.

        Args:
            query: User query string.
            candidates: Evidence candidates from retrieval.
                Each dict should have at minimum ``chunk_id``/``id``
                and ``text``/``content``.

        Returns:
            UnifiedEvidenceResult with complete decision context.
        """
        start = time.perf_counter()

        # Bound candidates
        candidates = candidates[: self.config.max_candidates]

        # S19 — Provenance recorder
        recorder = self._make_recorder(query)
        try:
            recorder.record_candidates(
                [str(c.get("chunk_id", c.get("id", f"idx_{i}")))
                 for i, c in enumerate(candidates)]
            )
        except Exception:
            pass

        # ── Layer 1: Temporal enrichment ──
        temporal_ctx: Dict[str, Any] = {"enabled": False}
        enriched = list(candidates)
        if self._temporal is not None:
            enriched, temporal_ctx = self._run_temporal(
                query, candidates, recorder,
            )

        # ── Layer 2: Relationship graph ──
        graph: Optional[EvidenceGraph] = None
        rel_info: Dict[str, Any] = {"enabled": False}
        if self._relationships is not None:
            graph, rel_info = self._run_relationships(enriched, recorder)

        # ── Layer 3: Conflict-aware assembly (+ sufficiency) ──
        assembly = self._run_assembly(query, enriched, recorder)

        # ── Layer 4: Extract deterministic signals ──
        det_signals = self._extract_signals(assembly, graph)

        # ── Layer 5: Adjudication (selective) ──
        adj = self._run_adjudication(
            query, enriched, det_signals, recorder,
        )

        # ── Layer 6: Deterministic safety veto ──
        safety = self._evaluate_safety(adj, det_signals, recorder)

        # ── Layer 7: Partition evidence ──
        selected, rejected = self._partition_evidence(
            assembly, adj, safety, candidates,
        )

        # Record selections / rejections
        for ev in selected:
            try:
                recorder.record_selection(
                    str(ev.get("chunk_id", ev.get("id", ""))),
                    "selected by unified pipeline",
                )
            except Exception:
                pass
        for ev in rejected:
            try:
                recorder.record_rejection(
                    str(ev.get("chunk_id", ev.get("id", ""))),
                    "rejected by unified pipeline",
                )
            except Exception:
                pass

        # ── Finalize provenance ──
        decision_str = self._compute_decision(assembly, adj, safety)
        confidence = self._compute_confidence(assembly, adj, safety)
        record: Optional[DecisionRecord] = None
        try:
            status_map = {
                "SUFFICIENT": FinalStatus.SUFFICIENT,
                "INSUFFICIENT": FinalStatus.INSUFFICIENT,
            }
            status = status_map.get(decision_str, FinalStatus.UNCERTAIN)
            record = recorder.finalize(
                status=status,
                reason=f"unified_pipeline_{decision_str.lower()}",
            )
        except Exception:
            pass

        elapsed = (time.perf_counter() - start) * 1000

        return UnifiedEvidenceResult(
            query=query,
            selected_evidence=selected,
            rejected_evidence=rejected,
            confidence=confidence,
            decision=decision_str,
            relationships=rel_info,
            conflicts=self._conflict_summary(assembly),
            temporal_context=temporal_ctx,
            sufficiency=self._sufficiency_summary(assembly),
            adjudication=self._adjudication_summary(adj),
            provenance=record,
            safety=safety,
            pipeline_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Subsystem runners — each fails safely
    # ------------------------------------------------------------------

    def _run_temporal(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        recorder: DecisionRecorder,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        ctx: Dict[str, Any] = {"enabled": True}
        try:
            intent = self._temporal.extract_query_intent(query)
            ctx["query_intent"] = (
                intent.value if hasattr(intent, "value") else str(intent)
            )
            target = self._temporal.extract_query_target_date(query)
            ctx["target_date"] = target
        except Exception as exc:
            logger.warning("S20 temporal intent failed: %s", exc)
            ctx["error"] = str(exc)
            return list(candidates), ctx

        try:
            enriched = self._temporal.enrich_chunks(query, candidates)
            for c in enriched:
                cid = str(c.get("chunk_id", c.get("id", "")))
                score = c.get("temporal_score", 0.5)
                try:
                    recorder.record_temporal(
                        cid, score >= 0.5,
                        f"temporal_score={score:.3f}",
                    )
                except Exception:
                    pass
            ctx["enriched_count"] = len(enriched)
            return enriched, ctx
        except Exception as exc:
            logger.warning("S20 temporal enrichment failed: %s", exc)
            ctx["error"] = str(exc)
            return list(candidates), ctx

    def _run_relationships(
        self,
        candidates: List[Dict[str, Any]],
        recorder: DecisionRecorder,
    ) -> Tuple[Optional[EvidenceGraph], Dict[str, Any]]:
        info: Dict[str, Any] = {"enabled": True}
        try:
            graph = self._relationships.build_graph(candidates)
            info["node_count"] = graph.node_count() if callable(getattr(graph, "node_count", None)) else getattr(graph, "node_count", 0)
            info["edge_count"] = graph.edge_count() if callable(getattr(graph, "edge_count", None)) else getattr(graph, "edge_count", 0)
            try:
                for rel_type in RelationshipType:
                    for edge in graph.get_relationships_by_type(rel_type):
                        recorder.record_relationship(
                            edge.source_id, edge.target_id,
                            rel_type.value,
                            f"detected {rel_type.value}",
                        )
            except Exception:
                pass
            return graph, info
        except Exception as exc:
            logger.warning("S20 relationship analysis failed: %s", exc)
            info["error"] = str(exc)
            return None, info

    def _run_assembly(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        recorder: DecisionRecorder,
    ) -> Optional[AssemblyResult]:
        if self._assembler is None:
            return None
        try:
            result = self._assembler.assemble(query, candidates)
            try:
                state = result.relational_state.state
                is_suf = state in (
                    EvidenceState.SUFFICIENT, EvidenceState.SUPPORTING,
                )
                recorder.record_sufficiency(is_suf, f"state={state.value}")
            except Exception:
                pass
            return result
        except Exception as exc:
            logger.warning("S20 assembly failed: %s", exc)
            return None

    def _run_adjudication(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        det_signals: Dict[str, Any],
        recorder: DecisionRecorder,
    ) -> Optional[ControlledAdjudicationResult]:
        if self._adjudication_controller is None:
            return None
        try:
            adj_candidates = self._to_adjudication_candidates(candidates)
            try:
                recorder.record_adjudication_invoked(
                    [c.evidence_id for c in adj_candidates],
                    "unified_pipeline_gate",
                )
            except Exception:
                pass
            result = self._adjudication_controller.process(
                query, adj_candidates, det_signals,
            )
            try:
                recorder.record_adjudication_result(
                    result.final_decision.value,
                    result.final_confidence,
                    result.gate_reason,
                )
            except Exception:
                pass
            return result
        except Exception as exc:
            logger.warning("S20 adjudication failed: %s", exc)
            return None

    def _evaluate_safety(
        self,
        adj: Optional[ControlledAdjudicationResult],
        det_signals: Dict[str, Any],
        recorder: DecisionRecorder,
    ) -> Dict[str, Any]:
        safety: Dict[str, Any] = {
            "deterministic_veto": False,
            "veto_reason": None,
        }
        if adj is not None and adj.deterministic_veto_applied:
            safety["deterministic_veto"] = True
            safety["veto_reason"] = adj.trace.get(
                "final_reason", "deterministic_veto",
            )
            try:
                recorder.record_safety_veto(
                    safety["veto_reason"],
                    {"adjudication_decision": adj.final_decision.value},
                )
            except Exception:
                pass
        return safety

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_recorder(self, query: str) -> DecisionRecorder:
        if not self.config.provenance_enabled:
            return NullDecisionRecorder()
        try:
            return DecisionRecorder(query=query)
        except Exception:
            return NullDecisionRecorder()

    @staticmethod
    def _to_adjudication_candidates(
        chunks: List[Dict[str, Any]],
    ) -> List[AdjudicationCandidate]:
        out: List[AdjudicationCandidate] = []
        for i, c in enumerate(chunks):
            cid = str(c.get("chunk_id", c.get("id", f"chunk_{i}")))
            content = str(c.get("text", c.get("content", "")))
            score = float(c.get("relevance_score", c.get("score", 0.0)))
            meta = {
                k: v for k, v in c.items()
                if k not in ("text", "content", "chunk_id", "id")
            }
            out.append(AdjudicationCandidate(
                evidence_id=cid,
                content=content,
                metadata=meta,
                relevance_score=score,
            ))
        return out

    @staticmethod
    def _extract_signals(
        assembly: Optional[AssemblyResult],
        graph: Optional[EvidenceGraph],
    ) -> Dict[str, Any]:
        signals: Dict[str, Any] = {
            "has_conflict": False,
            "conflict_severity": 0.0,
            "conflict_type": "none",
            "is_sufficient": True,
            "confidence_gap": 1.0,
            "superseded_evidence_ids": [],
        }
        if assembly is not None:
            cr = assembly.conflict_report
            signals["has_conflict"] = getattr(cr, "detected", False)
            signals["conflict_severity"] = getattr(cr, "conflict_score", 0.0)
            if signals["has_conflict"]:
                signals["conflict_type"] = "contradiction"
            state = assembly.relational_state.state
            signals["is_sufficient"] = state in (
                EvidenceState.SUFFICIENT, EvidenceState.SUPPORTING,
            )
        if graph is not None:
            try:
                superseded: List[str] = []
                for rel_type in RelationshipType:
                    if "supersede" in rel_type.value.lower():
                        for edge in graph.get_relationships_by_type(rel_type):
                            tid = getattr(edge, "target_id", None)
                            if tid and tid not in superseded:
                                superseded.append(tid)
                signals["superseded_evidence_ids"] = superseded
            except Exception:
                pass
        return signals

    @staticmethod
    def _partition_evidence(
        assembly: Optional[AssemblyResult],
        adj: Optional[ControlledAdjudicationResult],
        safety: Dict[str, Any],
        original_candidates: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if assembly is None:
            return [], list(original_candidates)

        selected = list(assembly.selected_chunks)

        # If adjudication narrowed the set, filter
        if (
            adj is not None
            and adj.adjudication_was_triggered
            and adj.adjudication_result is not None
            and not safety.get("deterministic_veto")
        ):
            adj_ids = set(adj.adjudication_result.selected_evidence_ids)
            if adj_ids:
                selected = [
                    c for c in selected
                    if str(c.get("chunk_id", c.get("id", ""))) in adj_ids
                ]

        sel_ids = {
            str(c.get("chunk_id", c.get("id", ""))) for c in selected
        }
        all_chunks = list(original_candidates)
        rejected = [
            c for c in all_chunks
            if str(c.get("chunk_id", c.get("id", ""))) not in sel_ids
        ]
        return selected, rejected

    @staticmethod
    def _compute_decision(
        assembly: Optional[AssemblyResult],
        adj: Optional[ControlledAdjudicationResult],
        safety: Dict[str, Any],
    ) -> str:
        if safety.get("deterministic_veto"):
            return "UNCERTAIN"
        if adj is not None and adj.adjudication_was_triggered:
            if adj.final_decision == AdjudicationDecision.ACCEPT:
                return "SUFFICIENT"
            if adj.final_decision == AdjudicationDecision.REJECT:
                return "INSUFFICIENT"
        if assembly is not None:
            state = assembly.relational_state.state
            if state in (EvidenceState.SUFFICIENT, EvidenceState.SUPPORTING):
                return "SUFFICIENT"
            if state == EvidenceState.INSUFFICIENT:
                return "INSUFFICIENT"
        return "UNCERTAIN"

    @staticmethod
    def _compute_confidence(
        assembly: Optional[AssemblyResult],
        adj: Optional[ControlledAdjudicationResult],
        safety: Dict[str, Any],
    ) -> float:
        if safety.get("deterministic_veto"):
            return 0.0
        if adj is not None and adj.adjudication_was_triggered:
            return adj.final_confidence
        if assembly is not None:
            return min(1.0, max(0.0, assembly.relational_state.relevance_score))
        return 0.0

    @staticmethod
    def _conflict_summary(
        assembly: Optional[AssemblyResult],
    ) -> Dict[str, Any]:
        if assembly is None:
            return {"detected": False, "conflict_score": 0.0, "pair_count": 0}
        cr = assembly.conflict_report
        return {
            "detected": getattr(cr, "detected", False),
            "conflict_score": getattr(cr, "conflict_score", 0.0),
            "pair_count": len(getattr(cr, "pairs", [])),
        }

    @staticmethod
    def _sufficiency_summary(
        assembly: Optional[AssemblyResult],
    ) -> Dict[str, Any]:
        if assembly is None:
            return {"state": "unknown", "coverage": 0.0}
        return {
            "state": assembly.relational_state.state.value,
            "coverage": assembly.relational_state.coverage_ratio,
        }

    @staticmethod
    def _adjudication_summary(
        adj: Optional[ControlledAdjudicationResult],
    ) -> Dict[str, Any]:
        if adj is None:
            return {"triggered": False}
        return {
            "triggered": adj.adjudication_was_triggered,
            "gate_reason": adj.gate_reason,
            "decision": adj.final_decision.value,
            "confidence": adj.final_confidence,
            "veto_applied": adj.deterministic_veto_applied,
            "time_ms": round(adj.total_time_ms, 2),
        }
