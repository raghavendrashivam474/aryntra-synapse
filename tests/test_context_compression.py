"""
Tests for S2 Context Compressor

Run with:
    pytest tests/test_context_compression.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.context.compressor import (
    compress_chunks,
    build_compressed_context,
    _normalize_whitespace,
    _remove_structural_markers,
    _truncate_at_sentence,
    _extract_sentences,
    _sentence_similarity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "c1",
            "text": "Paris is the capital of France. It is located on the Seine River. The city has a population of over 2 million people.",
            "score": 0.95,
        },
        {
            "chunk_id": "c2",
            "text": "France is a country in Western Europe. Paris is the capital of France. It is known for the Eiffel Tower.",
            "score": 0.85,
        },
        {
            "chunk_id": "c3",
            "text": "The Eiffel Tower was built in 1889. It is located in Paris. It is one of the most recognizable structures in the world.",
            "score": 0.75,
        },
    ]


@pytest.fixture
def empty_chunks():
    return []


@pytest.fixture
def single_chunk():
    return [
        {
            "chunk_id": "c1",
            "text": "A single short sentence.",
            "score": 0.99,
        }
    ]


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------

class TestWhitespaceNormalization:
    def test_collapses_excess_newlines(self):
        text = "line1\n\n\n\n\nline2"
        result = _normalize_whitespace(text)
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_strips_lines(self):
        text = "  hello  \n  world  "
        result = _normalize_whitespace(text)
        assert result == "hello\nworld"

    def test_preserves_double_newlines(self):
        text = "para1\n\npara2"
        result = _normalize_whitespace(text)
        assert result == "para1\n\npara2"


# ---------------------------------------------------------------------------
# Structural marker removal
# ---------------------------------------------------------------------------

class TestStructuralMarkerRemoval:
    def test_removes_source_markers(self):
        text = "[Source: doc1.txt] Some actual content."
        result = _remove_structural_markers(text)
        assert "[Source:" not in result
        assert "Some actual content." in result

    def test_removes_relevance_markers(self):
        text = "[Relevance: high] Important info here."
        result = _remove_structural_markers(text)
        assert "[Relevance:" not in result

    def test_removes_separator_lines(self):
        text = "text above\n---\ntext below"
        result = _remove_structural_markers(text)
        assert "---" not in result

    def test_preserves_normal_text(self):
        text = "This is normal text without markers."
        result = _remove_structural_markers(text)
        assert result == text


# ---------------------------------------------------------------------------
# Sentence truncation
# ---------------------------------------------------------------------------

class TestSentenceTruncation:
    def test_short_text_unchanged(self):
        text = "Short text."
        result = _truncate_at_sentence(text, 400)
        assert result == text

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = _truncate_at_sentence(text, 35)
        assert result.endswith(".")
        assert len(result) <= 35

    def test_hard_truncate_with_ellipsis(self):
        text = "ThisIsAVeryLongSentenceWithoutAnyPeriodsOrBoundariesWhatsoever"
        result = _truncate_at_sentence(text, 20)
        assert result.endswith("...")
        assert len(result) <= 23  # 20 + "..."

    def test_exact_boundary(self):
        text = "Exact fit."
        result = _truncate_at_sentence(text, 10)
        assert result == "Exact fit."


# ---------------------------------------------------------------------------
# Sentence extraction
# ---------------------------------------------------------------------------

class TestSentenceExtraction:
    def test_splits_sentences(self):
        text = "First. Second. Third."
        sentences = _extract_sentences(text)
        assert len(sentences) == 3

    def test_handles_single_sentence(self):
        text = "Just one sentence."
        sentences = _extract_sentences(text)
        assert len(sentences) == 1

    def test_empty_text(self):
        sentences = _extract_sentences("")
        assert sentences == []


# ---------------------------------------------------------------------------
# Sentence similarity
# ---------------------------------------------------------------------------

class TestSentenceSimilarity:
    def test_identical_sentences(self):
        s = "The quick brown fox."
        assert _sentence_similarity(s, s) == 1.0

    def test_case_insensitive(self):
        s1 = "The Quick Brown Fox."
        s2 = "the quick brown fox."
        assert _sentence_similarity(s1, s2) == 1.0

    def test_different_sentences(self):
        s1 = "The cat sat on the mat."
        s2 = "Quantum physics is complex."
        assert _sentence_similarity(s1, s2) < 0.5


# ---------------------------------------------------------------------------
# Compress chunks (integration)
# ---------------------------------------------------------------------------

class TestCompressChunks:
    def test_empty_input(self, empty_chunks):
        result = compress_chunks(empty_chunks)
        assert result == []

    def test_single_chunk_preserved(self, single_chunk):
        result = compress_chunks(single_chunk)
        assert len(result) == 1
        assert "single short sentence" in result[0]["text"].lower()

    def test_reduces_context_size(self, sample_chunks):
        original_total = sum(len(c["text"]) for c in sample_chunks)
        compressed = compress_chunks(sample_chunks, max_chunk_chars=50)
        compressed_total = sum(len(c["text"]) for c in compressed)
        assert compressed_total < original_total

    def test_deterministic_output(self, sample_chunks):
        r1 = compress_chunks(sample_chunks)
        r2 = compress_chunks(sample_chunks)
        for a, b in zip(r1, r2):
            assert a["text"] == b["text"]
            assert a["chunk_id"] == b["chunk_id"]

    def test_preserves_chunk_ids(self, sample_chunks):
        result = compress_chunks(sample_chunks)
        ids = {c["chunk_id"] for c in result}
        assert ids == {"c1", "c2", "c3"}

    def test_deduplication_removes_overlap(self):
        chunks = [
            {"chunk_id": "a", "text": "Paris is the capital of France.", "score": 0.9},
            {"chunk_id": "b", "text": "Paris is the capital of France. Also some other info.", "score": 0.8},
        ]
        result = compress_chunks(chunks, dedup_threshold=0.90)
        # The duplicate sentence should appear only once
        full_text = " ".join(c["text"] for c in result)
        count = full_text.lower().count("paris is the capital of france")
        assert count == 1

    def test_does_not_mutate_input(self, sample_chunks):
        import copy
        original = copy.deepcopy(sample_chunks)
        compress_chunks(sample_chunks)
        assert sample_chunks == original


# ---------------------------------------------------------------------------
# Build compressed context (full pipeline)
# ---------------------------------------------------------------------------

class TestBuildCompressedContext:
    def test_empty_returns_empty(self):
        assert build_compressed_context([]) == ""

    def test_produces_string(self, sample_chunks):
        result = build_compressed_context(sample_chunks)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_shorter_than_flat(self, sample_chunks):
        flat_total = sum(len(c["text"]) for c in sample_chunks)
        compressed = build_compressed_context(sample_chunks, max_chunk_chars=50)
        assert len(compressed) < flat_total

    def test_contains_numbered_sections(self, sample_chunks):
        result = build_compressed_context(sample_chunks)
        assert "[1]" in result
        assert "[2]" in result
