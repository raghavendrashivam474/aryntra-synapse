"""
Aryntra Synapse — Sprint 14 + Sprint 15
Configurable Resolution, Assembly, and Sufficiency Weights.
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


@dataclass
class S15SufficiencyConfig:
    """
    Sprint 15 — Minimum Sufficient Evidence thresholds and signal weights.

    All weights should sum to ~1.0 for interpretable scoring.
    Thresholds define the decision boundary:
      score >= sufficient_threshold  → SUFFICIENT (STOP)
      score < insufficient_threshold → INSUFFICIENT (EXPAND)
      between                        → UNCERTAIN (conservative EXPAND)
    """
    # Signal weights (sum ≈ 1.0)
    coverage_weight: float = 0.30
    support_weight: float = 0.15
    unresolved_weight: float = 0.20
    conflict_weight: float = 0.15
    redundancy_weight: float = 0.10
    marginal_gain_weight: float = 0.10

    # Decision thresholds
    sufficient_threshold: float = 0.70
    insufficient_threshold: float = 0.40

    # Marginal gain computation
    marginal_gain_floor: float = 0.02   # gains below this are treated as zero
    marginal_probe_count: int = 5        # how many remaining candidates to probe

    # Conflict veto: high conflict + low coverage → never declare sufficient
    conflict_veto_threshold: float = 0.40
    conflict_veto_coverage_floor: float = 0.80

    @classmethod
    def conservative(cls) -> "S15SufficiencyConfig":
        """High bar for stopping — minimizes premature-stop risk."""
        return cls(
            sufficient_threshold=0.80,
            insufficient_threshold=0.35,
            coverage_weight=0.35,
            unresolved_weight=0.25,
        )

    @classmethod
    def aggressive(cls) -> "S15SufficiencyConfig":
        """Low bar for stopping — minimizes over-expansion."""
        return cls(
            sufficient_threshold=0.60,
            insufficient_threshold=0.45,
            redundancy_weight=0.20,
            marginal_gain_weight=0.15,
        )

    @classmethod
    def balanced(cls) -> "S15SufficiencyConfig":
        """Default balanced configuration."""
        return cls()

    @classmethod
    def coverage_only(cls) -> "S15SufficiencyConfig":
        """Ablation: coverage signal only."""
        return cls(
            coverage_weight=1.0,
            support_weight=0.0,
            unresolved_weight=0.0,
            conflict_weight=0.0,
            redundancy_weight=0.0,
            marginal_gain_weight=0.0,
        )

    @classmethod
    def no_conflict(cls) -> "S15SufficiencyConfig":
        """Ablation: all signals except conflict."""
        return cls(conflict_weight=0.0, coverage_weight=0.35, unresolved_weight=0.25)
