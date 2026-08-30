"""
Aryntra Synapse — Sprint 14 + Sprint 15 + Sprint 16
Configurable Resolution, Assembly, Sufficiency, and Temporal Weights.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict


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
    temporal_weight: float = 0.0  # S16 extension, 0.0 preserves exact S15 scoring

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


# ── Sprint 16: Temporal Configuration ─────────────────────────────────

@dataclass
class S16TemporalConfig:
    """
    Sprint 16 - Temporal awareness thresholds and compatibility matrix.

    The compatibility matrix maps (query_intent, evidence_state) pairs
    to a 0.0-1.0 score. UNKNOWN states always return unknown_neutral_score.
    """
    temporal_weight: float = 0.25
    unknown_neutral_score: float = 0.50
    superseded_penalty: float = 0.10
    version_boost: float = 0.05

    # Stored as flat dict: "intent:state" -> score
    _compatibility: Optional[Dict[str, float]] = None

    def __post_init__(self):
        if self._compatibility is None:
            self._compatibility = self._default_matrix()

    def get_compatibility(self, intent: str, state: str) -> float:
        if self._compatibility is None:
            self._compatibility = self._default_matrix()
        return self._compatibility.get(
            f"{intent}:{state}", self.unknown_neutral_score
        )

    @staticmethod
    def _default_matrix() -> Dict[str, float]:
        return {
            # CURRENT queries
            "current:current": 1.0,
            "current:historical": 0.30,
            "current:future": 0.20,
            "current:time_bounded": 0.60,
            "current:superseded": 0.10,
            "current:unknown": 0.50,
            # HISTORICAL queries
            "historical:current": 0.30,
            "historical:historical": 1.0,
            "historical:future": 0.10,
            "historical:time_bounded": 0.70,
            "historical:superseded": 0.40,
            "historical:unknown": 0.50,
            # FUTURE queries
            "future:current": 0.20,
            "future:historical": 0.10,
            "future:future": 1.0,
            "future:time_bounded": 0.40,
            "future:superseded": 0.10,
            "future:unknown": 0.50,
            # TIME_RANGE queries
            "time_range:current": 0.50,
            "time_range:historical": 0.60,
            "time_range:future": 0.30,
            "time_range:time_bounded": 0.90,
            "time_range:superseded": 0.30,
            "time_range:unknown": 0.50,
            # POINT_IN_TIME queries
            "point_in_time:current": 0.30,
            "point_in_time:historical": 0.80,
            "point_in_time:future": 0.20,
            "point_in_time:time_bounded": 0.90,
            "point_in_time:superseded": 0.20,
            "point_in_time:unknown": 0.50,
            # UNKNOWN queries (all neutral)
            "unknown:current": 0.50,
            "unknown:historical": 0.50,
            "unknown:future": 0.50,
            "unknown:time_bounded": 0.50,
            "unknown:superseded": 0.50,
            "unknown:unknown": 0.50,
        }

    @classmethod
    def strict(cls) -> "S16TemporalConfig":
        """High temporal discrimination."""
        cfg = cls(temporal_weight=0.35, superseded_penalty=0.05)
        cfg._compatibility["current:historical"] = 0.15
        cfg._compatibility["current:superseded"] = 0.05
        return cfg

    @classmethod
    def relaxed(cls) -> "S16TemporalConfig":
        """Low temporal discrimination — near-neutral for most pairs."""
        cfg = cls(temporal_weight=0.10, unknown_neutral_score=0.55)
        for key in cfg._compatibility:
            if "unknown" not in key:
                cfg._compatibility[key] = max(
                    cfg._compatibility[key], 0.35
                )
        return cfg

    @classmethod
    def balanced(cls) -> "S16TemporalConfig":
        return cls()

# ── Sprint 17: Relationship Configuration ──────────────────────────────

@dataclass
class S17RelationshipConfig:
    """
    Sprint 17 — Evidence Relationship Graph configuration.

    Controls graph edge detection, bounds, and relationship-aware
    assembly re-ranking weights.
    """
    relationship_enabled: bool = True
    relationship_weight: float = 0.15
    max_relationship_edges: int = 50
    max_graph_nodes: int = 20

    # Feature flags for individual relationship detectors
    enable_supersession_edges: bool = True
    enable_contradiction_edges: bool = True
    enable_same_doc_edges: bool = True
    enable_version_chain_edges: bool = True
    enable_temporal_adjacency_edges: bool = True
    enable_elaboration_edges: bool = True
    enable_transitive_supersession: bool = True

    # Selection bias adjustments
    superseded_candidate_demotion: float = 0.20
    current_version_head_boost: float = 0.05

    @classmethod
    def balanced(cls) -> "S17RelationshipConfig":
        """Default balanced configuration."""
        return cls()

    @classmethod
    def strict(cls) -> "S17RelationshipConfig":
        """Strict relationship checking with heavier demotion of superseded nodes."""
        return cls(
            relationship_weight=0.25,
            superseded_candidate_demotion=0.35,
            current_version_head_boost=0.10,
        )

    @classmethod
    def conservative(cls) -> "S17RelationshipConfig":
        """Lightweight relationship checking, low weight."""
        return cls(
            relationship_weight=0.05,
            superseded_candidate_demotion=0.10,
            current_version_head_boost=0.02,
        )

    @classmethod
    def disabled(cls) -> "S17RelationshipConfig":
        """Backward-compatible disabled configuration."""
        return cls(relationship_enabled=False, relationship_weight=0.0)
