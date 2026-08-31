import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.evidence.state import EvidenceState
from app.evidence.temporal import TemporalAnalyzer, QueryTemporalIntent
from app.evidence.relationships import EvidenceGraph, RelationshipAnalyzer
from app.evidence.assembly import EvidenceAssembler
from app.evidence.contradiction import ContradictionDetector
from app.evidence.sufficiency import SufficiencyEvaluator
from app.evidence.coverage import CoverageAnalyzer
from app.evidence.adjudication import AdjudicationController, AdjudicationDecision, MockAdjudicator
from app.evidence.provenance import DecisionRecorder, DecisionRecord, FinalStatus
from app.evidence.calibration import DecisionCalibrator, DecisionState

@dataclass
class UnifiedEvidenceConfig:
    enable_adjudication: bool = True
    adjudication_threshold: float = 0.7

@dataclass
class UnifiedProcessResult:
    query: str
    decision: str
    confidence: float
    pipeline_time_ms: float
    selected_evidence: List[Dict[str, Any]]
    rejected_evidence: List[Dict[str, Any]]
    signals: Dict[str, Any]
    temporal_context: Dict[str, Any]
    relationships: Dict[str, Any]
    record: Optional[DecisionRecord] = None

class UnifiedEvidenceEngine:
    def __init__(self, config: UnifiedEvidenceConfig = UnifiedEvidenceConfig()):
        self.config = config
        self.temporal = TemporalAnalyzer()
        self.rel_analyzer = RelationshipAnalyzer()
        self.assembler = EvidenceAssembler()
        self.conflicts = ContradictionDetector()
        self.coverage = CoverageAnalyzer()
        self.sufficiency = SufficiencyEvaluator()
        self.adjudicator = AdjudicationController(adjudicator=MockAdjudicator())
        self.calibrator = DecisionCalibrator()

    def _get_val(self, obj, key, default=0.0):
        if obj is None: return default
        if isinstance(obj, dict): return obj.get(key, default)
        return getattr(obj, key, default)

    def process(self, query: str, candidates: List[Any], context: Dict[str, Any] = None) -> UnifiedProcessResult:
        start_time = time.time()
        recorder = DecisionRecorder(query=query)
        
        intent = self.temporal.extract_query_intent(query)
        target_date = self.temporal.extract_query_target_date(query)
        t_ctx = {"query_intent": intent.value if hasattr(intent, 'value') else str(intent), "target_date": target_date}
        
        cand_dicts = [c.to_dict() if hasattr(c, 'to_dict') else c for c in candidates]
        graph = self.rel_analyzer.build_graph(cand_dicts)
        assembly = self.assembler.assemble(query, candidates)
        
        selected_chunks = getattr(assembly, 'selected_chunks', [])
        selected_ids = [str(self._get_val(c, 'id')) for c in selected_chunks]
        selected_dicts = [c.to_dict() if hasattr(c, 'to_dict') else c for c in selected_chunks]
        remaining_dicts = [c.to_dict() if hasattr(c, 'to_dict') else c for c in candidates if str(self._get_val(c, 'id')) not in selected_ids]
        
        conflict_report = self.conflicts.analyze(selected_dicts)
        coverage_report = self.coverage.evaluate(query, selected_dicts)
        suff_result = self.sufficiency.evaluate(query, selected_dicts, remaining_dicts, coverage_report, conflict_report)
        
        c_dict = conflict_report.to_dict() if hasattr(conflict_report, 'to_dict') else {'has_conflict': False, 'conflict_score': 0.0}
        adj_result = self.adjudicator.process(query, selected_chunks, c_dict)
        
        veto = self._get_val(adj_result, 'deterministic_veto_triggered', False)
        score = max([self._get_val(c, 'score', 0.8) for c in selected_chunks]) if selected_chunks else 0.0
        
        calibration = self.calibrator.calibrate(
            semantic_relevance=score, 
            sufficiency_score=self._get_val(suff_result, 'score', 0.0),
            has_conflict=self._get_val(conflict_report, 'has_conflict', False),
            conflict_score=self._get_val(conflict_report, 'conflict_score', 0.0),
            deterministic_veto=veto
        )
        
        latency = (time.time() - start_time) * 1000
        status_map = {"ANSWER": FinalStatus.SUFFICIENT, "REJECT": FinalStatus.INSUFFICIENT, "UNCERTAIN": FinalStatus.UNCERTAIN}
        
        return UnifiedProcessResult(
            query=query, decision=calibration.decision.value, confidence=calibration.confidence,
            pipeline_time_ms=latency, 
            selected_evidence=[{"chunk_id": i} for i in selected_ids],
            rejected_evidence=[{"chunk_id": str(self._get_val(c, 'id'))} for c in candidates if str(self._get_val(c, 'id')) not in selected_ids],
            temporal_context=t_ctx,
            relationships={"node_count": graph.node_count, "edge_count": graph.edge_count},
            signals={
                "conflict_detected": self._get_val(conflict_report, 'has_conflict', False),
                "conflict_score": self._get_val(conflict_report, 'conflict_score', 0.0),
                "adjudication_triggered": self._get_val(adj_result, 'adjudication_was_triggered', False),
                "adjudication_decision": self._get_val(adj_result, 'final_decision', AdjudicationDecision.UNCERTAIN).value if adj_result else "NONE",
                "safety_veto": veto,
                "sufficiency_score": self._get_val(suff_result, 'score', 0.0)
            },
            record=recorder.finalize(status=status_map.get(calibration.decision.value, FinalStatus.UNCERTAIN), reason=f"calibrated_{calibration.reason}")
        )