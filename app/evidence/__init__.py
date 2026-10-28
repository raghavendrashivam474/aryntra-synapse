"""
Aryntra Synapse — Sprint 14 + Sprint 15
Conflict-Aware Evidence Resolution, Progressive Assembly,
and Minimum Sufficient Evidence Control Package.
"""

from app.evidence.assembly import (
    AssemblyMetrics,
    AssemblyResult,
    EvidenceAssembler,
)
from app.evidence.config import (
    S14ResolutionConfig,
    S15SufficiencyConfig,
    S16TemporalConfig,
)
from app.evidence.contradiction import (
    ConflictPair,
    ConflictReport,
    ConflictType,
    ContradictionDetector,
)
from app.evidence.coverage import (
    ConceptFacet,
    CoverageAnalyzer,
    CoverageReport,
)
from app.evidence.state import EvidenceState, RelationalEvidenceState
from app.evidence.sufficiency import (
    SufficiencyDecision,
    SufficiencyEvaluator,
    SufficiencyResult,
)
from app.evidence.temporal import (
    QueryTemporalIntent,
    TemporalAnalyzer,
    TemporalCompatibilityResult,
    TemporalMetadata,
    TemporalState,
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
    # S16 temporal
    "TemporalState",
    "QueryTemporalIntent",
    "TemporalMetadata",
    "TemporalCompatibilityResult",
    "TemporalAnalyzer",
    "S16TemporalConfig",
]
