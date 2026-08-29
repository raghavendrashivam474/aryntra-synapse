import pytest
from app.evidence.contradiction import (
    ContradictionDetector,
    ConflictType,
    ConflictReport,
)


class TestContradictionDetector:

    @pytest.fixture
    def detector(self):
        return ContradictionDetector(topic_similarity_threshold=0.25)

    def test_empty_or_single_chunk_no_conflict(self, detector):
        assert not detector.analyze([]).detected
        assert not detector.analyze([{"chunk_id": "1", "text": "Service launched in 2024."}]).detected

    def test_date_temporal_contradiction(self, detector):
        chunks = [
            {"chunk_id": "A", "text": "Synapse engine production service was deployed in 2023 across datacenters."},
            {"chunk_id": "B", "text": "Synapse engine production service was deployed in 2025 across datacenters."},
        ]
        report = detector.analyze(chunks)
        assert report.detected
        assert report.conflict_score > 0.0
        assert "A" in report.conflicted_chunk_ids
        assert "B" in report.conflicted_chunk_ids
        assert any(c.conflict_type == ConflictType.DATE for c in report.conflicts)

    def test_status_contradiction(self, detector):
        chunks = [
            {"chunk_id": "c1", "text": "Distributed vector cache indexing feature is currently enabled and supported in production."},
            {"chunk_id": "c2", "text": "Distributed vector cache indexing feature is deprecated and disabled in production."},
        ]
        report = detector.analyze(chunks)
        assert report.detected
        assert any(c.conflict_type == ConflictType.STATUS for c in report.conflicts)

    def test_explicit_negation_contradiction(self, detector):
        chunks = [
            {"chunk_id": "c1", "text": "The memory optimizer allocates dedicated GPU buffers for large models."},
            {"chunk_id": "c2", "text": "The memory optimizer does not allocate dedicated GPU buffers for large models."},
        ]
        report = detector.analyze(chunks)
        assert report.detected
        assert any(c.conflict_type == ConflictType.NEGATION for c in report.conflicts)

    def test_numeric_metric_contradiction(self, detector):
        chunks = [
            {"chunk_id": "c1", "text": "Cluster throughput reached 5000 transactions per second under peak load."},
            {"chunk_id": "c2", "text": "Cluster throughput reached 1200 transactions per second under peak load."},
        ]
        report = detector.analyze(chunks)
        assert report.detected
        assert any(c.conflict_type == ConflictType.NUMERIC for c in report.conflicts)

    def test_unrelated_chunks_no_false_conflict(self, detector):
        chunks = [
            {"chunk_id": "c1", "text": "Synapse uses token bucket rate limiting for gateway traffic."},
            {"chunk_id": "c2", "text": "The database cluster was upgraded in 2022 to PostgreSQL 15."},
        ]
        report = detector.analyze(chunks)
        assert not report.detected
        assert report.conflict_score == 0.0

    def test_non_truth_adjudication_invariant(self, detector):
        """Brief §6: ContradictionDetector detects conflict without adjudicating truth."""
        chunks = [
            {"chunk_id": "c1", "text": "System latency benchmark achieved 15ms response time."},
            {"chunk_id": "c2", "text": "System latency benchmark achieved 85ms response time."},
        ]
        report = detector.analyze(chunks)
        d = report.to_dict()
        assert "detected" in d
        assert "conflicts" in d
        assert "truth" not in d
        assert "winner" not in d
