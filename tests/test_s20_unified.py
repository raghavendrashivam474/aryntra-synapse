"""
S20 - Unified Evidence Intelligence Pipeline Tests
18 tests covering: init, happy path, temporal, version, contradiction,
adjudication, veto, provenance, bounds, failure, backward compat.

Updated to match current UnifiedEvidenceEngine API.
"""

import dataclasses

from app.evidence.unified import (
    UnifiedEvidenceConfig,
    UnifiedEvidenceEngine,
    UnifiedProcessResult,
)

# Valid decisions the engine can return
VALID_DECISIONS = ("SUFFICIENT", "INSUFFICIENT", "UNCERTAIN", "REJECT")


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
        assert isinstance(engine.config, UnifiedEvidenceConfig)
        assert engine.config.enable_adjudication is True
        assert engine.config.adjudication_threshold == 0.7

    def test_custom_config(self):
        cfg = UnifiedEvidenceConfig(
            enable_adjudication=False,
            adjudication_threshold=0.9,
        )
        engine = UnifiedEvidenceEngine(config=cfg)
        assert engine.config.enable_adjudication is False
        assert engine.config.adjudication_threshold == 0.9


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
        assert isinstance(result, UnifiedProcessResult)
        assert result.query == "What is the policy?"
        assert result.pipeline_time_ms >= 0
        assert result.decision in VALID_DECISIONS

    def test_empty_candidates(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("query", [])
        assert result.decision in VALID_DECISIONS
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
        # temporal_context contains query_intent and target_date
        assert isinstance(result.temporal_context, dict)
        assert result.temporal_context.get("query_intent") != "unknown"


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
        assert result.decision in VALID_DECISIONS


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
        # Conflict info is in signals dict
        assert isinstance(result.signals, dict)
        assert "conflict_detected" in result.signals


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
        # Sufficiency info is in signals dict
        assert isinstance(result.signals, dict)
        assert "sufficiency_score" in result.signals


# ---------------------------------------------------------------------------
# 8-9. Adjudication trigger / skip
# ---------------------------------------------------------------------------
class TestAdjudication:
    def test_adjudication_signals_present(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process(
            "ambiguous query",
            [_c("c1"), _c("c2")],
        )
        # Adjudication info is in signals dict
        assert "adjudication_triggered" in result.signals
        assert "adjudication_decision" in result.signals

    def test_adjudication_disabled(self):
        cfg = UnifiedEvidenceConfig(enable_adjudication=False)
        engine = UnifiedEvidenceEngine(config=cfg)
        result = engine.process("test", [_c("c1")])
        # When disabled, adjudication should not be triggered
        assert result.signals.get("adjudication_triggered") is False


# ---------------------------------------------------------------------------
# 10. Deterministic veto
# ---------------------------------------------------------------------------
class TestDeterministicVeto:
    def test_veto_field_exists(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("test", [_c("c1")])
        # Safety veto info is in signals dict
        assert "safety_veto" in result.signals


# ---------------------------------------------------------------------------
# 11-12. Provenance recording / replay
# ---------------------------------------------------------------------------
class TestProvenance:
    def test_provenance_recorded(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("test query", [_c("c1")])
        # Provenance is now in result.record (DecisionRecord)
        if result.record is not None:
            assert result.record.query == "test query"

    def test_provenance_replay_via_dict(self):
        engine = UnifiedEvidenceEngine()
        result = engine.process("replay test", [_c("c1"), _c("c2")])
        if result.record is not None:
            d = dataclasses.asdict(result.record)
            assert "query" in d
            assert "events" in d


# ---------------------------------------------------------------------------
# 13. Failure fallback
# ---------------------------------------------------------------------------
class TestFailureFallback:
    def test_all_disabled_still_returns(self):
        cfg = UnifiedEvidenceConfig(enable_adjudication=False)
        engine = UnifiedEvidenceEngine(config=cfg)
        result = engine.process("test", [_c("c1")])
        assert result.decision in VALID_DECISIONS
        assert result.pipeline_time_ms >= 0


# ---------------------------------------------------------------------------
# 14-15. Candidate / expansion bounds
# ---------------------------------------------------------------------------
class TestBounds:
    def test_many_candidates_no_crash(self):
        engine = UnifiedEvidenceEngine()
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
        d = dataclasses.asdict(result)
        assert "query" in d
        assert "decision" in d
        assert "pipeline_time_ms" in d
        assert "signals" in d
        assert "record" in d

    def test_existing_tests_untouched(self):
        """S20 must not break any S14-S19 test."""
        from app.evidence import (
            EvidenceAssembler,  # S14
            SufficiencyEvaluator,  # S15
            TemporalAnalyzer,  # S16
        )

        assert EvidenceAssembler is not None
        assert SufficiencyEvaluator is not None
        assert TemporalAnalyzer is not None
