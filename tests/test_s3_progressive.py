import pytest
from app.context.progressive import ProgressiveContextEngine


class MockLLMProvider:
    """Mock LLM provider returning predetermined sufficiency responses."""

    def __init__(self, sufficiency_sequence=None, default_judgment="SUFFICIENT"):
        self.sequence = list(sufficiency_sequence or [])
        self.default_judgment = default_judgment
        self.raw_calls = []

    def generate_raw(self, prompt: str) -> str:
        self.raw_calls.append(prompt)
        if self.sequence:
            return self.sequence.pop(0)
        return self.default_judgment


def generate_sample_chunks(n=3):
    # Use topically distinct sentences to avoid S2 sentence similarity deduplication (threshold = 0.90)
    texts = [
        "The capital of France is Paris. It is a major European city and a global center for art, fashion, gastronomy and culture.",
        "The theory of general relativity was developed by Albert Einstein between 1907 and 1915, describing gravity as geometry.",
        "Photosynthesis is a process used by plants and other organisms to convert light energy into chemical energy for fuel."
    ]
    return [
        {
            "chunk_id": f"doc_chunk_{i}",
            "text": texts[i - 1],
            "score": round(0.95 - (i * 0.1), 4),
        }
        for i in range(1, min(n + 1, len(texts) + 1))
    ]


def test_1_one_chunk_sufficient():
    """Test 1: Stage 1 chunk is immediately judged SUFFICIENT."""
    mock_llm = MockLLMProvider(sufficiency_sequence=["SUFFICIENT"])
    engine = ProgressiveContextEngine(llm_provider=mock_llm)
    chunks = generate_sample_chunks(3)

    result = engine.run("What is topic 1?", chunks)

    assert result["expansion_steps"] == 0
    assert result["final_context_chunks"] == 1
    assert result["total_model_calls"] == 1
    assert len(result["stages"]) == 1
    assert result["stages"][0]["sufficiency"] == "SUFFICIENT"


def test_2_two_chunks_required():
    """Test 2: Stage 1 is INSUFFICIENT, Stage 2 expands and is SUFFICIENT."""
    mock_llm = MockLLMProvider(sufficiency_sequence=["INSUFFICIENT", "SUFFICIENT"])
    engine = ProgressiveContextEngine(llm_provider=mock_llm)
    chunks = generate_sample_chunks(3)

    result = engine.run("Compare topic 1 and topic 2", chunks)

    assert result["expansion_steps"] == 1
    assert result["final_context_chunks"] == 2
    assert result["total_model_calls"] == 2
    assert len(result["stages"]) == 2
    assert result["stages"][0]["sufficiency"] == "INSUFFICIENT"
    assert result["stages"][1]["sufficiency"] == "SUFFICIENT"
    assert result["final_context_length"] > result["initial_context_length"]


def test_3_maximum_expansion():
    """Test 3: Expansion proceeds to all Top-K chunks without exceeding limit."""
    mock_llm = MockLLMProvider(sufficiency_sequence=["INSUFFICIENT", "INSUFFICIENT"])
    engine = ProgressiveContextEngine(llm_provider=mock_llm, max_steps=2)
    chunks = generate_sample_chunks(3)

    result = engine.run("Synthesize all concepts", chunks)

    assert result["expansion_steps"] == 2
    assert result["final_context_chunks"] == 3
    assert result["total_model_calls"] == 2
    assert result["stages"][2]["sufficiency"] == "MAX_CHUNKS_REACHED"


def test_4_deterministic_ordering():
    """Test 4: Same input produces identical stages, lengths, and chunks."""
    chunks = generate_sample_chunks(3)

    engine1 = ProgressiveContextEngine(llm_provider=MockLLMProvider(["INSUFFICIENT", "SUFFICIENT"]))
    r1 = engine1.run("Test deterministic", chunks)

    engine2 = ProgressiveContextEngine(llm_provider=MockLLMProvider(["INSUFFICIENT", "SUFFICIENT"]))
    r2 = engine2.run("Test deterministic", chunks)

    assert r1["expansion_steps"] == r2["expansion_steps"]
    assert r1["initial_context_length"] == r2["initial_context_length"]
    assert r1["final_context_length"] == r2["final_context_length"]
    assert r1["cumulative_context_length"] == r2["cumulative_context_length"]


def test_5_bounded_safety_limit():
    """Test 5: System terminates deterministically even if LLM always says INSUFFICIENT."""
    mock_llm = MockLLMProvider(sufficiency_sequence=["INSUFFICIENT"] * 50)
    engine = ProgressiveContextEngine(llm_provider=mock_llm, max_steps=2)
    chunks = generate_sample_chunks(3)

    result = engine.run("Unbounded test", chunks)

    assert result["expansion_steps"] <= 2
    assert result["total_model_calls"] <= 2


def test_6_context_accounting_integrity():
    """Test 6: Cumulative context correctly accumulates across stages."""
    mock_llm = MockLLMProvider(sufficiency_sequence=["INSUFFICIENT", "SUFFICIENT"])
    engine = ProgressiveContextEngine(llm_provider=mock_llm)
    chunks = generate_sample_chunks(3)

    result = engine.run("Accounting test", chunks)

    s1_len = result["stages"][0]["context_length"]
    s2_len = result["stages"][1]["context_length"]
    assert result["cumulative_context_length"] == s1_len + s2_len
    assert result["peak_context_length"] == s2_len
