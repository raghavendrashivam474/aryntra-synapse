"""
Aryntra Synapse — Sprint 12: Confidence Guard & Fallback Routing

Determines whether priority-based processing is trustworthy
for a given query/evidence combination. Falls back to broader
context when confidence is low.

Signals evaluated (all cheap, no embeddings or LLM):
- Priority score margin (top-1 vs top-2)
- HIGH priority count
- Lexical agreement with top chunk
- Corpus size
- Average priority score
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class FallbackDecision(str, Enum):
    TRUST_PRIORITY = "trust_priority"
    FALLBACK_BROAD = "fallback_broad"
    FALLBACK_SKIP = "fallback_skip"


@dataclass
class ConfidenceAssessment:
    decision: FallbackDecision
    confidence_score: float
    reason: str
    signals: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "confidence_score": round(self.confidence_score, 4),
            "reason": self.reason,
            "signals": self.signals,
        }


class ConfidenceGuard:
    """
    S12 Confidence Guard.

    Evaluates priority output trustworthiness using cheap signals.
    Does NOT require additional embedding calls or LLM invocations.
    """

    def __init__(
        self,
        min_score_margin: float = 0.15,
        min_high_count: int = 1,
        min_lexical_agreement: float = 0.10,
        small_corpus_threshold: int = 5,
    ):
        self.min_score_margin = min_score_margin
        self.min_high_count = min_high_count
        self.min_lexical_agreement = min_lexical_agreement
        self.small_corpus_threshold = small_corpus_threshold

    def assess(
        self,
        query: str,
        ranked_chunks: List[Dict[str, Any]],
        priority_metrics: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceAssessment:
        """Evaluate whether to trust priority results or fall back."""
        signals: Dict[str, Any] = {}
        reasons: List[str] = []
        confidence = 0.50  # neutral baseline

        if not ranked_chunks:
            return ConfidenceAssessment(
                decision=FallbackDecision.FALLBACK_BROAD,
                confidence_score=0.0,
                reason="no_chunks_available",
                signals={},
            )

        # Signal 1: Score margin between top-1 and top-2
        scores = [c.get("priority_score", 0.0) for c in ranked_chunks]
        if len(scores) >= 2:
            margin = scores[0] - scores[1]
            signals["score_margin"] = round(margin, 4)
            if margin >= self.min_score_margin:
                confidence += 0.15
            elif margin < 0.05:
                confidence -= 0.15
                reasons.append("low_score_margin")
        else:
            signals["score_margin"] = 0.0

        # Signal 2: HIGH priority count
        high_count = sum(
            1 for c in ranked_chunks if c.get("priority_class") == "HIGH"
        )
        signals["high_count"] = high_count
        if high_count >= self.min_high_count:
            confidence += 0.10
        else:
            confidence -= 0.10
            reasons.append("no_high_priority")

        # Signal 3: Lexical agreement with top chunk
        try:
            from app.context.sufficiency import extract_keywords
            query_kw = extract_keywords(query)
            if query_kw and ranked_chunks:
                top_text = ranked_chunks[0].get("text", "")
                top_kw = extract_keywords(top_text)
                if top_kw:
                    agreement = len(query_kw & top_kw) / len(query_kw)
                    signals["lexical_agreement"] = round(agreement, 4)
                    if agreement >= self.min_lexical_agreement:
                        confidence += 0.10
                    else:
                        confidence -= 0.10
                        reasons.append("low_lexical_agreement")
        except ImportError:
            pass

        # Signal 4: Corpus size
        corpus_size = len(ranked_chunks)
        signals["corpus_size"] = corpus_size
        if corpus_size <= self.small_corpus_threshold:
            confidence -= 0.10
            reasons.append("tiny_corpus")
        elif corpus_size >= 20:
            confidence += 0.05

        # Signal 5: Average priority score
        avg_score = sum(scores) / len(scores) if scores else 0.0
        signals["avg_priority_score"] = round(avg_score, 4)
        if avg_score < 0.15:
            confidence -= 0.10
            reasons.append("low_avg_score")

        confidence = max(0.0, min(1.0, confidence))

        if confidence >= 0.55:
            decision = FallbackDecision.TRUST_PRIORITY
        elif confidence >= 0.35:
            decision = FallbackDecision.FALLBACK_BROAD
        else:
            decision = FallbackDecision.FALLBACK_SKIP

        reason_str = ";".join(reasons) if reasons else "confident"

        logger.debug(
            "ConfidenceGuard: %.2f -> %s (%s)",
            confidence, decision.value, reason_str,
        )

        return ConfidenceAssessment(
            decision=decision,
            confidence_score=confidence,
            reason=reason_str,
            signals=signals,
        )
