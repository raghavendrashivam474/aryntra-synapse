"""
Aryntra Synapse — Sprint 14 + Sprint 15
Conflict-Aware Evidence Resolution, Progressive Assembly,
and Minimum Sufficient Evidence Control Package.
"""
from app.evidence.state import EvidenceState, RelationalEvidenceState
from app.evidence.contradiction import (
    ConflictType,
    ConflictPair,
    ConflictReport,
    ContradictionDetector,
)
from app.evidence.coverage import (
    ConceptFacet,
    CoverageReport,
    CoverageAnalyzer,
)
from app.evidence.config import S14ResolutionConfig, S15SufficiencyConfig
from app.evidence.assembly import (
    EvidenceAssembler,
    AssemblyResult,
    AssemblyMetrics,
)
from app.evidence.sufficiency import (
    SufficiencyDecision,
    SufficiencyResult,
    SufficiencyEvaluator,
)

__all__ = [
    # S14 state
    "EvidenceState",
    "RelationalEvidenceState",
    # S14 contradiction
    "ConflictType",
    "ConflictPair",
    "ConflictReport",
    "ContradictionDetector",
    # S14 coverage
    "ConceptFacet",
    "CoverageReport",
    "CoverageAnalyzer",
    # S14 + S15 config
    "S14ResolutionConfig",
    "S15SufficiencyConfig",
    # S14 assembly (S15-integrated)
    "EvidenceAssembler",
    "AssemblyResult",
    "AssemblyMetrics",
    # S15 sufficiency
    "SufficiencyDecision",
    "SufficiencyResult",
    "SufficiencyEvaluator",
]
