"""
app/context/semantic_gate.py

Aryntra Synapse — Sprint 6
Semantic sufficiency signal using existing embedding infrastructure.

Responsibilities:
- Compute cosine similarity between query and active evidence
- Return a semantic sufficiency score
- Zero LLM calls; uses local SentenceTransformer embeddings

This is Candidate A from the S6 specification: the simplest possible
semantic signal. It reuses the existing EmbeddingModel and adds no
new dependencies.
"""

import logging
import numpy as np
from typing import List, Dict, Any

from app.retrieval.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class SemanticResult:
    """Immutable record of a semantic similarity evaluation."""

    def __init__(
        self,
        semantic_score: float,
        max_chunk_similarity: float,
        mean_chunk_similarity: float,
        query_embedding_dim: int,
    ):
        self.semantic_score = semantic_score
        self.max_chunk_similarity = max_chunk_similarity
        self.mean_chunk_similarity = mean_chunk_similarity
        self.query_embedding_dim = query_embedding_dim

    def to_dict(self) -> dict:
        return {
            "semantic_score": round(self.semantic_score, 4),
            "max_chunk_similarity": round(self.max_chunk_similarity, 4),
            "mean_chunk_similarity": round(self.mean_chunk_similarity, 4),
            "query_embedding_dim": self.query_embedding_dim,
        }


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SemanticGate:
    """
    Lightweight semantic sufficiency signal.

    Compares the query embedding against the active evidence embedding
    using cosine similarity. Uses the existing EmbeddingModel infrastructure.
    No LLM calls required.

    Primary signal: cosine(query, concatenated_evidence)
    Observability:  per-chunk max and mean similarities
    """

    def __init__(self, embedding_model: EmbeddingModel):
        self._embedder = embedding_model

    def evaluate(
        self,
        query: str,
        active_chunks: List[Dict[str, Any]],
    ) -> SemanticResult:
        """
        Compute semantic similarity between query and active evidence.

        The primary signal (semantic_score) is the cosine similarity between
        the query embedding and the concatenated active evidence embedding.

        Per-chunk similarities are also computed for observability.
        """
        if not active_chunks:
            return SemanticResult(
                semantic_score=0.0,
                max_chunk_similarity=0.0,
                mean_chunk_similarity=0.0,
                query_embedding_dim=0,
            )

        # Embed query
        query_vec = self._embedder.embed(query)

        # Embed concatenated evidence (primary signal)
        evidence_text = " ".join(c.get("text", "") for c in active_chunks)
        if not evidence_text.strip():
            return SemanticResult(
                semantic_score=0.0,
                max_chunk_similarity=0.0,
                mean_chunk_similarity=0.0,
                query_embedding_dim=len(query_vec),
            )

        evidence_vec = self._embedder.embed(evidence_text)
        semantic_score = cosine_similarity(query_vec, evidence_vec)

        # Per-chunk similarities (observability)
        chunk_sims = []
        for chunk in active_chunks:
            chunk_text = chunk.get("text", "")
            if chunk_text.strip():
                chunk_vec = self._embedder.embed(chunk_text)
                chunk_sims.append(cosine_similarity(query_vec, chunk_vec))

        max_chunk_sim = max(chunk_sims) if chunk_sims else 0.0
        mean_chunk_sim = float(np.mean(chunk_sims)) if chunk_sims else 0.0

        result = SemanticResult(
            semantic_score=semantic_score,
            max_chunk_similarity=max_chunk_sim,
            mean_chunk_similarity=mean_chunk_sim,
            query_embedding_dim=len(query_vec),
        )

        logger.info(
            f"SemanticGate: score={semantic_score:.4f} "
            f"(max_chunk={max_chunk_sim:.4f}, mean_chunk={mean_chunk_sim:.4f})"
        )
        return result
