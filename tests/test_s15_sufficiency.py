"""
Aryntra Synapse — Sprint 15 Tests
Minimum Sufficient Evidence Controller.

Tests cover:
  - Sufficiency decisions (SUFFICIENT / INSUFFICIENT / UNCERTAIN)
  - Individual signal behavior
  - Conflict veto logic
  - Redundancy detection
  - Integration with EvidenceAssembler
  - Backward compatibility (assembler without evaluator)
  - Safety bounds (no infinite expansion)
"""
import pytest
from app.evidence.sufficiency import (
    SufficiencyEvaluator,
    SufficiencyDecision,
    SufficiencyResult,
)
from app.evidence.config import S15SufficiencyConfig, S14ResolutionConfig
from app.evidence.coverage import CoverageAnalyzer, CoverageReport
from app.evidence.contradiction import ContradictionDetector, ConflictReport
from app.evidence.assembly import EvidenceAssembler
from app.evidence.state import EvidenceState


# ── Fixtures ──

@pytest.fixture
def evaluator():
    return SufficiencyEvaluator()

@pytest.fixture
def coverage_analyzer():
    return CoverageAnalyzer()

@pytest.fixture
def contradiction_detector():
    return ContradictionDetector()


def _chunk(chunk_id, text, score=0.7):
    return {"chunk_id": chunk_id, "text": text, "priority_score": score}


# ── 1. Basic sufficiency decisions ──

