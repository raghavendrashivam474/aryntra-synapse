import pytest
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.evidence.contradiction import ConflictReport, ConflictPair, ConflictType
from app.evidence.coverage import CoverageReport


class TestS14ConfidenceGuardRouting:

    @pytest.fixture
    def guard(self):
        return ConfidenceGuard()

    def test_contradiction_triggers_resolve_conflict(self, guard):
        ranked = [
            {"chunk_id": "1", "text": "Launched in 2024", "priority_score": 0.9, "priority_class": "HIGH"},
            {"chunk_id": "2", "text": "Launched in 2025", "priority_score": 0.8, "priority_class": "HIGH"},
        ]
        conflict = ConflictReport(
            detected=True,
            conflict_score=0.75,
            conflicts=[ConflictPair("1", "2", ConflictType.DATE, "mismatch", 0.8)],
            conflicted_chunk_ids={"1", "2"}
        )
        assessment = guard.assess("When did it launch?", ranked, conflict_report=conflict)
        assert assessment.decision == FallbackDecision.RESOLVE_CONFLICT
        assert "contradiction_detected" in assessment.reason

    def test_low_coverage_triggers_expand_coverage(self, guard):
        ranked = [
            {"chunk_id": "1", "text": "The cause was bug X", "priority_score": 0.40, "priority_class": "MEDIUM"},
        ]
        coverage = CoverageReport(
            query_concepts=["cause", "time", "outcome"],
            covered_concepts=["cause"],
            missing_concepts=["time", "outcome"],
            coverage_ratio=0.33,
            is_sufficient=False,
        )
        assessment = guard.assess("What caused it, when, and outcome?", ranked, coverage_report=coverage)
        assert assessment.decision in (FallbackDecision.EXPAND_COVERAGE, FallbackDecision.FALLBACK_BROAD)
