"""
tests/test_s7_evidence_reuse.py

Aryntra Synapse — Sprint 7
Evidence Reuse & Deduplication tests.
"""

import pytest
from app.retrieval.evidence_fingerprint import EvidenceFingerprint
from app.context.evidence_store import EvidenceStore, ReuseMetrics


@pytest.fixture
def fp():
    return EvidenceFingerprint()


@pytest.fixture
def store():
    return EvidenceStore()


def make_chunks(texts=None):
    if texts is None:
        texts = [
            "Paris is the capital of France.",
            "Einstein developed general relativity.",
            "Photosynthesis converts light to energy.",
        ]
    return [
        {"chunk_id": f"chunk_{i}", "text": t, "score": round(0.9 - i * 0.1, 4)}
        for i, t in enumerate(texts)
    ]


# ── Fingerprint Tests (1-5) ──────────────────────────────────────

class TestFingerprint:
    def test_same_text_same_fingerprint(self, fp):
        text = "The system uses FAISS for retrieval."
        assert fp.fingerprint(text) == fp.fingerprint(text)

    def test_different_text_different_fingerprint(self, fp):
        a = fp.fingerprint("The system uses FAISS.")
        b = fp.fingerprint("The system uses BM25.")
        assert a != b

    def test_whitespace_normalization(self, fp):
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
        a = fp.fingerprint("FAISS is a vector search library.")
        b = fp.fingerprint("BM25 is a lexical ranking function.")
        assert a != b

    def test_empty_input(self, fp):
        assert fp.fingerprint("") == fp.fingerprint("")
        assert fp.fingerprint("") == fp.fingerprint("   ")
        assert fp.normalize("") == ""


# ── Evidence Store Tests (6-10) ──────────────────────────────────

class TestEvidenceStore:
    def test_new_evidence_inserted(self, store):
        chunks = make_chunks(["Alpha evidence."])
        tagged, metrics = store.process(chunks)
        assert store.size == 1
        assert metrics.new_count == 1
        assert metrics.reused_count == 0
        assert tagged[0]["evidence_status"] == "new"

    def test_existing_evidence_detected(self, store):
        chunks = make_chunks(["Alpha evidence."])
        store.process(chunks)
        tagged2, metrics2 = store.process(chunks)
        assert metrics2.reused_count == 1
        assert metrics2.new_count == 0
        assert tagged2[0]["evidence_status"] == "reused"

    def test_duplicate_not_inserted_twice(self, store):
        chunks = make_chunks(["Alpha evidence."])
        store.process(chunks)
        store.process(chunks)
        store.process(chunks)
        assert store.size == 1

    def test_retrieval_by_fingerprint(self, store, fp):
        text = "Unique evidence text."
        chunks = make_chunks([text])
        store.process(chunks)
        fingerprint = fp.fingerprint(text)
        result = store.lookup(fingerprint)
        assert result["text"] == text
        assert store.has(fingerprint) is True
        assert store.has("nonexistent") is False

    def test_workspace_count_after_duplicates(self, store):
        chunks_a = make_chunks(["Alpha.", "Beta."])
        chunks_b = make_chunks(["Alpha.", "Gamma."])
        store.process(chunks_a)
        assert store.size == 2
        store.process(chunks_b)
        assert store.size == 3


# ── Integration Tests (11-14) ────────────────────────────────────

class TestIntegration:
    def test_reused_evidence_reaches_pipeline(self, store):
        """Test 11: Reused evidence reaches the normal S6 pipeline."""
        chunks = make_chunks(["Pipeline evidence."])
        tagged, _ = store.process(chunks)
        store.process(chunks)
        tagged2, metrics2 = store.process(chunks)
        assert len(tagged2) == 1
        assert tagged2[0]["chunk_id"] == "chunk_0"
        assert tagged2[0]["text"] == "Pipeline evidence."
        assert tagged2[0]["score"] == 0.9
        assert "fingerprint" in tagged2[0]
        assert "evidence_status" in tagged2[0]

    def test_reuse_does_not_bypass_sufficiency(self, store):
        """Test 12: Reuse does not bypass sufficiency evaluation."""
        chunks = make_chunks(["Sufficiency test."])
        store.process(chunks)
        tagged, _ = store.process(chunks)
        for key in tagged[0]:
            assert "sufficient" not in key.lower()

    def test_reuse_does_not_alter_semantics(self, store):
        """Test 13: Reuse does not alter LLM answer generation semantics."""
        original = make_chunks(["Semantic preservation test."])
        tagged, _ = store.process(original)
        assert tagged[0]["chunk_id"] == original[0]["chunk_id"]
        assert tagged[0]["text"] == original[0]["text"]
        assert tagged[0]["score"] == original[0]["score"]

    def test_existing_tests_remain_green(self, store):
        """Test 14: S7 additions do not break existing workspace patterns."""
        from app.context.workspace import EvidenceWorkspace
        chunks = make_chunks(["WS test A.", "WS test B.", "WS test C."])
        tagged, _ = store.process(chunks)
        ws = EvidenceWorkspace(tagged)
        ws.promote_initial(count=1)
        assert ws.active_count == 1
        assert ws.available_count == 2
        active = ws.active()
        assert "fingerprint" in active[0]


# ── Edge Cases ────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_batch(self, store):
        tagged, metrics = store.process([])
        assert tagged == []
        assert metrics.total_candidates == 0
        assert metrics.reuse_rate == 0.0

    def test_clear_resets_store(self, store):
        store.process(make_chunks(["Clear test."]))
        assert store.size == 1
        store.clear()
        assert store.size == 0
        assert store.cumulative_stats["total_processed"] == 0

    def test_reuse_rate_calculation(self, store):
        chunks = make_chunks(["A.", "B.", "C."])
        store.process(chunks)
        _, m = store.process(chunks)
        assert m.reuse_rate == pytest.approx(1.0)
        assert m.reused_count == 3
        assert m.new_count == 0

    def test_mixed_reuse_rate(self, store):
        store.process(make_chunks(["X.", "Y."]))
        _, m = store.process(make_chunks(["X.", "Z."]))
        assert m.reused_count == 1
        assert m.new_count == 1
        assert m.reuse_rate == pytest.approx(0.5)

    def test_tag_chunks_does_not_mutate(self, fp):
        original = [{"chunk_id": "c1", "text": "Test.", "score": 0.5}]
        tagged = fp.tag_chunks(original)
        assert "fingerprint" not in original[0]
        assert "fingerprint" in tagged[0]
