import pytest
from experiments.s11_quality_evaluation import (
    detect_refusal,
    measure_keyword_coverage,
    measure_evidence_grounding,
    detect_unsupported_numbers,
    evaluate_quality,
    analyze_results,
)


def test_detect_refusal_positive():
    assert detect_refusal("I do not have enough information to answer this question.") is True
    assert detect_refusal("The provided context does not mention the author.") is True
    assert detect_refusal("Based on the provided context I cannot tell.") is True


def test_detect_refusal_negative():
    assert detect_refusal("Aryntra Synapse is a context-processing engine.") is False
    assert detect_refusal("The cache size is 4096 entries.") is False


def test_measure_keyword_coverage():
    query = "How to configure embedding cache max size?"
    answer = "To configure the embedding cache max size, use the settings parameter."
    cov = measure_keyword_coverage(answer, query)
    assert cov >= 0.75


def test_measure_evidence_grounding():
    chunks = [{"text": "Aryntra Synapse uses bounded LRU caches with maximum 4096 entries."}]
    answer = "Synapse features bounded caches holding up to 4096 entries."
    grounding = measure_evidence_grounding(answer, chunks)
    assert grounding > 0.0


def test_detect_unsupported_numbers():
    chunks = [{"text": "Synapse has 4096 cache entries."}]
    answer_valid = "The system supports 4096 cache items."
    assert detect_unsupported_numbers(answer_valid, chunks) == 0

    answer_invalid = "The system supports 9999 cache items."
    assert detect_unsupported_numbers(answer_invalid, chunks) == 1


def test_evaluate_quality_tier():
    chunks = [{"text": "Aryntra Synapse is an advanced context-processing and context-engineering engine."}]
    ans = "Aryntra Synapse is an advanced context-processing engine designed for context-engineering."
    q_rec = evaluate_quality("What is Synapse?", ans, chunks)
    assert q_rec["quality_tier"] in ("GOOD", "ACCEPTABLE")
    assert q_rec["refusal"] is False


def test_analyze_results_aggregation():
    mock_results = {
        "A_frozen": [{
            "config": "A_frozen",
            "total_latency": 10.0,
            "preprocessing_latency": 0.0,
            "generation_latency": 10.0,
            "quality": {
                "quality_tier": "GOOD",
                "failure_category": "NONE",
                "evidence_grounding": 0.8,
                "keyword_coverage": 0.9,
                "refusal": False
            }
        }]
    }
    analysis = analyze_results(mock_results)
    assert "A_frozen" in analysis
    assert analysis["A_frozen"]["mean_total_latency"] == 10.0
    assert analysis["A_frozen"]["good_or_acceptable_rate"] == 1.0