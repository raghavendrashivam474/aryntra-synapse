import pytest
from unittest.mock import MagicMock
from app.strategy.signals import extract_query_signals
from app.strategy.candidates import (
    StrategyPath,
    StrategyDecision,
    candidate_a_lexical_complexity,
    candidate_b_cache_warmth,
    candidate_c_reuse_confidence,
    candidate_d_priority_prescreen,
    candidate_e_composite,
    CANDIDATE_REGISTRY,
)
from app.strategy.selector import AdaptiveSelector, StrategyTelemetry
from app.core.config import settings


def test_signals_empty_query_and_chunks():
    signals = extract_query_signals("", [])
    assert signals["query_length"] == 0
    assert signals["query_keyword_count"] == 0
    assert signals["chunk_count"] == 0
    assert signals["reuse_rate"] == 0.0
    assert signals["cache_hit_rate"] == 0.0
    assert signals["first_chunk_lexical_overlap"] == 0.0


def test_signals_with_valid_chunks():
    query = "what is synapse architecture"
    chunks = [
        {"chunk_id": "c1", "text": "synapse architecture combines retrieval and context", "evidence_status": "reused"},
        {"chunk_id": "c2", "text": "unrelated text about cooking recipes", "evidence_status": "new"},
    ]
    reuse_metrics = {"reuse_rate": 0.50, "reused_count": 1}
    cache_stats = {"hit_rate": 0.75, "hits": 3, "misses": 1}

    signals = extract_query_signals(query, chunks, reuse_metrics, cache_stats)

    assert signals["query_length"] == 4
    assert signals["chunk_count"] == 2
    assert signals["reuse_rate"] == 0.50
    assert signals["cache_hit_rate"] == 0.75
    assert signals["first_chunk_lexical_overlap"] > 0.0
    assert signals["reused_count"] == 1


def test_candidate_a_simple_query():
    signals = {"query_length": 2, "query_keyword_count": 2}
    decision = candidate_a_lexical_complexity(signals)
    assert decision.path == StrategyPath.LIGHT
    assert decision.candidate == "A"


def test_candidate_a_complex_query():
    signals = {"query_length": 14, "query_keyword_count": 8}
    decision = candidate_a_lexical_complexity(signals)
    assert decision.path == StrategyPath.DEEP
    assert decision.candidate == "A"


def test_candidate_a_moderate_query():
    signals = {"query_length": 6, "query_keyword_count": 4}
    decision = candidate_a_lexical_complexity(signals)
    assert decision.path == StrategyPath.STANDARD


def test_candidate_b_warm_cache():
    signals = {"cache_hit_rate": 0.90, "chunk_count": 3}
    decision = candidate_b_cache_warmth(signals)
    assert decision.path == StrategyPath.STANDARD


def test_candidate_b_cold_cache_many_chunks():
    signals = {"cache_hit_rate": 0.10, "chunk_count": 5}
    decision = candidate_b_cache_warmth(signals)
    assert decision.path == StrategyPath.LIGHT


def test_candidate_c_high_reuse():
    signals = {"reuse_rate": 0.90, "chunk_count": 3}
    decision = candidate_c_reuse_confidence(signals)
    assert decision.path == StrategyPath.LIGHT


def test_candidate_c_novel_evidence():
    signals = {"reuse_rate": 0.0, "chunk_count": 4}
    decision = candidate_c_reuse_confidence(signals)
    assert decision.path == StrategyPath.STANDARD


def test_candidate_d_clear_relevance():
    signals = {"first_chunk_lexical_overlap": 0.80, "chunk_count": 2, "avg_lexical_overlap": 0.70}
    decision = candidate_d_priority_prescreen(signals)
    assert decision.path == StrategyPath.LIGHT


def test_candidate_d_clear_irrelevance():
    signals = {"first_chunk_lexical_overlap": 0.0, "chunk_count": 3, "avg_lexical_overlap": 0.0}
    decision = candidate_d_priority_prescreen(signals)
    assert decision.path == StrategyPath.LIGHT


