import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "which", "have",
    "been", "were", "when", "where", "what", "into", "more", "some", "used",
    "will", "first", "also", "than", "only", "does", "each", "other", "their",
    "about", "how", "who", "why", "are", "can", "may", "was", "its", "not",
    "but", "has", "had", "his", "her", "they", "them", "would", "could",
    "should", "there", "these", "those", "is", "it", "an", "or", "in", "on",
    "at", "to", "of", "a", "by", "do", "if", "no", "so", "up", "as",
}


def extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text, excluding stopwords."""
    tokens = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


class SufficiencyResult:
    """Immutable record of a sufficiency evaluation."""

    def __init__(
        self,
        is_sufficient: bool,
        reason: str,
        top_score: float,
        coverage_ratio: float,
        query_keywords: int,
        matched_keywords: int,
    ):
        self.is_sufficient = is_sufficient
        self.reason = reason
        self.top_score = top_score
        self.coverage_ratio = coverage_ratio
        self.query_keywords = query_keywords
        self.matched_keywords = matched_keywords

    def to_dict(self) -> dict:
        return {
            "is_sufficient": self.is_sufficient,
            "reason": self.reason,
            "top_score": self.top_score,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "query_keywords": self.query_keywords,
            "matched_keywords": self.matched_keywords,
        }


class SufficiencyEngine:
    """
    Lightweight deterministic sufficiency assessment.

    Uses two signals:
    1. Retrieval score threshold (is the top chunk relevant enough?)
    2. Keyword coverage (does the evidence cover the query concepts?)

    Both must be satisfied for sufficiency to be declared.
    This mechanism requires zero LLM calls.
    """

    def __init__(
        self,
        score_threshold: float = 0.45,
        coverage_threshold: float = 0.25,
    ):
        self.score_threshold = score_threshold
        self.coverage_threshold = coverage_threshold

    def evaluate(
        self,
        query: str,
        active_chunks: List[Dict[str, Any]],
    ) -> SufficiencyResult:
        """
        Evaluate whether the active evidence is sufficient for the query.

        Returns a SufficiencyResult with the decision and supporting metrics.
        """
        if not active_chunks:
            return SufficiencyResult(
                is_sufficient=False,
                reason="no_active_evidence",
                top_score=0.0,
                coverage_ratio=0.0,
                query_keywords=0,
                matched_keywords=0,
            )

        # Signal A: Retrieval score of top-ranked active chunk
        top_score = active_chunks[0].get("score", 0.0)
        score_pass = top_score >= self.score_threshold

        # Signal B: Keyword coverage
        query_kw = extract_keywords(query)
        if not query_kw:
            # If query has no extractable keywords, defer to score only
            coverage_ratio = 1.0 if score_pass else 0.0
            coverage_pass = score_pass
        else:
            evidence_text = " ".join(c.get("text", "") for c in active_chunks)
            evidence_kw = extract_keywords(evidence_text)
            matched = query_kw & evidence_kw
            coverage_ratio = len(matched) / len(query_kw)
            coverage_pass = coverage_ratio >= self.coverage_threshold

        # Combined decision
        is_sufficient = score_pass and coverage_pass

        if is_sufficient:
            reason = "score_and_coverage_sufficient"
        elif not score_pass and not coverage_pass:
            reason = "score_and_coverage_insufficient"
        elif not score_pass:
            reason = "score_insufficient"
        else:
            reason = "coverage_insufficient"

        result = SufficiencyResult(
            is_sufficient=is_sufficient,
            reason=reason,
            top_score=top_score,
            coverage_ratio=coverage_ratio,
            query_keywords=len(query_kw),
            matched_keywords=len(query_kw & extract_keywords(
                " ".join(c.get("text", "") for c in active_chunks)
            )) if query_kw else 0,
        )

        logger.info(
            f"Sufficiency: {result.reason} "
            f"(score={top_score:.3f}, coverage={coverage_ratio:.2f})"
        )
        return result