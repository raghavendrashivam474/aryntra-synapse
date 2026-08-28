"""
app/context/evidence_priority.py

Aryntra Synapse — Sprint 8 / Sprint 9
Evidence relevance and priority management engine with efficiency optimizations.

Responsibilities:
- Calculate individual priority signals (semantic, lexical, reuse)
- Support conditional semantic evaluation via lexical fast-path gating (S9)
- Support query and chunk embedding caching (S9)
- Compute deterministic unified priority score
- Classify evidence into HIGH, MEDIUM, LOW classes
- Route/partition evidence into active and retained states
- Zero LLM calls; completely deterministic
"""

import time
import logging
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional, Set
import numpy as np
from app.context.sufficiency import extract_keywords
from app.context.semantic_gate import cosine_similarity
from app.retrieval.embeddings import EmbeddingModel
from app.optimization.embedding_cache import EmbeddingCache, fingerprint_text
from app.optimization.semantic_gate import LexicalSemanticGate, FastPathDecision

logger = logging.getLogger(__name__)


class PriorityClass(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidencePriorityWeights:
    """Configurable weights and thresholds for S8/S9 Priority scoring."""

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
        # S9 Efficiency Telemetry
        semantic_calls: int = 0,
        semantic_cache_hits: int = 0,
        semantic_cache_misses: int = 0,
        query_cache_hits: int = 0,
        query_cache_misses: int = 0,
        lexical_fast_path_hits: int = 0,
        semantic_fallback_count: int = 0,
        semantic_latency: float = 0.0,
        cache_lookup_latency: float = 0.0,
    ):
        self.priority_latency = priority_latency
        self.high_priority_count = high_priority_count
        self.medium_priority_count = medium_priority_count
        self.low_priority_count = low_priority_count
        self.active_evidence_count = active_evidence_count
        self.retained_evidence_count = retained_evidence_count
        self.average_priority_score = average_priority_score
        self.semantic_calls = semantic_calls
        self.semantic_cache_hits = semantic_cache_hits
        self.semantic_cache_misses = semantic_cache_misses
        self.query_cache_hits = query_cache_hits
        self.query_cache_misses = query_cache_misses
        self.lexical_fast_path_hits = lexical_fast_path_hits
        self.semantic_fallback_count = semantic_fallback_count
        self.semantic_latency = semantic_latency
        self.cache_lookup_latency = cache_lookup_latency

    def to_dict(self) -> dict:
        return {
            "priority_latency": round(self.priority_latency, 6),
            "high_priority_count": self.high_priority_count,
            "medium_priority_count": self.medium_priority_count,
            "low_priority_count": self.low_priority_count,
            "active_evidence_count": self.active_evidence_count,
            "retained_evidence_count": self.retained_evidence_count,
            "average_priority_score": round(self.average_priority_score, 4),
            "semantic_calls": self.semantic_calls,
            "semantic_cache_hits": self.semantic_cache_hits,
            "semantic_cache_misses": self.semantic_cache_misses,
            "query_cache_hits": self.query_cache_hits,
            "query_cache_misses": self.query_cache_misses,
            "lexical_fast_path_hits": self.lexical_fast_path_hits,
            "semantic_fallback_count": self.semantic_fallback_count,
            "semantic_latency": round(self.semantic_latency, 6),
            "cache_lookup_latency": round(self.cache_lookup_latency, 6),
        }


