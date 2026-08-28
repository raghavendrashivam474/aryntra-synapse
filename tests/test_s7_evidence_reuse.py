"""
tests/test_s7_evidence_reuse.py

Aryntra Synapse — Sprint 7
Evidence Reuse & Deduplication tests.
"""

import pytest
from app.retrieval.evidence_fingerprint import EvidenceFingerprint


@pytest.fixture
def fp():
    return EvidenceFingerprint()


class TestFingerprint:
    def test_same_text_same_fingerprint(self, fp):
        """Test 1: Same text produces same fingerprint."""
        text = "The system uses FAISS for retrieval."
        assert fp.fingerprint(text) == fp.fingerprint(text)

    def test_different_text_different_fingerprint(self, fp):
        """Test 2: Different text produces different fingerprint."""
        a = fp.fingerprint("The system uses FAISS.")
        b = fp.fingerprint("The system uses BM25.")
        assert a != b

    def test_whitespace_normalization(self, fp):
        """Test 3: Whitespace variations produce same fingerprint."""
        base = "The system uses FAISS for retrieval."
        variants = [
            "  The system uses FAISS for retrieval.  ",
            "The  system   uses FAISS  for retrieval.",
            "The\tsystem\tuses\tFAISS\tfor\tretrieval.",
            "The\nsystem\nuses\nFAISS\nfor\nretrieval.",
            "The\r\nsystem\r\nuses\r\nFAISS\r\nfor\r\nretrieval.",
        ]
        base_fp = fp.fingerprint(base)
        for v in variants:
            assert fp.fingerprint(v) == base_fp, f"Failed for: {repr(v)}"

    def test_different_meaningful_content(self, fp):
        """Test 4: Different meaningful content produces different fingerprint."""
        a = fp.fingerprint("FAISS is a vector search library.")
        b = fp.fingerprint("BM25 is a lexical ranking function.")
        assert a != b

    def test_empty_input(self, fp):
        """Test 5: Empty input handled correctly."""
        assert fp.fingerprint("") == fp.fingerprint("")
        assert fp.fingerprint("") == fp.fingerprint("   ")
        assert fp.normalize("") == ""
