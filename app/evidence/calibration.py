from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

class DecisionState(Enum):
    ANSWER = "ANSWER"
    UNCERTAIN = "UNCERTAIN"
    REJECT = "REJECT"

@dataclass
class CalibratedDecision:
    decision: DecisionState
    confidence: float
    reason: str
    safety_status: str
    signals: Dict[str, Any]

class DecisionCalibrator:
    def __init__(self, answer_threshold: float = 0.7, uncertain_threshold: float = 0.4):
        self.answer_threshold = answer_threshold
        self.uncertain_threshold = uncertain_threshold

    def calibrate(self, 
                  semantic_relevance: float,
                  sufficiency_score: float,
                  has_conflict: bool,
                  conflict_score: float,
                  temporal_valid: bool = True,
                  deterministic_veto: bool = False,
                  veto_reason: Optional[str] = None) -> CalibratedDecision:
        
        if deterministic_veto or not temporal_valid:
            return CalibratedDecision(
                decision=DecisionState.UNCERTAIN,
                confidence=0.0,
                reason=veto_reason or "deterministic_safety_veto",
                safety_status="VETOED",
                signals={"conflict": conflict_score, "sufficiency": sufficiency_score}
            )

        base_confidence = (semantic_relevance * 0.6) + (sufficiency_score * 0.4)
        
        if has_conflict:
            penalty_factor = max(0.2, 1.0 - (conflict_score * 0.7))
            base_confidence *= penalty_factor
            
        if base_confidence >= self.answer_threshold:
            state = DecisionState.ANSWER
            reason = "strong_coherent_evidence"
        elif base_confidence >= self.uncertain_threshold:
            state = DecisionState.UNCERTAIN
            reason = "ambiguous_or_conflicting_evidence"
        else:
            state = DecisionState.REJECT
            reason = "insufficient_or_irrelevant_evidence"

        return CalibratedDecision(
            decision=state,
            confidence=round(base_confidence, 2),
            reason=reason,
            safety_status="SAFE",
            signals={"semantic": semantic_relevance, "sufficiency": sufficiency_score, "conflict": conflict_score}
        )