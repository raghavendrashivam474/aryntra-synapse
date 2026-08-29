"""S12 - Tests for Evidence Survival Telemetry."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.context.calibration import EvidenceSurvivalTracker


class TestEvidenceSurvivalTracker:
    def setup_method(self):
        self.tracker = EvidenceSurvivalTracker()
        self.chunks = [
            {"chunk_id": "c1", "text": "answer bearing"},
            {"chunk_id": "c2", "text": "distractor"},
            {"chunk_id": "c3", "text": "answer bearing too"},
        ]
        self.answer_ids = {"c1", "c3"}

    def test_mark_retrieved(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        assert self.tracker.record_count == 3

    def test_answer_bearing_identification(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        stats = self.tracker.get_answer_bearing_stats("q1")
        assert stats["total"] == 2
        assert stats["retrieved"] == 2

    def test_mark_prefilter_all_survive(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        self.tracker.mark_prefilter("q1", {"c1", "c2", "c3"})
        stats = self.tracker.get_answer_bearing_stats("q1")
        assert stats["survived"] == 2

    def test_mark_prefilter_loss(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        self.tracker.mark_prefilter("q1", {"c2"})
        stats = self.tracker.get_answer_bearing_stats("q1")
        assert stats["survived"] == 0

    def test_mark_priority(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        ranked = [
            {"chunk_id": "c1", "priority_class": "HIGH", "priority_score": 0.8, "state": "active"},
            {"chunk_id": "c2", "priority_class": "LOW", "priority_score": 0.1, "state": "retained"},
            {"chunk_id": "c3", "priority_class": "MEDIUM", "priority_score": 0.5, "state": "retained"},
        ]
        self.tracker.mark_priority("q1", ranked)
        stats = self.tracker.get_answer_bearing_stats("q1")
        assert stats["promoted"] == 1

    def test_mark_final_context(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        self.tracker.mark_final_context("q1", {"c1", "c3"})
        stats = self.tracker.get_answer_bearing_stats("q1")
        assert stats["final"] == 2

    def test_survival_rates_full_pipeline(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        self.tracker.mark_prefilter("q1", {"c1", "c2", "c3"})
        ranked = [
            {"chunk_id": "c1", "priority_class": "HIGH", "priority_score": 0.8, "state": "active"},
            {"chunk_id": "c3", "priority_class": "HIGH", "priority_score": 0.7, "state": "active"},
            {"chunk_id": "c2", "priority_class": "LOW", "priority_score": 0.1, "state": "retained"},
        ]
        self.tracker.mark_priority("q1", ranked)
        self.tracker.mark_final_context("q1", {"c1", "c3"})
        rates = self.tracker.get_survival_rates("q1")
        assert rates["retrieval_rate"] == 1.0
        assert rates["survival_rate"] == 1.0
        assert rates["promotion_rate"] == 1.0
        assert rates["final_rate"] == 1.0

    def test_empty_query(self):
        stats = self.tracker.get_answer_bearing_stats("nonexistent")
        assert stats["total"] == 0

    def test_reset(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        assert self.tracker.record_count == 3
        self.tracker.reset()
        assert self.tracker.record_count == 0

    def test_to_list(self):
        self.tracker.mark_retrieved("q1", self.chunks, self.answer_ids)
        records = self.tracker.to_list()
        assert len(records) == 3
        assert "chunk_id" in records[0]
        assert "is_answer_bearing" in records[0]

    def test_survival_rates_empty(self):
        rates = self.tracker.get_survival_rates("nonexistent")
        assert rates["retrieval_rate"] == 0.0
        assert rates["final_rate"] == 0.0
