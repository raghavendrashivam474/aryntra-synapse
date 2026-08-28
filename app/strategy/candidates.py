"""
S10 - Five candidate strategy implementations.

Each candidate is a pure function: signals -> StrategyDecision.
No side effects, no mutable state, fully deterministic.

Candidate A: Lexical Complexity Gate
Candidate B: Cache Warmth Router
Candidate C: Reuse Confidence Router
Candidate D: Priority Pre-screener
Candidate E: Composite Score Router
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any


class StrategyPath(str, Enum):
    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class StrategyDecision:
    path: StrategyPath
    candidate: str
    reason: str
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "selected_strategy": self.path.value,
            "candidate": self.candidate,
            "reason": self.reason,
            "signals": self.signals,
        }


def candidate_a_lexical_complexity(signals: Dict[str, Any]) -> StrategyDecision:
    q_len = signals.get("query_length", 0)
    kw_count = signals.get("query_keyword_count", 0)

    if q_len <= 4 and kw_count <= 3:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="A",
            reason=f"simple_query(len={q_len},kw={kw_count})",
            signals=signals,
        )
    if q_len >= 10 or kw_count >= 7:
        return StrategyDecision(
            path=StrategyPath.DEEP,
            candidate="A",
            reason=f"complex_query(len={q_len},kw={kw_count})",
            signals=signals,
        )
    return StrategyDecision(
        path=StrategyPath.STANDARD,
        candidate="A",
        reason=f"moderate_query(len={q_len},kw={kw_count})",
        signals=signals,
    )


def candidate_b_cache_warmth(signals: Dict[str, Any]) -> StrategyDecision:
    hit_rate = signals.get("cache_hit_rate", 0.0)
    chunk_count = signals.get("chunk_count", 0)

    if hit_rate >= 0.8:
        return StrategyDecision(
            path=StrategyPath.STANDARD,
            candidate="B",
            reason=f"warm_cache_cheap(hit_rate={hit_rate:.2f})",
            signals=signals,
        )
    if hit_rate < 0.3 and chunk_count > 3:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="B",
            reason=f"cold_cache_expensive(hit_rate={hit_rate:.2f},chunks={chunk_count})",
            signals=signals,
        )
    return StrategyDecision(
        path=StrategyPath.STANDARD,
        candidate="B",
        reason=f"moderate_cache(hit_rate={hit_rate:.2f})",
        signals=signals,
    )


def candidate_c_reuse_confidence(signals: Dict[str, Any]) -> StrategyDecision:
    reuse_rate = signals.get("reuse_rate", 0.0)
    chunk_count = signals.get("chunk_count", 0)

    if reuse_rate >= 0.8:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="C",
            reason=f"high_reuse_skip_rerank(rate={reuse_rate:.2f})",
            signals=signals,
        )
    if reuse_rate < 0.2 and chunk_count >= 3:
        return StrategyDecision(
            path=StrategyPath.STANDARD,
            candidate="C",
            reason=f"novel_evidence_full_rank(rate={reuse_rate:.2f})",
            signals=signals,
        )
    return StrategyDecision(
        path=StrategyPath.STANDARD,
        candidate="C",
        reason=f"mixed_reuse(rate={reuse_rate:.2f})",
        signals=signals,
    )


def candidate_d_priority_prescreen(signals: Dict[str, Any]) -> StrategyDecision:
    lexical = signals.get("first_chunk_lexical_overlap", 0.0)
    avg_lex = signals.get("avg_lexical_overlap", 0.0)
    chunk_count = signals.get("chunk_count", 0)

    if lexical >= 0.6 and chunk_count <= 3:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="D",
            reason=f"clear_relevance(lex={lexical:.2f},chunks={chunk_count})",
            signals=signals,
        )
    if lexical <= 0.05 and avg_lex <= 0.05:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="D",
            reason=f"clear_irrelevance(lex={lexical:.2f},avg={avg_lex:.2f})",
            signals=signals,
        )
    if 0.15 <= lexical <= 0.45 and chunk_count > 3:
        return StrategyDecision(
            path=StrategyPath.DEEP,
            candidate="D",
            reason=f"ambiguous_needs_semantic(lex={lexical:.2f},chunks={chunk_count})",
            signals=signals,
        )
    return StrategyDecision(
        path=StrategyPath.STANDARD,
        candidate="D",
        reason=f"moderate_lexical(lex={lexical:.2f})",
        signals=signals,
    )


def candidate_e_composite(signals: Dict[str, Any]) -> StrategyDecision:
    q_complexity = min(signals.get("query_length", 0) / 15.0, 1.0)
    kw_complexity = min(signals.get("query_keyword_count", 0) / 10.0, 1.0)
    cache_warmth = signals.get("cache_hit_rate", 0.0)
    reuse_confidence = signals.get("reuse_rate", 0.0)
    lexical_clarity = signals.get("first_chunk_lexical_overlap", 0.0)

    raw = (
        +0.30 * q_complexity
        +0.25 * kw_complexity
        -0.20 * cache_warmth
        -0.15 * reuse_confidence
        -0.10 * lexical_clarity
    )
    score = max(0.0, min(1.0, (raw + 0.45) / 1.0))

    if score < 0.30:
        return StrategyDecision(
            path=StrategyPath.LIGHT,
            candidate="E",
            reason=f"low_composite(score={score:.3f})",
            signals=signals,
        )
    if score > 0.70:
        return StrategyDecision(
            path=StrategyPath.DEEP,
            candidate="E",
            reason=f"high_composite(score={score:.3f})",
            signals=signals,
        )
    return StrategyDecision(
        path=StrategyPath.STANDARD,
        candidate="E",
        reason=f"moderate_composite(score={score:.3f})",
        signals=signals,
    )


CANDIDATE_REGISTRY = {
    "control": None,
    "candidate_a": candidate_a_lexical_complexity,
    "candidate_b": candidate_b_cache_warmth,
    "candidate_c": candidate_c_reuse_confidence,
    "candidate_d": candidate_d_priority_prescreen,
    "candidate_e": candidate_e_composite,
}
