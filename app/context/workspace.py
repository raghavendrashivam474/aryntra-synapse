import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.context.compressor import build_compressed_context

logger = logging.getLogger(__name__)


class PromotionEvent:
    """Immutable record of a single evidence promotion."""

    def __init__(
        self,
        chunk_id: str,
        stage: int,
        reason: str,
        previous_active_count: int,
        new_active_count: int,
        new_context_length: int,
        repeated_context_length: int,
        latency: float = 0.0,
    ):
        self.chunk_id = chunk_id
        self.stage = stage
        self.reason = reason
        self.previous_active_count = previous_active_count
        self.new_active_count = new_active_count
        self.new_context_length = new_context_length
        self.repeated_context_length = repeated_context_length
        self.latency = latency

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "stage": self.stage,
            "reason": self.reason,
            "previous_active_count": self.previous_active_count,
            "new_active_count": self.new_active_count,
            "new_context_length": self.new_context_length,
            "repeated_context_length": self.repeated_context_length,
            "latency": self.latency,
        }


class EvidenceWorkspace:
    """
    Per-query stateful evidence store.

    Classifies retrieved chunks as ACTIVE (in the current LLM prompt)
    or AVAILABLE (retained but not yet promoted). Tracks promotion
    history and provides new-vs-repeated context accounting.

    Lifecycle: created per query, discarded after generation.
    No cross-query state is maintained.
    """

    def __init__(
        self,
        chunks: List[Dict[str, Any]],
        max_active: int = 3,
        max_chunk_chars: int = 400,
        dedup_threshold: float = 0.90,
    ):
        self._all_chunks = list(chunks)
        self._chunk_map = {c["chunk_id"]: c for c in chunks}
        self._active_ids: List[str] = []
        self._available_ids: List[str] = [c["chunk_id"] for c in chunks]
        self._promotion_history: List[PromotionEvent] = []
        self._max_active = max_active
        self._max_chunk_chars = max_chunk_chars
        self._dedup_threshold = dedup_threshold

        # Track what context was introduced at each stage
        self._stage_new_context: Dict[int, int] = {}
        self._stage_repeated_context: Dict[int, int] = {}

    # ── State queries ──

    def active(self) -> List[Dict[str, Any]]:
        return [self._chunk_map[cid] for cid in self._active_ids]

    def available(self) -> List[Dict[str, Any]]:
        return [self._chunk_map[cid] for cid in self._available_ids]

    def has_available(self) -> bool:
        return len(self._available_ids) > 0 and len(self._active_ids) < self._max_active

    def is_active(self, chunk_id: str) -> bool:
        return chunk_id in self._active_ids

    @property
    def active_count(self) -> int:
        return len(self._active_ids)

    @property
    def available_count(self) -> int:
        return len(self._available_ids)

    @property
    def promotion_history(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._promotion_history]

    # ── Context construction ──

    def build_active_context(self) -> str:
        """Compress and format all currently active chunks."""
        return build_compressed_context(
            chunks=self.active(),
            max_chunk_chars=self._max_chunk_chars,
            dedup_threshold=self._dedup_threshold,
        )

    def build_delta_context(self, chunk_id: str) -> str:
        """Build context string for a single newly promoted chunk."""
        chunk = self._chunk_map.get(chunk_id)
        if not chunk:
            return ""
        return build_compressed_context(
            chunks=[chunk],
            max_chunk_chars=self._max_chunk_chars,
            dedup_threshold=self._dedup_threshold,
        )

    # ── Promotion ──

    def promote_next(self, reason: str = "insufficient_evidence") -> Optional[PromotionEvent]:
        """
        Promote the highest-ranked available chunk to active.
        Returns the PromotionEvent or None if no promotion is possible.
        """
        if not self.has_available():
            return None

        t0 = time.perf_counter()
        chunk_id = self._available_ids.pop(0)
        previous_count = len(self._active_ids)
        self._active_ids.append(chunk_id)
        new_count = len(self._active_ids)

        # Calculate new vs repeated context
        delta_ctx = self.build_delta_context(chunk_id)
        new_ctx_len = len(delta_ctx)

        # Repeated context = all previously active chunks
        if previous_count > 0:
            prev_active = [self._chunk_map[cid] for cid in self._active_ids[:-1]]
            repeated_ctx = build_compressed_context(
                chunks=prev_active,
                max_chunk_chars=self._max_chunk_chars,
                dedup_threshold=self._dedup_threshold,
            )
            repeated_ctx_len = len(repeated_ctx)
        else:
            repeated_ctx_len = 0

        stage = len(self._promotion_history) + 1
        latency = round(time.perf_counter() - t0, 6)

        event = PromotionEvent(
            chunk_id=chunk_id,
            stage=stage,
            reason=reason,
            previous_active_count=previous_count,
            new_active_count=new_count,
            new_context_length=new_ctx_len,
            repeated_context_length=repeated_ctx_len,
            latency=latency,
        )
        self._promotion_history.append(event)
        self._stage_new_context[stage] = new_ctx_len
        self._stage_repeated_context[stage] = repeated_ctx_len

        logger.info(
            f"Workspace promotion: {chunk_id} "
            f"(stage={stage}, active={new_count}, "
            f"new={new_ctx_len}, repeated={repeated_ctx_len})"
        )
        return event

    def promote_initial(self, count: int = 1) -> List[PromotionEvent]:
        """Promote the first N chunks as the initial active set."""
        events = []
        for _ in range(min(count, len(self._available_ids))):
            event = self.promote_next(reason="initial_exposure")
            if event:
                events.append(event)
        return events

    def promote_priority_initial(self, fallback_count: int = 1) -> List[PromotionEvent]:
        """
        S8 Priority Initial Promotion:
        Promotes all HIGH priority chunks (up to max_active).
        If no chunks are HIGH priority, promotes fallback_count chunks.
        """
        high_ids = [
            cid for cid in self._available_ids
            if self._chunk_map[cid].get("priority_class") == "HIGH"
        ]
        promote_count = len(high_ids) if high_ids else fallback_count
        promote_count = min(promote_count, self._max_active)

        events = []
        for _ in range(min(promote_count, len(self._available_ids))):
            event = self.promote_next(reason="priority_high_initial")
            if event:
                events.append(event)
        return events

    # ── Accounting ──

    def total_new_context(self) -> int:
        return sum(self._stage_new_context.values())

    def total_repeated_context(self) -> int:
        return sum(self._stage_repeated_context.values())

    def summary(self) -> Dict[str, Any]:
        return {
            "total_chunks": len(self._all_chunks),
            "active_chunks": self.active_count,
            "available_chunks": self.available_count,
            "promotion_count": len(self._promotion_history),
            "total_new_context": self.total_new_context(),
            "total_repeated_context": self.total_repeated_context(),
            "promotion_history": self.promotion_history,
        }
