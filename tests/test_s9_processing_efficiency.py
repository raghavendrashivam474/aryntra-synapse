"""
tests/test_s9_processing_efficiency.py

Aryntra Synapse — Sprint 9
Test suite for evidence processing efficiency, embedding caching,
lexical fast-path gating, and engine integration.
"""

import numpy as np
import pytest
from app.optimization.embedding_cache import EmbeddingCache, fingerprint_text, _fingerprint
from app.optimization.semantic_gate import LexicalSemanticGate, SemanticGate, FastPathDecision
from app.context.evidence_priority import (
    EvidencePriorityEngine,
    EvidencePriorityWeights,
    PriorityClass,
    PriorityMetrics,
)


# ==============================================================================
# 1. Embedding Cache Tests
# ==============================================================================

def test_fingerprint_deterministic():
    assert _fingerprint("hello world") == fingerprint_text("hello world")
    assert fingerprint_text("query text") == fingerprint_text("query text")
    assert fingerprint_text("query text 1") != fingerprint_text("query text 2")


def test_cache_hit_returns_cached_vector():
    cache = EmbeddingCache(max_entries=10)
    calls = 0

    def mock_embed(t: str) -> np.ndarray:
        nonlocal calls
        calls += 1
        return np.array([0.1, 0.2, 0.3], dtype=np.float32)

    vec1 = cache.get_or_compute("test chunk text", mock_embed)
    vec2 = cache.get_or_compute("test chunk text", mock_embed)

    assert calls == 1
    assert np.array_equal(vec1, vec2)
    assert cache.stats()["hits"] == 1
    assert cache.stats()["misses"] == 1


def test_cache_batch_computation():
    cache = EmbeddingCache(max_entries=10)
    batch_calls = 0

    def mock_batch_embed(texts):
        nonlocal batch_calls
        batch_calls += 1
        return [np.array([float(len(t))], dtype=np.float32) for t in texts]

    texts = ["apple", "banana", "cherry"]
    vecs = cache.get_or_compute_batch(texts, mock_batch_embed)
    assert len(vecs) == 3
    assert batch_calls == 1
    assert cache.stats()["misses"] == 3

    # Fetch again with 1 overlap and 1 new
    vecs2 = cache.get_or_compute_batch(["banana", "date"], mock_batch_embed)
    assert len(vecs2) == 2
    assert batch_calls == 2  # Only 1 new item computed
    assert cache.stats()["hits"] == 1
    assert cache.stats()["misses"] == 4


def test_cache_lru_eviction():
    cache = EmbeddingCache(max_entries=2)
    cache.get_or_compute("k1", lambda t: np.array([1.0], dtype=np.float32))
    cache.get_or_compute("k2", lambda t: np.array([2.0], dtype=np.float32))
    cache.get_or_compute("k3", lambda t: np.array([3.0], dtype=np.float32))

    assert cache.stats()["size"] == 2
    # k1 should have been evicted
    assert cache.get(fingerprint_text("k1")) is None


# ==============================================================================
# 2. Lexical Fast-Path Gate Tests
# ==============================================================================

def test_gate_high_confidence_bypass():
    gate = LexicalSemanticGate(high_confidence=0.5, low_confidence=0.1)
    query = "architecture core pipeline"
    evidence = "The architecture core pipeline handles indexing and query retrieval."
    decision = gate.decide(query, evidence)

    assert decision.needs_semantic is False
    assert decision.reason == "lexical_high_confidence"
    assert decision.lexical_score >= 0.5


def test_gate_low_confidence_bypass():
    gate = LexicalSemanticGate(high_confidence=0.5, low_confidence=0.1)
    query = "quantum computing algorithms"
    evidence = "The recipe for chocolate cake requires flour and cocoa."
    decision = gate.decide(query, evidence)

    assert decision.needs_semantic is False
    assert decision.reason == "lexical_low_confidence"
    assert decision.lexical_score <= 0.1


def test_gate_ambiguous_requires_semantic():
    gate = LexicalSemanticGate(high_confidence=0.7, low_confidence=0.05)
    # Overlap is partial (1 keyword out of 4)
    query = "distributed system fault tolerance"
    evidence = "The system relies on raft consensus across nodes."
    decision = gate.decide(query, evidence)

    assert decision.needs_semantic is True
    assert decision.reason == "ambiguous_needs_semantic"


# ==============================================================================
# 3. Engine Integration Tests (S8 with S9 optimizations)
# ==============================================================================

class MockEmbedder:
    def __init__(self):
        self.call_count = 0

    def embed(self, text: str) -> np.ndarray:
        self.call_count += 1
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)

    def embed_batch(self, texts):
        self.call_count += len(texts)
        return [np.array([1.0, 0.0, 0.0], dtype=np.float32) for _ in texts]


def test_engine_with_caching_and_gate():
    mock_embed = MockEmbedder()
    q_cache = EmbeddingCache()
    ev_cache = EmbeddingCache()
    gate = LexicalSemanticGate(high_confidence=0.5, low_confidence=0.05)

    engine = EvidencePriorityEngine(
        embedding_model=mock_embed,
        weights=EvidencePriorityWeights.full_blend(),
        query_cache=q_cache,
        evidence_cache=ev_cache,
        semantic_gate=gate,
    )

    query = "architecture core components"
    chunks = [
        {"chunk_id": "c1", "text": "The architecture core components are modular.", "fingerprint": "fp1"},
        {"chunk_id": "c2", "text": "Cooking lasagna in the oven.", "fingerprint": "fp2"},
        {"chunk_id": "c3", "text": "The core design principles enable scalability.", "fingerprint": "fp3"},
    ]

    # Run 1: Cold caches
    ranked, metrics = engine.rank(query, chunks)
    assert len(ranked) == 3
    assert metrics.lexical_fast_path_hits >= 1
    assert metrics.semantic_fallback_count >= 1
    assert metrics.query_cache_misses == 1

    # Run 2: Warm caches with identical query and chunks
    mock_embed.call_count = 0
    ranked2, metrics2 = engine.rank(query, chunks)
    assert len(ranked2) == 3
    assert metrics2.query_cache_hits == 1
    assert metrics2.semantic_cache_hits >= 1
    assert mock_embed.call_count == 0  # Zero embedding calls due to cache hit!


def test_engine_backward_compatibility_when_s9_disabled():
    """When no caches or gate are passed, engine works identically to pure S8."""
    mock_embed = MockEmbedder()
    engine = EvidencePriorityEngine(
        embedding_model=mock_embed,
        weights=EvidencePriorityWeights.semantic_only(),
    )

    query = "test query"
    chunks = [{"chunk_id": "c1", "text": "test chunk"}]
    ranked, metrics = engine.rank(query, chunks)

    assert len(ranked) == 1
    assert metrics.semantic_calls > 0
    assert metrics.semantic_cache_hits == 0
    assert metrics.lexical_fast_path_hits == 0
