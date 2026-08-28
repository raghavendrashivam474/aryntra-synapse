"""
tests/test_s8_evidence_priority.py

Aryntra Synapse — Sprint 8
Evidence relevance & priority management test suite.
"""

import pytest
from app.context.evidence_priority import (
    EvidencePriorityEngine,
    EvidencePriorityWeights,
    PriorityClass,
)
from app.context.workspace import EvidenceWorkspace
from app.retrieval.embeddings import EmbeddingModel


@pytest.fixture(scope="module")
def embedder():
    return EmbeddingModel()


@pytest.fixture
def priority_engine(embedder):
    return EvidencePriorityEngine(embedding_model=embedder)


class TestDeterminism:
    def test_same_input_same_score(self, priority_engine):
        query = "How does vector indexing work in FAISS?"
        chunks = [
            {"chunk_id": "c1", "text": "FAISS provides efficient vector indexing algorithms.", "score": 0.85},
            {"chunk_id": "c2", "text": "Unrelated topic about gardening and soil nutrients.", "score": 0.20},
        ]

        ranked1, m1 = priority_engine.rank(query, chunks)
        ranked2, m2 = priority_engine.rank(query, chunks)

        assert len(ranked1) == len(ranked2)
        for r1, r2 in zip(ranked1, ranked2):
            assert r1["chunk_id"] == r2["chunk_id"]
            assert r1["priority_score"] == r2["priority_score"]
            assert r1["priority_class"] == r2["priority_class"]
            assert r1["semantic_score"] == r2["semantic_score"]
            assert r1["lexical_score"] == r2["lexical_score"]


class TestRankingAndClassification:
    def test_relevant_ranks_above_irrelevant(self, priority_engine):
        query = "What is Retrieval Augmented Generation?"
        chunks = [
            {"chunk_id": "irr_1", "text": "Baking sourdough bread requires water, flour, and yeast.", "score": 0.1},
            {"chunk_id": "rel_1", "text": "Retrieval Augmented Generation combines retrieval with generative language models.", "score": 0.9},
        ]

        ranked, metrics = priority_engine.rank(query, chunks)
        assert ranked[0]["chunk_id"] == "rel_1"
        assert ranked[1]["chunk_id"] == "irr_1"
        assert ranked[0]["priority_score"] > ranked[1]["priority_score"]
        assert ranked[0]["priority_class"] in (PriorityClass.HIGH.value, PriorityClass.MEDIUM.value)
        assert ranked[1]["priority_class"] == PriorityClass.LOW.value

    def test_threshold_classification(self, embedder):
        weights = EvidencePriorityWeights(
            semantic_weight=0.5, lexical_weight=0.5, reuse_weight=0.0,
            high_threshold=0.70, medium_threshold=0.30
        )
        engine = EvidencePriorityEngine(embedding_model=embedder, weights=weights)
        query = "machine learning models"
        chunks = [
            {"chunk_id": "c_high", "text": "machine learning models learn patterns from training data.", "score": 0.95},
            {"chunk_id": "c_low", "text": "The solar system contains eight planets orbiting the sun.", "score": 0.10},
        ]

        ranked, metrics = engine.rank(query, chunks)
        assert metrics.high_priority_count >= 1
        assert metrics.low_priority_count >= 1
        assert metrics.active_evidence_count >= 1


class TestEdgeCases:
    def test_empty_chunks_list(self, priority_engine):
        ranked, metrics = priority_engine.rank("query", [])
        assert ranked == []
        assert metrics.high_priority_count == 0
        assert metrics.average_priority_score == 0.0
        assert metrics.active_evidence_count == 0

    def test_empty_query_text(self, priority_engine):
        chunks = [{"chunk_id": "c1", "text": "Sample text here", "score": 0.5}]
        ranked, metrics = priority_engine.rank("", chunks)
        assert len(ranked) == 1
        assert ranked[0]["priority_score"] >= 0.0

    def test_whitespace_chunk_text(self, priority_engine):
        chunks = [{"chunk_id": "c_empty", "text": "   ", "score": 0.0}]
        ranked, metrics = priority_engine.rank("sample query", chunks)
        assert len(ranked) == 1
        assert ranked[0]["semantic_score"] == 0.0
        assert ranked[0]["lexical_score"] == 0.0


class TestS7ReuseIntegration:
    def test_reused_signal_increases_priority_score(self, embedder):
        weights = EvidencePriorityWeights(
            semantic_weight=0.4, lexical_weight=0.3, reuse_weight=0.3,
            high_threshold=0.6, medium_threshold=0.3
        )
        engine = EvidencePriorityEngine(embedding_model=embedder, weights=weights)
        query = "Python programming"

        chunk_new = {"chunk_id": "c_new", "text": "Python programming language.", "score": 0.5, "evidence_status": "new"}
        chunk_reused = {"chunk_id": "c_reused", "text": "Python programming language.", "score": 0.5, "evidence_status": "reused"}

        ranked_new, _ = engine.rank(query, [chunk_new])
        ranked_reused, _ = engine.rank(query, [chunk_reused])

        assert ranked_reused[0]["reuse_score"] == 1.0
        assert ranked_new[0]["reuse_score"] == 0.0
        assert ranked_reused[0]["priority_score"] > ranked_new[0]["priority_score"]


class TestAblationWeights:
    def test_semantic_only_mode(self, embedder):
        engine = EvidencePriorityEngine(
            embedding_model=embedder,
            weights=EvidencePriorityWeights.semantic_only()
        )
        query = "Artificial Intelligence concepts"
        chunks = [
            {"chunk_id": "c1", "text": "AI and machine intelligence methodologies.", "score": 0.8, "evidence_status": "reused"}
        ]
        ranked, _ = engine.rank(query, chunks)
        assert ranked[0]["priority_score"] == pytest.approx(ranked[0]["semantic_score"], abs=1e-4)

    def test_lexical_only_mode(self, embedder):
        engine = EvidencePriorityEngine(
            embedding_model=embedder,
            weights=EvidencePriorityWeights.lexical_only()
        )
        query = "Artificial Intelligence concepts"
        chunks = [
            {"chunk_id": "c1", "text": "Artificial Intelligence concepts and paradigms.", "score": 0.8}
        ]
        ranked, _ = engine.rank(query, chunks)
        assert ranked[0]["priority_score"] == pytest.approx(ranked[0]["lexical_score"], abs=1e-4)


class TestWorkspaceIntegration:
    def test_workspace_promotes_high_priority_first(self, priority_engine):
        query = "vector database indexing"
        raw_chunks = [
            {"chunk_id": "c_irr", "text": "Cooking pasta in boiling salted water.", "score": 0.1},
            {"chunk_id": "c_high", "text": "Vector database indexing algorithms like HNSW and IVF.", "score": 0.95},
            {"chunk_id": "c_med", "text": "Databases store data records efficiently.", "score": 0.6},
        ]
        ranked_chunks, _ = priority_engine.rank(query, raw_chunks)
        ws = EvidenceWorkspace(chunks=ranked_chunks, max_active=3)

        events = ws.promote_priority_initial(fallback_count=1)
        active = ws.active()

        assert len(active) >= 1
        assert active[0]["chunk_id"] == "c_high"
        assert ws.available_count == len(raw_chunks) - len(active)
