"""
app/optimization/semantic_gate.py

Aryntra Synapse — Sprint 9
Cheap lexical pre-filter. Decides whether expensive semantic scoring is needed.
The gate never assigns semantic truth on its own — it routes whether
semantic computation is required.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Set, Dict, Any, Optional, Union
from app.context.sufficiency import extract_keywords


@dataclass(frozen=True)
class FastPathDecision:
    needs_semantic: bool
    lexical_score: float
    reason: str
    suggested_semantic_score: Optional[float] = None


# Alias for backward compatibility
GateDecision = FastPathDecision


class LexicalSemanticGate:
    """
    Lexical gate evaluating keyword overlap between query and evidence chunk.

    - high_confidence: Keyword overlap is strong enough that chunk is already
      clearly relevant; semantic computation would not change the priority decision.
    - low_confidence: Keyword overlap is zero/negligible; chunk can be filtered
      or assigned low priority without semantic computation.
    - between: Lexical evidence is ambiguous, semantic check is required.
    """

    def __init__(
        self,
        high_confidence: float = 0.60,
        low_confidence: float = 0.05,
    ):
        assert 0.0 <= low_confidence < high_confidence <= 1.0
        self.high_confidence = high_confidence
        self.low_confidence = low_confidence
        self.fast_path_hits = 0
        self.semantic_fallbacks = 0

    def compute_lexical_score(self, query: Union[str, Set[str]], chunk_text: str) -> float:
        if not query or not chunk_text.strip():
            return 0.0
        query_keywords = extract_keywords(query) if isinstance(query, str) else query
        if not query_keywords:
            return 0.0
        chunk_keywords = extract_keywords(chunk_text)
        if not chunk_keywords:
            return 0.0
        matched = query_keywords & chunk_keywords
        return len(matched) / len(query_keywords)

    def decide(
        self,
        query: Union[str, Set[str]],
        chunk_text: str,
    ) -> FastPathDecision:
        score = self.compute_lexical_score(query, chunk_text)

        if score >= self.high_confidence:
            self.fast_path_hits += 1
            return FastPathDecision(
                needs_semantic=False,
                lexical_score=score,
                reason="lexical_high_confidence",
                suggested_semantic_score=score,
            )

        if score <= self.low_confidence:
            self.fast_path_hits += 1
            return FastPathDecision(
                needs_semantic=False,
                lexical_score=score,
                reason="lexical_low_confidence",
                suggested_semantic_score=0.0,
            )

        self.semantic_fallbacks += 1
        return FastPathDecision(
            needs_semantic=True,
            lexical_score=score,
            reason="ambiguous_needs_semantic",
            suggested_semantic_score=None,
        )

    def score(self, query: Union[str, Set[str]], chunk_text: str) -> float:
        return self.compute_lexical_score(query, chunk_text)

    def stats(self) -> Dict[str, Any]:
        total = self.fast_path_hits + self.semantic_fallbacks
        return {
            "fast_path_hits": self.fast_path_hits,
            "semantic_fallbacks": self.semantic_fallbacks,
            "fast_path_rate": round(self.fast_path_hits / total, 4) if total > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        self.fast_path_hits = 0
        self.semantic_fallbacks = 0


# Backward-compatible alias
SemanticGate = LexicalSemanticGate
