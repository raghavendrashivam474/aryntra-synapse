"""
Aryntra Synapse — Sprint 12: Priority Calibration & Evidence Survival Telemetry

Responsibilities:
- Configurable priority weight profiles for systematic experimentation
- Programmatic calibration matrix generation
- Evidence survival tracking through all pipeline stages
- Answer-bearing evidence integrity measurement
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)


# =====================================================================
# Component 1: Configurable Priority Calibration
# =====================================================================

@dataclass
class PriorityCalibrationConfig:
    """
    S12 configurable priority weights and thresholds.
    Wraps the existing EvidencePriorityWeights with experiment metadata
    and provides clean conversion to the S8/S9 weight format.
    """
    semantic_weight: float = 0.50
    lexical_weight: float = 0.30
    reuse_weight: float = 0.20
    high_threshold: float = 0.60
    medium_threshold: float = 0.30
    label: str = "default"

    def validate(self) -> bool:
        """Ensure weights are non-negative and sum to approximately 1.0."""
        if any(w < 0 for w in (self.semantic_weight, self.lexical_weight, self.reuse_weight)):
            return False
        total = self.semantic_weight + self.lexical_weight + self.reuse_weight
        return abs(total - 1.0) < 0.05 or total == 0.0

    def to_weights(self):
        """Convert to existing S8/S9 EvidencePriorityWeights."""
        from app.context.evidence_priority import EvidencePriorityWeights
        return EvidencePriorityWeights(
            semantic_weight=self.semantic_weight,
            lexical_weight=self.lexical_weight,
            reuse_weight=self.reuse_weight,
            high_threshold=self.high_threshold,
            medium_threshold=self.medium_threshold,
        )

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "semantic_weight": self.semantic_weight,
            "lexical_weight": self.lexical_weight,
            "reuse_weight": self.reuse_weight,
            "high_threshold": self.high_threshold,
            "medium_threshold": self.medium_threshold,
            "valid": self.validate(),
        }


# =====================================================================
# Component 2: Calibration Matrix Generator
# =====================================================================

class CalibrationMatrixGenerator:
    """
    Programmatically generates weight combinations for S12 experiments.
    Produces single-factor, pairwise, and full-blend configurations
    without manual enumeration.
    """

    @staticmethod
    def single_factor() -> List[PriorityCalibrationConfig]:
        """One signal active, others zero."""
        return [
            PriorityCalibrationConfig(1.0, 0.0, 0.0, label="semantic_only"),
            PriorityCalibrationConfig(0.0, 1.0, 0.0, label="lexical_only"),
            PriorityCalibrationConfig(0.0, 0.0, 1.0, label="reuse_only"),
        ]

    @staticmethod
    def pairwise(steps: int = 5) -> List[PriorityCalibrationConfig]:
        """Two-signal blends at regular intervals."""
        configs = []
        pairs = [
            ("semantic", "lexical", "reuse"),
            ("semantic", "reuse", "lexical"),
            ("lexical", "reuse", "semantic"),
        ]
        for active_a, active_b, zero_name in pairs:
            for i in range(1, steps):
                w_a = round(i / steps, 2)
                w_b = round(1.0 - w_a, 2)
                weights = {active_a: w_a, active_b: w_b, zero_name: 0.0}
                label = f"{active_a}_{w_a}_{active_b}_{w_b}"
                configs.append(PriorityCalibrationConfig(
                    semantic_weight=weights["semantic"],
                    lexical_weight=weights["lexical"],
                    reuse_weight=weights["reuse"],
                    label=label,
                ))
        return configs

    @staticmethod
    def full_blend(steps: int = 5) -> List[PriorityCalibrationConfig]:
        """Three-signal blends summing to 1.0."""
        configs = []
        for i in range(1, steps):
            for j in range(1, steps - i):
                k = steps - i - j
                if k < 1:
                    continue
                sw = round(i / steps, 2)
                lw = round(j / steps, 2)
                rw = round(k / steps, 2)
                label = f"blend_s{sw}_l{lw}_r{rw}"
                configs.append(PriorityCalibrationConfig(
                    semantic_weight=sw,
                    lexical_weight=lw,
                    reuse_weight=rw,
                    label=label,
                ))
        return configs

    @classmethod
    def full_matrix(cls) -> List[PriorityCalibrationConfig]:
        """Complete calibration matrix: single + pairwise + full."""
        matrix = cls.single_factor() + cls.pairwise() + cls.full_blend()
        logger.info("CalibrationMatrixGenerator: %d configurations", len(matrix))
        return matrix


# =====================================================================
# Component 4: Evidence Survival Telemetry
# =====================================================================

@dataclass
class EvidenceSurvivalRecord:
    """Tracks a single chunk's journey through the pipeline."""
    query_id: str
    chunk_id: str
    is_answer_bearing: bool
    retrieved: bool = False
    survived_prefilter: bool = False
    priority_rank: Optional[int] = None
    priority_tier: Optional[str] = None
    priority_score: float = 0.0
    promoted: bool = False
    final_context: bool = False

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "chunk_id": self.chunk_id,
            "is_answer_bearing": self.is_answer_bearing,
            "retrieved": self.retrieved,
            "survived_prefilter": self.survived_prefilter,
            "priority_rank": self.priority_rank,
            "priority_tier": self.priority_tier,
            "priority_score": round(self.priority_score, 4),
            "promoted": self.promoted,
            "final_context": self.final_context,
        }


