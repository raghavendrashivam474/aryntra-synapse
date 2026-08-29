"""
Aryntra Synapse — Sprint 14
Conflict-Aware Evidence Resolution & Progressive Assembly Package.
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
from app.evidence.config import S14ResolutionConfig
from app.evidence.assembly import (
    EvidenceAssembler,
    AssemblyResult,
    AssemblyMetrics,
)

__all__ = [
    "EvidenceState",
    "RelationalEvidenceState",
    "ConflictType",
    "ConflictPair",
    "ConflictReport",
    "ContradictionDetector",
    "ConceptFacet",
    "CoverageReport",
    "CoverageAnalyzer",
    "S14ResolutionConfig",
    "EvidenceAssembler",
    "AssemblyResult",
    "AssemblyMetrics",
]
