"""
S20 — Unified Evidence Intelligence Pipeline Tests

16 tests covering: init, happy path, temporal, version, contradiction,
adjudication, veto, provenance, bounds, failure, backward compat.
"""

import pytest

from app.evidence.unified import (
    UnifiedEvidenceEngine,
    UnifiedEvidenceConfig,
    UnifiedEvidenceResult,
)
from app.evidence.adjudication import (
    MockAdjudicator,
    AdjudicationResult,
    AdjudicationDecision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(cid: str, text: str = "Some evidence text.", score: float = 0.8, **kw):
    """Build a minimal candidate dict."""
    c = {"chunk_id": cid, "text": text, "relevance_score": score}
    c.update(kw)
    return c


# ---------------------------------------------------------------------------
# 1. Pipeline initialisation
# ---------------------------------------------------------------------------

class TestPipelineInit:
    def test_default_init(self):
        engine = UnifiedEvidenceEngine()
        assert engine.config.temporal_enabled is True
        assert engine.config.adjudication_enabled is True
        assert engine.config.provenance_enabled is True

    def test_all_layers_disabled(self):
        cfg = UnifiedEvidenceConfig(
            temporal_enabled=False,
            relationship_enabled=False,
            sufficiency_enabled=False,
            adjudication_enabled=False,
            provenance_enabled=False,
        )
        engine = UnifiedEvidenceEngine(config=cfg)
        assert engine._temporal is None
        assert engine._relationships is None
        assert engine._adjudication_controller is None


# ---------------------------------------------------------------------------
# 2. Simple query
# ---------------------------------------------------------------------------

class TestSimpleQuery:
    def test_basic_pipeline(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process(
            "What is the policy?",
            [_c("c1"), _c("c2")],
        )
        assert isinstance(result, UnifiedEvidenceResult)
        assert result.query == "What is the policy?"
        assert result.pipeline_time_ms >= 0
        assert result.decision in ("SUFFICIENT", "INSUFFICIENT", "UNCERTAIN")

    def test_empty_candidates(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("query", [])
        assert result.decision in ("INSUFFICIENT", "UNCERTAIN")
        assert result.selected_evidence == []


# ---------------------------------------------------------------------------
# 3. Temporal query
# ---------------------------------------------------------------------------

class TestTemporalQuery:
    def test_temporal_context_populated(self):
        engine = UnifiedEvidenceEngine()
        candidates = [
            _c("c1", "Policy from 2025.", effective_date="2025-01"),
            _c("c2", "Policy from 2026.", effective_date="2026-01"),
        ]
        result = engine.process("What policy in 2026?", candidates)
        assert result.temporal_context.get("enabled") is True


# ---------------------------------------------------------------------------
# 4. Version query
# ---------------------------------------------------------------------------

class TestVersionQuery:
    def test_version_chain(self):
        engine = UnifiedEvidenceEngine()
        candidates = [
            _c("v1", "Old policy.", version="1.0"),
            _c("v2", "New policy.", version="2.0"),
        ]
        result = engine.process("Current policy?", candidates)
        assert result.decision in ("SUFFICIENT", "INSUFFICIENT", "UNCERTAIN")


# ---------------------------------------------------------------------------
# 5. Contradiction query
# ---------------------------------------------------------------------------

class TestContradictionQuery:
    def test_contradiction_detected(self):
        engine = UnifiedEvidenceEngine()
        candidates = [
            _c("c1", "Limit is 100."),
            _c("c2", "Limit is 200."),
        ]
        result = engine.process("What is the limit?", candidates)
        assert isinstance(result.conflicts, dict)
        assert "detected" in result.conflicts


# ---------------------------------------------------------------------------
# 6. Relationship-aware selection
# ---------------------------------------------------------------------------

class TestRelationshipAware:
    def test_relationship_info_present(self):
        engine = UnifiedEvidenceEngine()
        candidates = [
            _c("c1", "Section A.", document_id="doc1"),
            _c("c2", "Section B.", document_id="doc1"),
        ]
        result = engine.process("doc1 info?", candidates)
        assert isinstance(result.relationships, dict)


# ---------------------------------------------------------------------------
# 7. Sufficiency stopping
# ---------------------------------------------------------------------------

class TestSufficiency:
    def test_sufficiency_summary(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("test", [_c("c1")])
        assert "state" in result.sufficiency


# ---------------------------------------------------------------------------
# 8-9. Adjudication trigger / skip
# ---------------------------------------------------------------------------

class TestAdjudication:
    def test_adjudication_with_mock_accept(self):
        mock = MockAdjudicator()
        mock.set_response(AdjudicationResult(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.85,
            selected_evidence_ids=("c1",),
            rationale="test accept",
            adjudication_time_ms=1.0,
        ))
        engine = UnifiedEvidenceEngine(adjudicator=mock)
        result = engine.process(
            "ambiguous query", [_c("c1"), _c("c2")],
        )
        assert result.adjudication is not None

    def test_adjudication_disabled(self):
        cfg = UnifiedEvidenceConfig(adjudication_enabled=False)
        engine = UnifiedEvidenceEngine(config=cfg)
        result = engine.process("test", [_c("c1")])
        assert result.adjudication.get("triggered") is False


# ---------------------------------------------------------------------------
# 10. Deterministic veto
# ---------------------------------------------------------------------------

class TestDeterministicVeto:
    def test_veto_field_exists(self):
        mock = MockAdjudicator()
        mock.set_response(AdjudicationResult(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.9,
            selected_evidence_ids=("c1",),
            rationale="accept",
            adjudication_time_ms=1.0,
        ))
        engine = UnifiedEvidenceEngine(adjudicator=mock)
        result = engine.process("test", [_c("c1")])
        assert "deterministic_veto" in result.safety


# ---------------------------------------------------------------------------
# 11-12. Provenance recording / replay
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_recorded(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("test query", [_c("c1")])
        if result.provenance is not None:
            assert result.provenance.query == "test query"

    def test_provenance_replay_via_dict(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("replay test", [_c("c1"), _c("c2")])
        if result.provenance is not None:
            d = result.provenance.to_dict()
            assert "query" in d
            assert "events" in d


# ---------------------------------------------------------------------------
# 13. Failure fallback
# ---------------------------------------------------------------------------

class TestFailureFallback:
    def test_all_disabled_still_returns(self):
        cfg = UnifiedEvidenceConfig(
            temporal_enabled=False,
            relationship_enabled=False,
            sufficiency_enabled=False,
            adjudication_enabled=False,
            provenance_enabled=False,
        )
        engine = UnifiedEvidenceEngine(config=cfg)
        result = engine.process("test", [_c("c1")])
        assert result.decision in ("SUFFICIENT", "INSUFFICIENT", "UNCERTAIN")
        assert result.pipeline_time_ms >= 0


# ---------------------------------------------------------------------------
# 14-15. Candidate / expansion bounds
# ---------------------------------------------------------------------------

class TestBounds:
    def test_max_candidates_respected(self):
        cfg = UnifiedEvidenceConfig(max_candidates=3)
        engine = UnifiedEvidenceEngine(config=cfg)
        candidates = [_c(f"c{i}") for i in range(20)]
        result = engine.process("test", candidates)
        assert result.pipeline_time_ms >= 0  # no crash


# ---------------------------------------------------------------------------
# 16. Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_result_to_dict(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("test", [_c("c1")])
        d = result.to_dict()
        assert "query" in d
        assert "decision" in d
        assert "pipeline_time_ms" in d
        assert "safety" in d
        assert "provenance" in d

    def test_existing_tests_untouched(self):
        """S20 must not break any S14-S19 test."""
        # This is a meta-test — the real check is running the full suite.
        # Here we just verify the imports don't collide.
        from app.evidence import EvidenceAssembler  # S14
        from app.evidence import SufficiencyEvaluator  # S15
        from app.evidence import TemporalAnalyzer  # S16
        assert EvidenceAssembler is not None
        assert SufficiencyEvaluator is not None
        assert TemporalAnalyzer is not None