class EvidenceSurvivalTracker:
    """
    S12 Evidence Survival Telemetry.

    Tracks answer-bearing evidence through:
      retrieved -> survived_prefilter -> priority_ranked -> promoted -> final_context

    This allows distinguishing retrieval failure from priority failure
    from sufficiency failure from LLM generation failure.
    """

    def __init__(self):
        self._records: List[EvidenceSurvivalRecord] = []

    def mark_retrieved(
        self,
        query_id: str,
        chunks: List[Dict[str, Any]],
        answer_bearing_ids: Set[str],
    ) -> None:
        """Record which chunks were retrieved and which bear the answer."""
        for c in chunks:
            cid = c.get("chunk_id", str(id(c)))
            self._records.append(EvidenceSurvivalRecord(
                query_id=query_id,
                chunk_id=cid,
                is_answer_bearing=(cid in answer_bearing_ids),
                retrieved=True,
            ))

    def mark_prefilter(self, query_id: str, surviving_ids: Set[str]) -> None:
        """Record which chunks survived pre-filtering."""
        for r in self._records:
            if r.query_id == query_id and r.retrieved:
                r.survived_prefilter = (r.chunk_id in surviving_ids)

    def mark_priority(self, query_id: str, ranked_chunks: List[Dict[str, Any]]) -> None:
        """Record priority ranking results."""
        for rank, c in enumerate(ranked_chunks):
            cid = c.get("chunk_id", "")
            for r in self._records:
                if r.query_id == query_id and r.chunk_id == cid:
                    r.priority_rank = rank
                    r.priority_tier = c.get("priority_class", "")
                    r.priority_score = c.get("priority_score", 0.0)
                    r.promoted = (c.get("state") == "active")

    def mark_final_context(self, query_id: str, final_ids: Set[str]) -> None:
        """Record which chunks made it into the final LLM context."""
        for r in self._records:
            if r.query_id == query_id:
                r.final_context = (r.chunk_id in final_ids)

    def get_answer_bearing_stats(self, query_id: str) -> Dict[str, int]:
        """Aggregate survival stats for answer-bearing chunks of a query."""
        ab = [
            r for r in self._records
            if r.query_id == query_id and r.is_answer_bearing
        ]
        if not ab:
            return {
                "retrieved": 0, "survived": 0,
                "promoted": 0, "final": 0, "total": 0,
            }
        return {
            "retrieved": sum(1 for r in ab if r.retrieved),
            "survived": sum(1 for r in ab if r.survived_prefilter),
            "promoted": sum(1 for r in ab if r.promoted),
            "final": sum(1 for r in ab if r.final_context),
            "total": len(ab),
        }

    def get_survival_rates(self, query_id: str) -> Dict[str, float]:
        """Compute survival rates as fractions."""
        stats = self.get_answer_bearing_stats(query_id)
        total = stats["total"]
        if total == 0:
            return {"retrieval_rate": 0.0, "survival_rate": 0.0,
                    "promotion_rate": 0.0, "final_rate": 0.0}
        return {
            "retrieval_rate": round(stats["retrieved"] / total, 4),
            "survival_rate": round(stats["survived"] / total, 4),
            "promotion_rate": round(stats["promoted"] / total, 4),
            "final_rate": round(stats["final"] / total, 4),
        }

    def to_list(self) -> List[dict]:
        return [r.to_dict() for r in self._records]

    def reset(self) -> None:
        self._records.clear()

    @property
    def record_count(self) -> int:
        return len(self._records)
