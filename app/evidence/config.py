"""
Aryntra Synapse — Sprint 14
Configurable Resolution & Assembly Weights.
"""
from dataclasses import dataclass


@dataclass
class S14ResolutionConfig:
    """Configurable weights for S14 conflict-aware ranking and assembly."""
    relevance_weight: float = 0.45
    lexical_weight: float = 0.25
    coverage_weight: float = 0.20
    contradiction_penalty_weight: float = 0.25
    max_assembly_chunks: int = 5
    max_assembly_iterations: int = 4
    min_coverage_target: float = 0.75
    contradiction_threshold: float = 0.40

    @classmethod
    def baseline_s13(cls) -> "S14ResolutionConfig":
        """Exact S13 baseline behavior (no contradiction penalty, no coverage weighting)."""
        return cls(
            relevance_weight=0.60,
            lexical_weight=0.40,
            coverage_weight=0.0,
            contradiction_penalty_weight=0.0,
            max_assembly_chunks=1,
            max_assembly_iterations=1,
        )

    @classmethod
    def contradiction_only(cls) -> "S14ResolutionConfig":
        return cls(
            relevance_weight=0.50,
            lexical_weight=0.30,
            coverage_weight=0.0,
            contradiction_penalty_weight=0.35,
        )

    @classmethod
    def coverage_only(cls) -> "S14ResolutionConfig":
        return cls(
            relevance_weight=0.40,
            lexical_weight=0.25,
            coverage_weight=0.35,
            contradiction_penalty_weight=0.0,
        )

    @classmethod
    def assembly_only(cls) -> "S14ResolutionConfig":
        return cls(
            relevance_weight=0.55,
            lexical_weight=0.35,
            coverage_weight=0.10,
            contradiction_penalty_weight=0.0,
            max_assembly_chunks=5,
        )

    @classmethod
    def full_resolution(cls) -> "S14ResolutionConfig":
        return cls(
            relevance_weight=0.40,
            lexical_weight=0.20,
            coverage_weight=0.25,
            contradiction_penalty_weight=0.25,
            max_assembly_chunks=5,
            max_assembly_iterations=4,
        )
