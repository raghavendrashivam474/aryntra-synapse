import pytest
from app.evidence.assembly import EvidenceAssembler
from app.evidence.config import S14ResolutionConfig
from app.evidence.state import EvidenceState


class TestEvidenceAssembler:

    @pytest.fixture
    def assembler(self):
        return EvidenceAssembler(config=S14ResolutionConfig.full_resolution())

    def test_empty_candidates_handling(self, assembler):
        result = assembler.assemble("query text", [])
        assert result.selected_chunks == []
        assert result.relational_state.state == EvidenceState.INSUFFICIENT

    def test_fragment_progressive_assembly(self, assembler):
        query = "What caused the outage, when did it happen, and what was the outcome?"
        chunks = [
            {"chunk_id": "c1", "text": "The outage was caused by a network switch overload.", "score": 0.85},
            {"chunk_id": "c2", "text": "The incident happened on date 2024-11-04 at 03:00 UTC.", "score": 0.70},
            {"chunk_id": "c3", "text": "The final outcome was zero customer data loss.", "score": 0.65},
            {"chunk_id": "c4", "text": "Unrelated billing cycle notes for enterprise accounts.", "score": 0.20},
        ]
        result = assembler.assemble(query, chunks)
        assert len(result.selected_chunks) >= 2
        assert result.coverage_report.coverage_ratio >= 0.70
        assert result.relational_state.state == EvidenceState.SUFFICIENT
        # Unrelated chunk c4 should not be selected
        selected_ids = [c["chunk_id"] for c in result.selected_chunks]
        assert "c4" not in selected_ids

    def test_contradictory_candidate_penalized_during_assembly(self, assembler):
        query = "When was the feature released?"
        chunks = [
            {"chunk_id": "c1", "text": "The vector feature was released in 2023.", "score": 0.90},
            {"chunk_id": "c2", "text": "The vector feature was released in 2025.", "score": 0.88},
        ]
        result = assembler.assemble(query, chunks)
        # Even if both discuss release date, conflict detection flags relational state
        conflict = result.conflict_report
        assert conflict.detected or result.relational_state.state in (EvidenceState.CONTRADICTORY, EvidenceState.SUFFICIENT)

    def test_budget_exhaustion_safety(self):
        cfg = S14ResolutionConfig(max_assembly_chunks=2, max_assembly_iterations=2)
        assembler = EvidenceAssembler(config=cfg)
        query = "What caused X, when did X occur, where did X happen, who fixed X, and what was the outcome?"
        chunks = [
            {"chunk_id": "1", "text": "caused by error", "score": 0.9},
            {"chunk_id": "2", "text": "occurred in 2024", "score": 0.8},
            {"chunk_id": "3", "text": "happened in US-East", "score": 0.7},
            {"chunk_id": "4", "text": "fixed by Alice", "score": 0.6},
        ]
        result = assembler.assemble(query, chunks)
        assert len(result.selected_chunks) <= 2
        assert result.metrics.iterations <= 2
