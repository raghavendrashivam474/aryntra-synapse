import pytest
from app.context.workspace import EvidenceWorkspace


def make_chunks(n=3):
    texts = [
        "Paris is the capital of France and a major European cultural center.",
        "Albert Einstein developed the theory of general relativity in 1915.",
        "Photosynthesis converts light energy into chemical energy in plants.",
    ]
    return [
        {"chunk_id": f"doc_chunk_{i}", "text": texts[i - 1], "score": round(0.95 - i * 0.1, 4)}
        for i in range(1, min(n + 1, len(texts) + 1))
    ]


def test_workspace_creation():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks)
    assert ws.active_count == 0
    assert ws.available_count == 3


def test_initial_active_state():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks)
    ws.promote_initial(count=1)
    assert ws.active_count == 1
    assert ws.available_count == 2
    assert ws.is_active("doc_chunk_1")
    assert not ws.is_active("doc_chunk_2")


def test_promotion_order():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks)
    ws.promote_initial(count=1)
    event = ws.promote_next(reason="test")
    assert event is not None
    assert event.chunk_id == "doc_chunk_2"
    assert event.previous_active_count == 1
    assert event.new_active_count == 2


def test_duplicate_prevention():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks)
    ws.promote_initial(count=1)
    assert ws.is_active("doc_chunk_1")
    # doc_chunk_1 is no longer in available
    available_ids = [c["chunk_id"] for c in ws.available()]
    assert "doc_chunk_1" not in available_ids


def test_isolation():
    chunks_a = make_chunks(3)
    chunks_b = make_chunks(3)
    ws_a = EvidenceWorkspace(chunks_a)
    ws_b = EvidenceWorkspace(chunks_b)
    ws_a.promote_initial(count=2)
    assert ws_a.active_count == 2
    assert ws_b.active_count == 0


def test_bounds():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks, max_active=2)
    ws.promote_initial(count=1)
    ws.promote_next()
    assert ws.active_count == 2
    assert not ws.has_available()
    event = ws.promote_next()
    assert event is None


def test_determinism():
    chunks = make_chunks(3)
    ws1 = EvidenceWorkspace(chunks)
    ws1.promote_initial(count=1)
    ws1.promote_next()
    
    ws2 = EvidenceWorkspace(chunks)
    ws2.promote_initial(count=1)
    ws2.promote_next()
    
    s1 = ws1.summary()
    s2 = ws2.summary()
    
    # Strip latency values to compare structural determinism
    for h in s1["promotion_history"]:
        h["latency"] = 0.0
    for h in s2["promotion_history"]:
        h["latency"] = 0.0
        
    assert s1 == s2


def test_empty_evidence():
    ws = EvidenceWorkspace([])
    assert ws.active_count == 0
    assert ws.available_count == 0
    assert not ws.has_available()
    event = ws.promote_next()
    assert event is None


def test_reuse_accounting():
    chunks = make_chunks(3)
    ws = EvidenceWorkspace(chunks)
    ws.promote_initial(count=1)
    ws.promote_next(reason="test")
    summary = ws.summary()
    assert summary["total_new_context"] > 0
    assert summary["total_repeated_context"] >= 0
    assert summary["promotion_count"] == 2
