"""
app/context/evidence_priority.py

Aryntra Synapse — Sprint 8
Evidence relevance and priority management engine.

Responsibilities:
- Calculate individual priority signals (semantic, lexical, reuse)
- Compute deterministic unified priority score
- Classify evidence into HIGH, MEDIUM, LOW classes
- Route/partition evidence into active and retained states
- Zero LLM calls; completely deterministic
"""

import time
import logging
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from app.context.sufficiency import extract_keywords
from app.context.semantic_gate import cosine_similarity
from app.retrieval.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class PriorityClass(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidencePriorityWeights:
    """Configurable weights and thresholds for S8 Priority scoring."""

    def __init__(
        self,
        semantic_weight: float = 0.50,
        lexical_weight: float = 0.30,
        reuse_weight: float = 0.20,
        high_threshold: float = 0.60,
        medium_threshold: float = 0.30,
    ):
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.reuse_weight = reuse_weight
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    @classmethod
    def semantic_only(cls) -> "EvidencePriorityWeights":
        return cls(semantic_weight=1.0, lexical_weight=0.0, reuse_weight=0.0)

    @classmethod
    def lexical_only(cls) -> "EvidencePriorityWeights":
        return cls(semantic_weight=0.0, lexical_weight=1.0, reuse_weight=0.0)

    @classmethod
    def semantic_lexical(cls) -> "EvidencePriorityWeights":
        return cls(semantic_weight=0.60, lexical_weight=0.40, reuse_weight=0.0)

    @classmethod
    def full_blend(cls) -> "EvidencePriorityWeights":
        return cls(semantic_weight=0.50, lexical_weight=0.30, reuse_weight=0.20)


class PrioritizedEvidenceChunk:
    """A wrapper containing the original chunk and its priority metrics."""

    def __init__(
        self,
        chunk: Dict[str, Any],
        semantic_score: float,
        lexical_score: float,
        reuse_score: float,
        priority_score: float,
        priority_class: PriorityClass,
        state: str = "retained",
    ):
        self.chunk = chunk
        self.chunk_id = chunk.get("chunk_id", "")
        self.text = chunk.get("text", "")
        self.semantic_score = semantic_score
        self.lexical_score = lexical_score
        self.reuse_score = reuse_score
        self.priority_score = priority_score
        self.priority_class = priority_class
        self.state = state

    def to_dict(self) -> Dict[str, Any]:
        """Convert prioritized chunk to flat dict preserving existing keys."""
        d = dict(self.chunk)
        d.update({
            "semantic_score": round(self.semantic_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "reuse_score": round(self.reuse_score, 4),
            "priority_score": round(self.priority_score, 4),
            "priority_class": self.priority_class.value,
            "state": self.state,
        })
        return d


class PriorityMetrics:
    """Immutable metrics record of priority calculation for a retrieval batch."""

    def __init__(
        self,
        priority_latency: float,
        high_priority_count: int,
        medium_priority_count: int,
        low_priority_count: int,
        active_evidence_count: int,
        retained_evidence_count: int,
        average_priority_score: float,
    ):
        self.priority_latency = priority_latency
        self.high_priority_count = high_priority_count
        self.medium_priority_count = medium_priority_count
        self.low_priority_count = low_priority_count
        self.active_evidence_count = active_evidence_count
        self.retained_evidence_count = retained_evidence_count
        self.average_priority_score = average_priority_score

    def to_dict(self) -> dict:
        return {
            "priority_latency": round(self.priority_latency, 6),
            "high_priority_count": self.high_priority_count,
            "medium_priority_count": self.medium_priority_count,
            "low_priority_count": self.low_priority_count,
            "active_evidence_count": self.active_evidence_count,
            "retained_evidence_count": self.retained_evidence_count,
            "average_priority_score": round(self.average_priority_score, 4),
        }


class EvidencePriorityEngine:
    """
    S8 Evidence Priority Engine.

    Scores each candidate evidence chunk using:
    - Semantic Similarity (via cosine similarity with query embedding)
    - Lexical Similarity (query keyword matching/overlap)
    - Reuse Value (S7 metadata indicating whether chunk was already processed)

    Then ranks and classifies each chunk into HIGH, MEDIUM, or LOW priority.
    """

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        weights: Optional[EvidencePriorityWeights] = None,
    ):
        self._embedder = embedding_model or EmbeddingModel()
        self.weights = weights or EvidencePriorityWeights()

    def rank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], PriorityMetrics]:
        """
        Produce a deterministic ranked list of prioritized chunks and metrics.
        """
        if not chunks:
            metrics = PriorityMetrics(
                priority_latency=0.0,
                high_priority_count=0,
                medium_priority_count=0,
                low_priority_count=0,
                active_evidence_count=0,
                retained_evidence_count=0,
                average_priority_score=0.0,
            )
            return [], metrics

        t0 = time.perf_counter()

        # Batch encode if semantic weighting is active
        compute_semantic = self.weights.semantic_weight > 0.0
        if compute_semantic:
            query_vec = self._embedder.embed(query)
            texts = [c.get("text", "") for c in chunks]
            valid_indices = [i for i, t in enumerate(texts) if t.strip()]
            valid_texts = [texts[i] for i in valid_indices]

            if valid_texts:
                batch_vecs = self._embedder.embed_batch(valid_texts)
                chunk_vec_map = {valid_indices[k]: batch_vecs[k] for k in range(len(valid_indices))}
            else:
                chunk_vec_map = {}
        else:
            query_vec = None
            chunk_vec_map = {}

        query_keywords = extract_keywords(query)

        prioritized = []
        high_cnt = 0
        med_cnt = 0
        low_cnt = 0
        total_score = 0.0

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")

            # 1. Semantic score calculation
            if compute_semantic and i in chunk_vec_map:
                semantic_score = cosine_similarity(query_vec, chunk_vec_map[i])
            else:
                semantic_score = 0.0

            # 2. Lexical score calculation
            if query_keywords and chunk_text.strip():
                chunk_keywords = extract_keywords(chunk_text)
                matched = query_keywords & chunk_keywords
                lexical_score = len(matched) / len(query_keywords)
            else:
                lexical_score = 0.0

            # 3. Reuse score calculation (S7 status check)
            is_reused = chunk.get("evidence_status") == "reused"
            reuse_score = 1.0 if is_reused else 0.0

            # 4. Combined deterministic priority score
            priority_score = (
                self.weights.semantic_weight * semantic_score
                + self.weights.lexical_weight * lexical_score
                + self.weights.reuse_weight * reuse_score
            )
            total_score += priority_score

            # Classify into Priority Classes based on thresholds
            if priority_score >= self.weights.high_threshold:
                p_class = PriorityClass.HIGH
                high_cnt += 1
            elif priority_score >= self.weights.medium_threshold:
                p_class = PriorityClass.MEDIUM
                med_cnt += 1
            else:
                p_class = PriorityClass.LOW
                low_cnt += 1

            p_chunk = PrioritizedEvidenceChunk(
                chunk=chunk,
                semantic_score=semantic_score,
                lexical_score=lexical_score,
                reuse_score=reuse_score,
                priority_score=priority_score,
                priority_class=p_class,
            )
            prioritized.append(p_chunk)

        # Sort descending by priority score
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)
        priority_latency = time.perf_counter() - t0

        avg_score = total_score / len(chunks) if chunks else 0.0

        # Mark state: HIGH is active by default (up to high_cnt), rest retained
        active_cnt = high_cnt if high_cnt > 0 else (1 if chunks else 0)
        retained_cnt = len(chunks) - active_cnt

        ranked_dict_chunks = []
        for j, p_chunk in enumerate(prioritized):
            if j < active_cnt:
                p_chunk.state = "active"
            else:
                p_chunk.state = "retained"
            ranked_dict_chunks.append(p_chunk.to_dict())

        metrics = PriorityMetrics(
            priority_latency=priority_latency,
            high_priority_count=high_cnt,
            medium_priority_count=med_cnt,
            low_priority_count=low_cnt,
            active_evidence_count=active_cnt,
            retained_evidence_count=retained_cnt,
            average_priority_score=avg_score,
        )

        logger.info(
            f"EvidencePriorityEngine: Ranked {len(chunks)} chunks -> "
            f"HIGH={high_cnt}, MED={med_cnt}, LOW={low_cnt}, "
            f"avg_score={avg_score:.4f}, latency={priority_latency:.6f}s"
        )

        return ranked_dict_chunks, metrics
