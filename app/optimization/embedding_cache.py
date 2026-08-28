"""
app/optimization/embedding_cache.py

Aryntra Synapse — Sprint 9
Deterministic, bounded, fingerprint-keyed cache for evidence and query embeddings.
Non-destructive. Transparent to S6/S7/S8.
"""
from __future__ import annotations
from collections import OrderedDict
from threading import Lock
from typing import Callable, Optional, Dict, Any, List
import hashlib
import numpy as np


def fingerprint_text(text: str) -> str:
    """Deterministic SHA-256 fingerprint for arbitrary text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


# Backward-compatible alias
_fingerprint = fingerprint_text


class EmbeddingCache:
    """
    LRU Embedding Cache for vector embeddings.
    Thread-safe, bounded, measurable.
    """

    def __init__(self, max_entries: int = 4096):
        self._store: OrderedDict[str, np.ndarray] = OrderedDict()
        self._max = max_entries
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[np.ndarray]:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self.hits += 1
                return self._store[key]
            self.misses += 1
            return None

    def put(self, key: str, vector: np.ndarray) -> None:
        with self._lock:
            self._store[key] = vector
            self._store.move_to_end(key)
            if len(self._store) > self._max:
                self._store.popitem(last=False)

    def get_or_compute(
        self,
        text: str,
        compute_fn: Callable[[str], np.ndarray],
        precomputed_key: Optional[str] = None,
    ) -> np.ndarray:
        key = precomputed_key or fingerprint_text(text)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self.hits += 1
                return self._store[key]

        # Compute outside lock
        vector = compute_fn(text)

        with self._lock:
            self._store[key] = vector
            self._store.move_to_end(key)
            if len(self._store) > self._max:
                self._store.popitem(last=False)
            self.misses += 1

        return vector

    def get_or_compute_batch(
        self,
        texts: List[str],
        compute_batch_fn: Callable[[List[str]], np.ndarray],
        precomputed_keys: Optional[List[str]] = None,
    ) -> List[np.ndarray]:
        if not texts:
            return []

        keys = precomputed_keys or [fingerprint_text(t) for t in texts]
        results: List[Optional[np.ndarray]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        with self._lock:
            for idx, key in enumerate(keys):
                if key in self._store:
                    self._store.move_to_end(key)
                    self.hits += 1
                    results[idx] = self._store[key]
                else:
                    self.misses += 1
                    missing_indices.append(idx)
                    missing_texts.append(texts[idx])

        if missing_texts:
            computed_vectors = compute_batch_fn(missing_texts)
            with self._lock:
                for orig_idx, vec in zip(missing_indices, computed_vectors):
                    key = keys[orig_idx]
                    self._store[key] = vec
                    self._store.move_to_end(key)
                    if len(self._store) > self._max:
                        self._store.popitem(last=False)
                    results[orig_idx] = vec

        return [r for r in results if r is not None]

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total > 0 else 0.0,
            "size": len(self._store),
            "max_size": self._max,
        }

    def reset_stats(self) -> None:
        with self._lock:
            self.hits = 0
            self.misses = 0

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0
