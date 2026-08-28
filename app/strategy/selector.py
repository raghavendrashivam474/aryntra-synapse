"""
S10 - Adaptive Strategy Selector.

Orchestrates signal extraction, candidate evaluation, and path execution.
"""
import time
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.strategy.signals import extract_query_signals
from app.strategy.candidates import (
    StrategyPath,
    StrategyDecision,
    CANDIDATE_REGISTRY,
)

logger = logging.getLogger(__name__)


class StrategyTelemetry:
    """Records S10 decision and execution metrics for observability."""

    def __init__(self):
        self.decisions: List[Dict[str, Any]] = []
        self.total_light = 0
        self.total_standard = 0
        self.total_deep = 0
        self.selector_latency_total = 0.0

    def record(self, decision: StrategyDecision, execution_latency: float) -> None:
        entry = decision.to_dict()
        entry["execution_latency"] = round(execution_latency, 6)
        self.decisions.append(entry)
        if decision.path == StrategyPath.LIGHT:
            self.total_light += 1
        elif decision.path == StrategyPath.STANDARD:
            self.total_standard += 1
        else:
            self.total_deep += 1

    def to_dict(self) -> dict:
        return {
            "total_decisions": len(self.decisions),
            "light_count": self.total_light,
            "standard_count": self.total_standard,
            "deep_count": self.total_deep,
            "selector_latency_total": round(self.selector_latency_total, 6),
            "decisions": self.decisions,
        }

    def reset(self) -> None:
        self.decisions.clear()
        self.total_light = 0
        self.total_standard = 0
        self.total_deep = 0
        self.selector_latency_total = 0.0


class AdaptiveSelector:
    """
    S10 Adaptive Strategy Selector.
    """

    def __init__(
        self,
        mode: str = "control",
        primary_candidate: str = "candidate_e",
        fallback_candidate: str = "candidate_d",
    ):
        if mode not in CANDIDATE_REGISTRY and mode not in (
            "adaptive",
            "adaptive_fallback",
        ):
            raise ValueError(
                f"Unknown S10 mode: {mode}. "
                f"Valid: {list(CANDIDATE_REGISTRY.keys())} + adaptive, adaptive_fallback"
            )
        self.mode = mode
        self.primary_candidate = primary_candidate
        self.fallback_candidate = fallback_candidate
        self.telemetry = StrategyTelemetry()

    def select(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        reuse_metrics: Optional[Dict[str, Any]] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> StrategyDecision:
        t0 = time.perf_counter()

        signals = extract_query_signals(query, chunks, reuse_metrics, cache_stats)

        if self.mode == "control":
            decision = StrategyDecision(
                path=StrategyPath.STANDARD,
                candidate="control",
                reason="control_always_standard",
                signals=signals,
            )

        elif self.mode == "adaptive":
            fn = CANDIDATE_REGISTRY.get(self.primary_candidate)
            if fn:
                decision = fn(signals)
            else:
                decision = StrategyDecision(
                    path=StrategyPath.STANDARD,
                    candidate="adaptive",
                    reason="primary_missing_fallback_standard",
                    signals=signals,
                )

        elif self.mode == "adaptive_fallback":
            primary_fn = CANDIDATE_REGISTRY.get(self.primary_candidate)
            fallback_fn = CANDIDATE_REGISTRY.get(self.fallback_candidate)

            if primary_fn:
                decision = primary_fn(signals)
            else:
                decision = StrategyDecision(
                    path=StrategyPath.STANDARD,
                    candidate="fallback",
                    reason="primary_missing",
                    signals=signals,
                )

            if decision.path == StrategyPath.LIGHT and fallback_fn:
                fb_decision = fallback_fn(signals)
                if fb_decision.path != StrategyPath.LIGHT:
                    decision = StrategyDecision(
                        path=StrategyPath.STANDARD,
                        candidate=f"{self.primary_candidate}+{self.fallback_candidate}",
                        reason=f"fallback_override({decision.reason})",
                        signals=signals,
                    )

        else:
            fn = CANDIDATE_REGISTRY.get(self.mode)
            if fn:
                decision = fn(signals)
            else:
                decision = StrategyDecision(
                    path=StrategyPath.STANDARD,
                    candidate=self.mode,
                    reason="candidate_fn_missing",
                    signals=signals,
                )

        self.telemetry.selector_latency_total += time.perf_counter() - t0
        return decision

    def execute_path(
        self,
        decision: StrategyDecision,
        query: str,
        chunks: List[Dict[str, Any]],
        priority_engine,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        t0 = time.perf_counter()

        empty_metrics = {
            "priority_latency": 0.0,
            "high_priority_count": 0,
            "medium_priority_count": 0,
            "low_priority_count": 0,
            "active_evidence_count": len(chunks),
            "retained_evidence_count": 0,
            "average_priority_score": 0.0,
            "semantic_calls": 0,
            "semantic_cache_hits": 0,
            "semantic_cache_misses": 0,
            "query_cache_hits": 0,
            "query_cache_misses": 0,
            "lexical_fast_path_hits": 0,
            "semantic_fallback_count": 0,
            "semantic_latency": 0.0,
            "cache_lookup_latency": 0.0,
        }

        if decision.path == StrategyPath.LIGHT:
            result_chunks = chunks
            metrics = empty_metrics

        elif decision.path == StrategyPath.DEEP:
            ranked, pm = priority_engine.rank(query, chunks)
            metrics = pm.to_dict()
            metrics["s10_deep_path"] = True
            result_chunks = ranked

        else:  # STANDARD
            ranked, pm = priority_engine.rank(query, chunks)
            metrics = pm.to_dict()
            result_chunks = ranked

        exec_latency = time.perf_counter() - t0
        self.telemetry.record(decision, exec_latency)

        logger.info(
            "S10 [%s] %s -> %s (%.3fms) | %s",
            self.mode,
            decision.candidate,
            decision.path.value,
            exec_latency * 1000,
            decision.reason,
        )

        return result_chunks, metrics
