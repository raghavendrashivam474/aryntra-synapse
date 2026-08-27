"""
tests/test_s6_semantic_gate.py

Aryntra Synapse — Sprint 6
Unit tests for SemanticGate and SemanticSufficiencyEngine.

Tests cover:
- Semantic score computation correctness
- Identical query/evidence behavior
- Unrelated evidence behavior
- Threshold enforcement
- Lexical + semantic combination (blended mode)
- Empty evidence handling
- S5 mode preservation
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from app.context.semantic_gate import SemanticGate, SemanticResult, cosine_similarity
from app.context.sufficiency import (
    SufficiencyEngine,
    SufficiencyResult,
    SemanticSufficiencyEngine,
    SemanticSufficiencyResult,
)


# --- Fixtures ---

@pytest.fixture
def mock_embedder():
    """
    Mock EmbeddingModel that returns deterministic orthogonal vectors.
    Uses 5 dimensions to separate concepts cleanly.
    """
    embedder = MagicMock()

    def fake_embed(text: str) -> np.ndarray:
        text_lower = text.lower()
        # Dimension 0: Retention / Storage / Workspace
        if any(w in text_lower for w in ["retain", "store", "workspace", "data"]):
            return np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Dimension 1: Causes / Reasons / Why
        elif any(w in text_lower for w in ["cause", "reason", "why"]):
            return np.array([0.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Dimension 2: Dates / Years / Incidents
        elif any(w in text_lower for w in ["2024", "occurred", "event"]):
            return np.array([0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        # Dimension 3: Generic Query
        elif "query" in text_lower:
            return np.array([0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        # Dimension 4: Generic Evidence
        else:
            return np.array([0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)

    embedder.embed = MagicMock(side_effect=fake_embed)
    embedder.embed_batch = MagicMock(
        side_effect=lambda texts: np.array([fake_embed(t) for t in texts])
    )
    return embedder


@pytest.fixture
def semantic_gate(mock_embedder):
    return SemanticGate(mock_embedder)


@pytest.fixture
def lexical_engine():
    return SufficiencyEngine(score_threshold=0.45, coverage_threshold=0.25)


@pytest.fixture
def blended_engine(lexical_engine, semantic_gate):
    return SemanticSufficiencyEngine(
        lexical_engine=lexical_engine,
        semantic_gate=semantic_gate,
        semantic_threshold=0.50,
        mode="blended",
    )


@pytest.fixture
def semantic_only_engine(lexical_engine, semantic_gate):
    return SemanticSufficiencyEngine(
        lexical_engine=lexical_engine,
        semantic_gate=semantic_gate,
        semantic_threshold=0.50,
        mode="semantic_only",
    )


# --- cosine_similarity tests ---

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert cosine_similarity(a, b) == 0.0


# --- SemanticGate tests ---

class TestSemanticGate:
    def test_empty_chunks(self, semantic_gate):
        result = semantic_gate.evaluate("test query", [])
        assert result.semantic_score == 0.0
        assert result.max_chunk_similarity == 0.0

    def test_semantic_score_computed(self, semantic_gate):
        chunks = [{"text": "Information is stored in the workspace."}]
        result = semantic_gate.evaluate("How is data retained?", chunks)
        # Both map to Dimension 0 -> similarity should be 1.0
        assert result.semantic_score == pytest.approx(1.0, abs=1e-6)
        assert result.query_embedding_dim == 5

    def test_related_evidence_higher_than_unrelated(self, semantic_gate):
        related = [{"text": "Information is stored in the workspace."}]
        unrelated = [{"text": "The event occurred in 2024."}]

        # Query maps to Dimension 0
        r_related = semantic_gate.evaluate("How is data retained?", related)
        r_unrelated = semantic_gate.evaluate("How is data retained?", unrelated)

        assert r_related.semantic_score > r_unrelated.semantic_score
        assert r_unrelated.semantic_score == 0.0  # Dimension 0 vs Dimension 2 is orthogonal

    def test_result_to_dict(self, semantic_gate):
        chunks = [{"text": "Data is stored in the workspace."}]
        result = semantic_gate.evaluate("How is data retained?", chunks)
        d = result.to_dict()
        assert "semantic_score" in d
        assert "max_chunk_similarity" in d
        assert "mean_chunk_similarity" in d


# --- SemanticSufficiencyEngine tests ---

class TestSemanticSufficiencyEngine:
    def test_blended_both_pass(self, blended_engine):
        """Both lexical and semantic signals pass -> sufficient."""
        chunks = [{
            "text": "Information is stored in the workspace for retention.",
            "score": 0.80,
        }]
        result = blended_engine.evaluate(
            "How is data retained in the workspace?", chunks
        )
        assert result.is_sufficient is True
        assert "sufficient" in result.reason

    def test_blended_semantic_fails(self, blended_engine):
        """Lexical passes but semantic fails -> insufficient in blended."""
        chunks = [{
            # Contains "event" to pass the lexical keyword coverage filter
            "text": "The event occurred in 2024.",
            "score": 0.80,
        }]
        # Query maps to Dimension 1 ("cause"); chunks map to Dimension 2 ("event"). Orthogonal!
        result = blended_engine.evaluate(
            "What caused the event?", chunks
        )
        assert result.semantic_score == 0.0
        assert result.is_sufficient is False
        assert result.reason == "lexical_pass_semantic_insufficient"

    def test_semantic_only_mode(self, semantic_only_engine):
        """semantic_only mode ignores lexical signal."""
        chunks = [{
            "text": "Information is stored in the workspace.",
            "score": 0.10,  # Would fail S5 lexical score threshold
        }]
        result = semantic_only_engine.evaluate(
            "How is data retained?", chunks
        )
        # Should pass on semantic alone (1.0 similarity) despite low S5 retrieval score
        assert result.semantic_score == pytest.approx(1.0, abs=1e-6)
        assert result.is_sufficient is True

    def test_empty_chunks_insufficient(self, blended_engine):
        result = blended_engine.evaluate("test query", [])
        assert result.is_sufficient is False

    def test_result_observability(self, blended_engine):
        """Result contains both lexical and semantic details (§17)."""
        chunks = [{
            "text": "Information is stored in the workspace.",
            "score": 0.60,
        }]
        result = blended_engine.evaluate("How is data retained?", chunks)
        d = result.to_dict()
        assert "lexical" in d
        assert "semantic_score" in d
        assert "combined_score" in d
        assert "is_sufficient" in d
        assert "reason" in d

    def test_invalid_mode_raises(self, lexical_engine, semantic_gate):
        with pytest.raises(ValueError, match="Unknown mode"):
            SemanticSufficiencyEngine(
                lexical_engine=lexical_engine,
                semantic_gate=semantic_gate,
                mode="invalid_mode",
            )

    def test_threshold_respected(self, lexical_engine, semantic_gate):
        """High threshold should make sufficiency harder."""
        strict = SemanticSufficiencyEngine(
            lexical_engine=lexical_engine,
            semantic_gate=semantic_gate,
            semantic_threshold=0.99,
            mode="semantic_only",
        )
        # Query ("test query") maps to Dim 3; Chunk ("Some evidence.") maps to Dim 4. Similarity = 0.0
        chunks = [{"text": "Some evidence.", "score": 0.80}]
        result = strict.evaluate("test query", chunks)
        assert result.is_sufficient is False

    def test_s5_lexical_preserved(self, blended_engine):
        """The lexical result inside S6 should match S5 behavior."""
        chunks = [{
            "text": "Information is stored in the workspace.",
            "score": 0.80,
        }]
        result = blended_engine.evaluate("How is information retained?", chunks)
        # The lexical sub-result should be a valid S5 SufficiencyResult
        assert isinstance(result.lexical_result, SufficiencyResult)
        assert result.lexical_result.top_score == 0.80
