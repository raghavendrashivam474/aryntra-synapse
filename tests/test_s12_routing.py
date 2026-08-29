"""S12 - Tests for Confidence Guard and Fallback Routing."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.strategy.fallback import ConfidenceGuard, FallbackDecision, ConfidenceAssessment


class TestConfidenceGuard:
    def setup_method(self):
        self.guard = ConfidenceGuard()

    def test_empty_chunks_fallback(self):
        result = self.guard.assess("test query", [])
        assert result.decision == FallbackDecision.FALLBACK_BROAD
        assert result.confidence_score == 0.0

    def test_high_confidence_trust(self):
        ranked = [
            {"chunk_id": "c1", "text": "priority score alpha beta gamma semantic lexical",
             "priority_score": 0.9, "priority_class": "HIGH", "state": "active"},
            {"chunk_id": "c2", "text": "unrelated filler text about databases",
             "priority_score": 0.1, "priority_class": "LOW", "state": "retained"},
            {"chunk_id": "c3", "text": "more filler about cloud computing",
             "priority_score": 0.05, "priority_class": "LOW", "state": "retained"},
        ] * 10
        result = self.guard.assess("priority score alpha", ranked)
        assert result.decision == FallbackDecision.TRUST_PRIORITY
        assert result.confidence_score >= 0.55

    def test_low_confidence_fallback(self):
        ranked = [
            {"chunk_id": "c1", "text": "random text",
             "priority_score": 0.12, "priority_class": "LOW", "state": "retained"},
            {"chunk_id": "c2", "text": "more random",
             "priority_score": 0.11, "priority_class": "LOW", "state": "retained"},
        ]
        result = self.guard.assess("complex query about priority", ranked)
        assert result.decision in (FallbackDecision.FALLBACK_BROAD, FallbackDecision.FALLBACK_SKIP)

    def test_to_dict(self):
        ranked = [
            {"chunk_id": "c1", "text": "test",
             "priority_score": 0.5, "priority_class": "HIGH"}
        ] * 10
        result = self.guard.assess("test", ranked)
        d = result.to_dict()
        assert "decision" in d
        assert "confidence_score" in d
        assert "signals" in d

    def test_signals_populated(self):
        ranked = [
            {"chunk_id": "c1", "text": "test query keywords",
             "priority_score": 0.8, "priority_class": "HIGH"},
            {"chunk_id": "c2", "text": "other text",
             "priority_score": 0.3, "priority_class": "MEDIUM"},
        ] * 10
        result = self.guard.assess("test query", ranked)
        assert "score_margin" in result.signals
        assert "high_count" in result.signals
        assert "corpus_size" in result.signals

    def test_fallback_decision_enum(self):
        assert FallbackDecision.TRUST_PRIORITY.value == "trust_priority"
        assert FallbackDecision.FALLBACK_BROAD.value == "fallback_broad"
        assert FallbackDecision.FALLBACK_SKIP.value == "fallback_skip"
