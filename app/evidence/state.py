"""
Aryntra Synapse — Sprint 14
Evidence State Model with Relational Attributes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    conflicting_with: list[str] = field(default_factory=list)
    covered_concepts: list[str] = field(default_factory=list)
    missing_concepts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
