"""
app/context/evidence_store.py

Aryntra Synapse — Sprint 7
Cross-query persistent evidence store with fingerprint-based deduplication.

Responsibilities:
- Maintain a fingerprint -> evidence mapping across queries
- Classify incoming evidence as NEW or REUSED
- Track reuse metrics per batch
- Zero LLM calls; purely deterministic

This store lives at the application level (not per-query).
It is the mechanism by which Synapse answers:
"I already have this evidence."

It does NOT decide sufficiency (S5/S6) or promotion (S4/S8).
"""

import time
import logging
from typing import List, Dict, Any, Tuple

from app.retrieval.evidence_fingerprint import EvidenceFingerprint

logger = logging.getLogger(__name__)


class ReuseMetrics:
    """Immutable record of evidence reuse for a single retrieval batch."""

    def __init__(
        self,
        total_candidates: int,
        unique_candidates: int,
        reused_count: int,
        new_count: int,
        reuse_rate: float,
        fingerprinting_latency: float,
        lookup_latency: float,
    ):
        self.total_candidates = total_candidates
        self.unique_candidates = unique_candidates
        self.reused_count = reused_count
        self.new_count = new_count
        self.reuse_rate = reuse_rate
        self.fingerprinting_latency = fingerprinting_latency
        self.lookup_latency = lookup_latency

    def to_dict(self) -> dict:
        return {
            "total_candidates": self.total_candidates,
            "unique_candidates": self.unique_candidates,
            "reused_count": self.reused_count,
            "new_count": self.new_count,
            "reuse_rate": round(self.reuse_rate, 4),
            "fingerprinting_latency": round(self.fingerprinting_latency, 6),
            "lookup_latency": round(self.lookup_latency, 6),
        }


class EvidenceStore:
    """
    Cross-query persistent evidence store.

    Maintains a fingerprint -> evidence mapping. When new evidence arrives,
    it is fingerprinted and checked against the store. Reused evidence is
    recognized but still passed downstream (reuse != sufficiency).
    """

    def __init__(self, fingerprinter: EvidenceFingerprint = None):
        self._fingerprinter = fingerprinter or EvidenceFingerprint()
        self._store: Dict[str, Dict[str, Any]] = {}
        self._total_processed = 0
        self._total_reused = 0

    def process(
        self, chunks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], ReuseMetrics]:
        """
        Process a batch of retrieved chunks.

        For each chunk:
        1. Compute fingerprint
        2. Check if fingerprint exists in store
        3. If new: add to store
        4. If reused: mark as reused
        5. Pass ALL chunks downstream (unchanged except for metadata)

        Returns
        -------
        tagged_chunks : list with 'fingerprint' and 'evidence_status' keys added
        metrics : ReuseMetrics for this batch
        """
        if not chunks:
            return [], ReuseMetrics(
                total_candidates=0,
                unique_candidates=0,
                reused_count=0,
                new_count=0,
                reuse_rate=0.0,
                fingerprinting_latency=0.0,
                lookup_latency=0.0,
            )

        # Phase 1: Fingerprinting
        t_fp_start = time.perf_counter()
        tagged = self._fingerprinter.tag_chunks(chunks)
        fp_latency = time.perf_counter() - t_fp_start

        # Phase 2: Lookup and classification
        t_lookup_start = time.perf_counter()
        reused_count = 0
        new_count = 0
        unique_fps = set()

        for chunk in tagged:
            fp = chunk["fingerprint"]
            unique_fps.add(fp)

            if fp in self._store:
                chunk["evidence_status"] = "reused"
                reused_count += 1
            else:
                chunk["evidence_status"] = "new"
                self._store[fp] = {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "text": chunk.get("text", ""),
                    "first_seen_score": chunk.get("score", 0.0),
                }
                new_count += 1

        lookup_latency = time.perf_counter() - t_lookup_start

        total = len(chunks)
        reuse_rate = reused_count / total if total > 0 else 0.0

        self._total_processed += total
        self._total_reused += reused_count

        metrics = ReuseMetrics(
            total_candidates=total,
            unique_candidates=len(unique_fps),
            reused_count=reused_count,
            new_count=new_count,
            reuse_rate=reuse_rate,
            fingerprinting_latency=fp_latency,
            lookup_latency=lookup_latency,
        )

        logger.info(
            f"EvidenceStore: {total} candidates, "
            f"{reused_count} reused, {new_count} new "
            f"(rate={reuse_rate:.2%}, fp={fp_latency:.6f}s, "
            f"lookup={lookup_latency:.6f}s)"
        )

        return tagged, metrics

    def lookup(self, fingerprint: str) -> Dict[str, Any]:
        """Look up evidence by fingerprint. Returns empty dict if not found."""
        return self._store.get(fingerprint, {})

    def has(self, fingerprint: str) -> bool:
        """Check if a fingerprint exists in the store."""
        return fingerprint in self._store

    def clear(self) -> None:
        """Clear all stored evidence."""
        self._store.clear()
        self._total_processed = 0
        self._total_reused = 0

    @property
    def size(self) -> int:
        """Number of unique evidence items in the store."""
        return len(self._store)

    @property
    def cumulative_stats(self) -> Dict[str, Any]:
        return {
            "store_size": self.size,
            "total_processed": self._total_processed,
            "total_reused": self._total_reused,
            "cumulative_reuse_rate": (
                self._total_reused / self._total_processed
                if self._total_processed > 0
                else 0.0
            ),
        }
