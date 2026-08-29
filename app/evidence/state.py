"""
Aryntra Synapse — Sprint 14
Evidence State Model with Relational Attributes.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class EvidenceState(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    SUFFICIENT = "sufficient"
    UNRESOLVED = "unresolved"


@dataclass
class RelationalEvidenceState:
    """Relational state of an evidence chunk or evidence set."""
    state: EvidenceState
    relevance_score: float = 0.0
    coverage_ratio: float = 0.0
    conflict_score: float = 0.0
    conflicting_with: List[str] = field(default_factory=list)
    covered_concepts: List[str] = field(default_factory=list)
    missing_concepts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "relevance_score": round(self.relevance_score, 4),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "conflict_score": round(self.conflict_score, 4),
            "conflicting_with": self.conflicting_with,
            "covered_concepts": self.covered_concepts,
            "missing_concepts": self.missing_concepts,
            "metadata": self.metadata,
        }