class EvidencePriorityEngine:
    """
    S8 / S9 Evidence Priority Engine.

    Scores candidate evidence chunks using:
    - Semantic Similarity (via cosine similarity with query embedding)
    - Lexical Similarity (query keyword matching/overlap)
    - Reuse Value (S7 metadata indicating whether chunk was already processed)

    S9 Optimizations:
    - EmbeddingCache for query & chunk vector embeddings
    - LexicalSemanticGate for conditional semantic evaluation
    """

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        weights: Optional[EvidencePriorityWeights] = None,
        query_cache: Optional[EmbeddingCache] = None,
        evidence_cache: Optional[EmbeddingCache] = None,
        semantic_gate: Optional[LexicalSemanticGate] = None,
    ):
        self._embedder = embedding_model or EmbeddingModel()
        self.weights = weights or EvidencePriorityWeights()
        self.query_cache = query_cache
        self.evidence_cache = evidence_cache
        self.semantic_gate = semantic_gate

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
        sem_latency = 0.0
        cache_latency = 0.0
        semantic_calls = 0
        q_hits_start = self.query_cache.hits if self.query_cache else 0
        q_miss_start = self.query_cache.misses if self.query_cache else 0
        ev_hits_start = self.evidence_cache.hits if self.evidence_cache else 0
        ev_miss_start = self.evidence_cache.misses if self.evidence_cache else 0
        fast_path_hits_start = self.semantic_gate.fast_path_hits if self.semantic_gate else 0
        fallbacks_start = self.semantic_gate.semantic_fallbacks if self.semantic_gate else 0

        query_keywords = extract_keywords(query)
        compute_semantic = self.weights.semantic_weight > 0.0

        # Step 1: Pre-filter chunks using LexicalSemanticGate (if enabled)
        gate_decisions: Dict[int, FastPathDecision] = {}
        chunks_requiring_semantic: List[Tuple[int, str]] = []

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")
            if not chunk_text.strip():
                continue

            if compute_semantic:
                if self.semantic_gate:
                    decision = self.semantic_gate.decide(query_keywords, chunk_text)
                    gate_decisions[i] = decision
                    if decision.needs_semantic:
                        chunks_requiring_semantic.append((i, chunk_text))
                else:
                    chunks_requiring_semantic.append((i, chunk_text))

        # Step 2: Resolve Query Embedding (if any chunks require semantic scoring)
        query_vec: Optional[np.ndarray] = None
        if compute_semantic and chunks_requiring_semantic:
            t_sem_0 = time.perf_counter()
            if self.query_cache is not None:
                t_c0 = time.perf_counter()
                query_vec = self.query_cache.get_or_compute(query, self._embedder.embed)
                cache_latency += (time.perf_counter() - t_c0)
            else:
                query_vec = self._embedder.embed(query)
                semantic_calls += 1
            sem_latency += (time.perf_counter() - t_sem_0)

        # Step 3: Resolve Chunk Embeddings (only for chunks requiring semantic scoring)
        chunk_vec_map: Dict[int, np.ndarray] = {}
        if compute_semantic and chunks_requiring_semantic and query_vec is not None:
            indices_to_fetch = [idx for idx, _ in chunks_requiring_semantic]
            texts_to_fetch = [txt for _, txt in chunks_requiring_semantic]

            t_sem_1 = time.perf_counter()
            if self.evidence_cache is not None:
                t_c1 = time.perf_counter()
                fingerprints = [
                    chunks[idx].get("fingerprint") or fingerprint_text(texts_to_fetch[k])
                    for k, idx in enumerate(indices_to_fetch)
                ]
                vectors = self.evidence_cache.get_or_compute_batch(
                    texts=texts_to_fetch,
                    compute_batch_fn=self._embedder.embed_batch,
                    precomputed_keys=fingerprints,
                )
                cache_latency += (time.perf_counter() - t_c1)
                for idx, vec in zip(indices_to_fetch, vectors):
                    chunk_vec_map[idx] = vec
            else:
                batch_vecs = self._embedder.embed_batch(texts_to_fetch)
                semantic_calls += len(texts_to_fetch)
                for k, idx in enumerate(indices_to_fetch):
                    chunk_vec_map[idx] = batch_vecs[k]

            sem_latency += (time.perf_counter() - t_sem_1)

        # Step 4: Scoring and Classification
        prioritized = []
        high_cnt = 0
        med_cnt = 0
        low_cnt = 0
        total_score = 0.0

        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")

            # 1. Semantic score calculation
            if compute_semantic:
                if i in chunk_vec_map and query_vec is not None:
                    semantic_score = float(cosine_similarity(query_vec, chunk_vec_map[i]))
                elif i in gate_decisions and not gate_decisions[i].needs_semantic:
                    semantic_score = float(gate_decisions[i].suggested_semantic_score or 0.0)
                else:
                    semantic_score = 0.0
            else:
                semantic_score = 0.0

            # 2. Lexical score calculation
            if i in gate_decisions:
                lexical_score = float(gate_decisions[i].lexical_score)
            elif query_keywords and chunk_text.strip():
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
                state="retained",
            )
            prioritized.append(p_chunk)

        # Sort descending by priority score
        prioritized.sort(key=lambda x: x.priority_score, reverse=True)

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

        total_latency = time.perf_counter() - t0
        avg_score = total_score / len(prioritized) if prioritized else 0.0

        # Calculate delta telemetry
        q_hits = (self.query_cache.hits - q_hits_start) if self.query_cache else 0
        q_miss = (self.query_cache.misses - q_miss_start) if self.query_cache else 0
        ev_hits = (self.evidence_cache.hits - ev_hits_start) if self.evidence_cache else 0
        ev_miss = (self.evidence_cache.misses - ev_miss_start) if self.evidence_cache else 0
        fast_path = (self.semantic_gate.fast_path_hits - fast_path_hits_start) if self.semantic_gate else 0
        fallbacks = (self.semantic_gate.semantic_fallbacks - fallbacks_start) if self.semantic_gate else 0

        metrics = PriorityMetrics(
            priority_latency=total_latency,
            high_priority_count=high_cnt,
            medium_priority_count=med_cnt,
            low_priority_count=low_cnt,
            active_evidence_count=active_cnt,
            retained_evidence_count=retained_cnt,
            average_priority_score=avg_score,
            semantic_calls=semantic_calls,
            semantic_cache_hits=ev_hits,
            semantic_cache_misses=ev_miss,
            query_cache_hits=q_hits,
            query_cache_misses=q_miss,
            lexical_fast_path_hits=fast_path,
            semantic_fallback_count=fallbacks,
            semantic_latency=sem_latency,
            cache_lookup_latency=cache_latency,
        )

        logger.info(
            f"EvidencePriorityEngine: Ranked {len(chunks)} chunks -> "
            f"HIGH={high_cnt}, MEDIUM={med_cnt}, LOW={low_cnt} "
            f"[Active={active_cnt}, Retained={retained_cnt}] "
            f"in {total_latency*1000:.3f}ms"
        )

        return ranked_dict_chunks, metrics
