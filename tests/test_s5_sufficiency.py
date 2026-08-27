import pytest
from app.context.sufficiency import SufficiencyEngine, extract_keywords


def make_chunks(n=3, base_score=0.8):
    texts = [
        "Paris is the capital of France and a major European cultural center with the Eiffel Tower.",
        "Albert Einstein developed the theory of general relativity describing gravity as spacetime curvature.",
        "Photosynthesis converts light energy into chemical energy stored in glucose molecules in plants.",
    ]
    return [
        {"chunk_id": f"doc_chunk_{i}", "text": texts[i - 1], "score": round(base_score - i * 0.15, 4)}
        for i in range(1, min(n + 1, len(texts) + 1))
    ]


def test_extract_keywords():
    kw = extract_keywords("What is the capital of France?")
    assert "capital" in kw
    assert "france" in kw
    assert "what" not in kw  # stopword
    assert "the" not in kw   # stopword


def test_sufficient_high_score_good_coverage():
    engine = SufficiencyEngine(score_threshold=0.4, coverage_threshold=0.2)
    chunks = make_chunks(1, base_score=0.9)
    result = engine.evaluate("capital France", chunks)
    assert result.is_sufficient is True
    assert result.reason == "score_and_coverage_sufficient"


def test_insufficient_low_score():
    engine = SufficiencyEngine(score_threshold=0.9, coverage_threshold=0.1)
    chunks = make_chunks(1, base_score=0.5)
    result = engine.evaluate("capital France", chunks)
    assert result.is_sufficient is False
    assert "score" in result.reason


def test_insufficient_low_coverage():
    engine = SufficiencyEngine(score_threshold=0.1, coverage_threshold=0.9)
    chunks = make_chunks(1, base_score=0.9)
    result = engine.evaluate("quantum computing algorithms", chunks)
    assert result.is_sufficient is False
    assert "coverage" in result.reason


def test_no_active_evidence():
    engine = SufficiencyEngine()
    result = engine.evaluate("test query", [])
    assert result.is_sufficient is False
    assert result.reason == "no_active_evidence"


def test_empty_query_keywords():
    engine = SufficiencyEngine(score_threshold=0.1, coverage_threshold=0.5)
    chunks = make_chunks(1, base_score=0.9)
    result = engine.evaluate("the a an", chunks)  # all stopwords
    assert result.is_sufficient is True  # defers to score


def test_sufficiency_result_serialization():
    engine = SufficiencyEngine()
    chunks = make_chunks(1)
    result = engine.evaluate("France capital", chunks)
    d = result.to_dict()
    assert "is_sufficient" in d
    assert "reason" in d
    assert "top_score" in d
    assert "coverage_ratio" in d


def test_deterministic_evaluation():
    engine = SufficiencyEngine(score_threshold=0.4, coverage_threshold=0.2)
    chunks = make_chunks(2)
    r1 = engine.evaluate("capital France", chunks)
    r2 = engine.evaluate("capital France", chunks)
    assert r1.is_sufficient == r2.is_sufficient
    assert r1.reason == r2.reason
    assert r1.coverage_ratio == r2.coverage_ratio


def test_more_chunks_improve_coverage():
    engine = SufficiencyEngine(score_threshold=0.1, coverage_threshold=0.5)
    chunks_1 = make_chunks(1, base_score=0.9)
    chunks_2 = make_chunks(2, base_score=0.9)
    r1 = engine.evaluate("Einstein relativity photosynthesis", chunks_1)
    r2 = engine.evaluate("Einstein relativity photosynthesis", chunks_2)
    assert r2.matched_keywords >= r1.matched_keywords