def test_candidate_d_ambiguous():
    signals = {"first_chunk_lexical_overlap": 0.30, "chunk_count": 4, "avg_lexical_overlap": 0.20}
    decision = candidate_d_priority_prescreen(signals)
    assert decision.path == StrategyPath.DEEP


def test_candidate_e_composite_low_and_high():
    signals_light = {
        "query_length": 2, "query_keyword_count": 1,
        "cache_hit_rate": 1.0, "reuse_rate": 1.0,
        "first_chunk_lexical_overlap": 0.9,
    }
    decision_light = candidate_e_composite(signals_light)
    assert decision_light.path == StrategyPath.LIGHT

    signals_deep = {
        "query_length": 15, "query_keyword_count": 10,
        "cache_hit_rate": 0.0, "reuse_rate": 0.0,
        "first_chunk_lexical_overlap": 0.0,
    }
    decision_deep = candidate_e_composite(signals_deep)
    assert decision_deep.path == StrategyPath.DEEP


def test_selector_control_mode():
    selector = AdaptiveSelector(mode="control")
    decision = selector.select("test query", [{"text": "chunk text"}])
    assert decision.path == StrategyPath.STANDARD
    assert decision.candidate == "control"


def test_selector_individual_candidate_mode():
    selector = AdaptiveSelector(mode="candidate_a")
    decision = selector.select("hi", [{"text": "hello"}])
    assert decision.path == StrategyPath.LIGHT
    assert decision.candidate == "A"


def test_selector_adaptive_mode():
    selector = AdaptiveSelector(mode="adaptive", primary_candidate="candidate_d")
    decision = selector.select("test query", [{"text": "test query completely matches"}])
    assert decision.path == StrategyPath.LIGHT


def test_selector_fallback_mode_safety():
    selector = AdaptiveSelector(
        mode="adaptive_fallback",
        primary_candidate="candidate_a",
        fallback_candidate="candidate_d",
    )
    decision = selector.select(
        "short",
        [{"text": "ambiguous context one"}, {"text": "two"}, {"text": "three"}, {"text": "four"}]
    )
    assert decision.path in (StrategyPath.STANDARD, StrategyPath.LIGHT)


def test_selector_execute_path_light():
    selector = AdaptiveSelector(mode="control")
    decision = StrategyDecision(path=StrategyPath.LIGHT, candidate="test", reason="test")
    chunks = [{"chunk_id": "c1", "text": "sample"}]
    mock_engine = MagicMock()

    result, metrics = selector.execute_path(decision, "query", chunks, mock_engine)
    assert result == chunks
    assert metrics["semantic_calls"] == 0
    assert metrics["priority_latency"] == 0.0
    mock_engine.rank.assert_not_called()


def test_selector_execute_path_standard():
    selector = AdaptiveSelector(mode="control")
    decision = StrategyDecision(path=StrategyPath.STANDARD, candidate="test", reason="test")
    chunks = [{"chunk_id": "c1", "text": "sample"}]
    mock_engine = MagicMock()
    mock_metrics = MagicMock()
    mock_metrics.to_dict.return_value = {"priority_latency": 0.001, "semantic_calls": 1}
    mock_engine.rank.return_value = (chunks, mock_metrics)

    result, metrics = selector.execute_path(decision, "query", chunks, mock_engine)
    mock_engine.rank.assert_called_once_with("query", chunks)
    assert metrics["semantic_calls"] == 1


def test_telemetry_recording():
    telemetry = StrategyTelemetry()
    decision = StrategyDecision(path=StrategyPath.LIGHT, candidate="A", reason="simple")
    telemetry.record(decision, 0.0005)

    stats = telemetry.to_dict()
    assert stats["total_decisions"] == 1
    assert stats["light_count"] == 1
    assert stats["standard_count"] == 0
    assert stats["deep_count"] == 0

    telemetry.reset()
    assert telemetry.to_dict()["total_decisions"] == 0


def test_health_endpoint_contains_s10():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "enable_adaptive_strategy" in data
    assert "s10_mode" in data