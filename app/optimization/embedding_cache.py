"""
app/optimization/embedding_cache.py

Aryntra Synapse — Sprint 9
Deterministic, bounded, fingerprint-keyed cache for evidence and query embeddings.
Non-destructive. Transparent to S6/S7/S8.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from typing import Any

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

    def get(self, key: str) -> np.ndarray | None:
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
        precomputed_key: str | None = None,
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
        texts: list[str],
        compute_batch_fn: Callable[[list[str]], np.ndarray],
        precomputed_keys: list[str] | None = None,
    ) -> list[np.ndarray]:
        if not texts:
            return []

        keys = precomputed_keys or [fingerprint_text(t) for t in texts]
        results: list[np.ndarray | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

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
                for orig_idx, vec in zip(missing_indices, computed_vectors, strict=False):
                    key = keys[orig_idx]
                    self._store[key] = vec
                    self._store.move_to_end(key)
                    if len(self._store) > self._max:
                        self._store.popitem(last=False)
                    results[orig_idx] = vec

        return [r for r in results if r is not None]

    def stats(self) -> dict[str, Any]:
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