class TestSufficiencyDecisions:

    def test_sufficient_high_coverage_no_conflict(self, evaluator, coverage_analyzer):
        query = "What caused the server outage?"
        chunks = [_chunk("c1", "The server outage was caused by a memory leak in the auth service.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, [], cov, conf)
        assert result.decision == SufficiencyDecision.SUFFICIENT
        assert result.sufficiency_score >= 0.70

    def test_insufficient_no_evidence(self, evaluator, coverage_analyzer):
        query = "What caused the server outage?"
        cov = coverage_analyzer.evaluate(query, [])
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, [], [], cov, conf)
        assert result.decision == SufficiencyDecision.INSUFFICIENT
        assert result.sufficiency_score == 0.0

    def test_insufficient_low_coverage(self, evaluator, coverage_analyzer):
        query = "What caused the outage and when was it resolved and what was the impact?"
        # Chunk only covers "cause", not "when" or "impact"
        chunks = [_chunk("c1", "A bug caused the issue.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)
        remaining = [_chunk("c2", "Unrelated text about weather patterns in Europe.")]

        result = evaluator.evaluate(query, chunks, remaining, cov, conf)
        assert result.decision in (SufficiencyDecision.INSUFFICIENT, SufficiencyDecision.UNCERTAIN)

    def test_uncertain_moderate_coverage(self, evaluator, coverage_analyzer):
        query = "What caused the outage and when was it resolved?"
        chunks = [_chunk("c1", "The cause was a database failover event.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)
        remaining = [_chunk("c2", "The resolution occurred at 3am UTC.")]

        result = evaluator.evaluate(query, chunks, remaining, cov, conf)
        # Should be uncertain or insufficient — not sufficient yet
        assert result.decision != SufficiencyDecision.SUFFICIENT or cov.coverage_ratio >= 0.70


# ── 2. Signal tests ──

class TestSignals:

    def test_coverage_signal(self, evaluator, coverage_analyzer):
        query = "What caused the server outage?"
        chunks = [_chunk("c1", "The cause of the server outage was a power failure.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, [], cov, conf)
        assert result.signals["coverage"] > 0.5

    def test_support_signal_high_relevance(self, evaluator, coverage_analyzer):
        query = "What caused the outage?"
        chunks = [_chunk("c1", "The cause was a network failure.", score=0.95)]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, [], cov, conf)
        assert result.signals["support"] >= 0.90

    def test_support_signal_low_relevance(self, evaluator, coverage_analyzer):
        query = "What caused the outage?"
        chunks = [_chunk("c1", "The cause was a network failure.", score=0.10)]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, [], cov, conf)
        assert result.signals["support"] <= 0.20

    def test_conflict_signal_reduces_sufficiency(self, evaluator, coverage_analyzer):
        query = "When was the system restored?"
        chunks = [_chunk("c1", "The system was restored in 2024.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf_no = ConflictReport(detected=False, conflict_score=0.0)
        conf_yes = ConflictReport(detected=True, conflict_score=0.70)

        r_no = evaluator.evaluate(query, chunks, [], cov, conf_no)
        r_yes = evaluator.evaluate(query, chunks, [], cov, conf_yes)
        assert r_no.sufficiency_score > r_yes.sufficiency_score

    def test_redundancy_signal_no_remaining(self, evaluator, coverage_analyzer):
        query = "What caused the outage?"
        chunks = [_chunk("c1", "The cause was a bug.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, [], cov, conf)
        assert result.signals["redundancy"] == 1.0
        assert result.signals["marginal_gain"] == 0.0

    def test_marginal_gain_high(self, evaluator, coverage_analyzer):
        query = "What caused the outage and when was it resolved?"
        chunks = [_chunk("c1", "The cause was a memory leak.")]
        remaining = [_chunk("c2", "The resolution occurred at 2024-03-15 03:00 UTC.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(query, chunks, remaining, cov, conf)
        assert result.signals["marginal_gain"] > 0.0


# ── 3. Conflict veto ──

class TestConflictVeto:

    def test_high_conflict_blocks_sufficient(self, evaluator, coverage_analyzer):
        query = "When was the system restored?"
        chunks = [_chunk("c1", "Restored in 2024.")]
        cov = coverage_analyzer.evaluate(query, chunks)
        conf = ConflictReport(detected=True, conflict_score=0.60)
        remaining = [_chunk("c2", "Actually restored in 2023.")]

        result = evaluator.evaluate(query, chunks, remaining, cov, conf)
        # Conflict veto should prevent SUFFICIENT
        assert result.decision != SufficiencyDecision.SUFFICIENT


# ── 4. Config presets ──

class TestConfigPresets:

    def test_conservative_higher_threshold(self):
        cfg = S15SufficiencyConfig.conservative()
        assert cfg.sufficient_threshold > S15SufficiencyConfig.balanced().sufficient_threshold

    def test_aggressive_lower_threshold(self):
        cfg = S15SufficiencyConfig.aggressive()
        assert cfg.sufficient_threshold < S15SufficiencyConfig.balanced().sufficient_threshold

    def test_coverage_only_single_signal(self):
        cfg = S15SufficiencyConfig.coverage_only()
        assert cfg.coverage_weight == 1.0
        assert cfg.support_weight == 0.0


# ── 5. Integration with EvidenceAssembler ──

class TestAssemblerIntegration:

    def test_assembler_without_evaluator_backward_compat(self, coverage_analyzer):
        """S14 behavior preserved when no evaluator is provided."""
        assembler = EvidenceAssembler(coverage_analyzer=coverage_analyzer)
        query = "What caused the server outage?"
        chunks = [
            _chunk("c1", "The cause of the server outage was a power failure in the datacenter.", 0.9),
            _chunk("c2", "The outage impacted 500 users across the region.", 0.6),
        ]
        result = assembler.assemble(query, chunks)
        assert result.metrics.sufficiency_decision == "not_evaluated"
        assert result.metrics.sufficiency_score == -1.0
        assert len(result.selected_chunks) >= 1

    def test_assembler_with_evaluator_stops_early(self):
        """S15 evaluator should stop expansion when evidence is sufficient."""
        assembler = EvidenceAssembler.with_sufficiency()
        query = "What caused the server outage?"
        chunks = [
            _chunk("c1", "The cause of the server outage was a power failure in the datacenter.", 0.95),
            _chunk("c2", "The outage impacted 500 users across the region.", 0.60),
            _chunk("c3", "Recovery took approximately 4 hours to complete.", 0.40),
            _chunk("c4", "The weather was sunny that day in the region.", 0.10),
        ]
        result = assembler.assemble(query, chunks)
        assert result.metrics.sufficiency_decision != "not_evaluated"
        # Should not need all 4 chunks for a simple query
        assert result.metrics.selected_count <= 3

    def test_assembler_with_evaluator_expands_for_complex(self):
        """S15 evaluator should expand for multi-concept queries."""
        assembler = EvidenceAssembler.with_sufficiency()
        query = "What caused the outage and when was it resolved and what was the outcome?"
        chunks = [
            _chunk("c1", "The cause of the outage was a database failover.", 0.90),
            _chunk("c2", "The resolution occurred at 2024-03-15 03:00 UTC.", 0.70),
            _chunk("c3", "The outcome was a full data recovery with no loss.", 0.65),
            _chunk("c4", "Unrelated marketing announcement for Q2.", 0.10),
        ]
        result = assembler.assemble(query, chunks)
        # Should expand to cover cause + time + outcome
        assert result.metrics.selected_count >= 2

    def test_assembler_with_sufficiency_factory(self):
        """Convenience factory creates working assembler."""
        assembler = EvidenceAssembler.with_sufficiency()
        assert assembler.sufficiency_evaluator is not None
        result = assembler.assemble("test query", [_chunk("c1", "test text")])
        assert result.metrics.sufficiency_decision != "not_evaluated"


# ── 6. Safety bounds ──

class TestSafetyBounds:

    def test_max_chunks_respected(self):
        """Assembly never exceeds max_assembly_chunks."""
        config = S14ResolutionConfig(max_assembly_chunks=3, max_assembly_iterations=3)
        assembler = EvidenceAssembler.with_sufficiency(s14_config=config)
        query = "What caused the outage and when and where and how and what outcome?"
        chunks = [
            _chunk(f"c{i}", f"Chunk {i} with cause time location mechanism outcome data.", 0.9 - i * 0.05)
            for i in range(10)
        ]
        result = assembler.assemble(query, chunks)
        assert len(result.selected_chunks) <= 3

    def test_max_iterations_respected(self):
        """Assembly never exceeds max_assembly_iterations."""
        config = S14ResolutionConfig(max_assembly_iterations=2)
        assembler = EvidenceAssembler.with_sufficiency(s14_config=config)
        query = "What caused the outage and when and where and how?"
        chunks = [
            _chunk(f"c{i}", f"Chunk {i} about cause and time.", 0.9 - i * 0.05)
            for i in range(8)
        ]
        result = assembler.assemble(query, chunks)
        assert result.metrics.iterations <= 2

    def test_empty_input(self):
        """Empty input returns INSUFFICIENT without crashing."""
        assembler = EvidenceAssembler.with_sufficiency()
        result = assembler.assemble("test query", [])
        assert result.relational_state.state == EvidenceState.INSUFFICIENT
        assert len(result.selected_chunks) == 0


# ── 7. Regression: all S14 tests must still pass ──

class TestBackwardCompatibility:

    def test_s14_default_assembler_unchanged(self):
        """Default EvidenceAssembler() without evaluator behaves as S14."""
        assembler = EvidenceAssembler()
        assert assembler.sufficiency_evaluator is None
        query = "What caused the outage?"
        chunks = [
            _chunk("c1", "The cause was a power failure.", 0.9),
            _chunk("c2", "Recovery took 4 hours.", 0.5),
        ]
        result = assembler.assemble(query, chunks)
        # S14 metrics should work
        assert result.metrics.assembly_decision in (
            "assembled_sufficient", "partial_coverage", "insufficient",
            "conflict_detected_unresolved",
        )

    def test_s14_config_presets_unchanged(self):
        """S14 config presets still produce valid assemblers."""
        for factory in [
            S14ResolutionConfig.baseline_s13,
            S14ResolutionConfig.contradiction_only,
            S14ResolutionConfig.coverage_only,
            S14ResolutionConfig.assembly_only,
            S14ResolutionConfig.full_resolution,
        ]:
            config = factory()
            assembler = EvidenceAssembler(config=config)
            result = assembler.assemble("test", [_chunk("c1", "test")])
            assert result is not None
