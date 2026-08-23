"""
tests/test_representation.py

Sprint 1 test suite for context representation.
Verifies equivalence of FlatRepresenter with assemble_context() and
validates StructuredRepresenterV1 functionality.
"""

import pytest
from app.context.representation import (
    FlatRepresenter,
    StructuredRepresenterV1,
    get_representer,
)
from app.llm.ollama_provider import assemble_context


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "doc1_chunk_001",
            "text": "Sentence Transformers produce dense embeddings for FAISS search.",
            "score": 0.85,
        },
        {
            "chunk_id": "doc1_chunk_002",
            "text": "FAISS index enables rapid similarity retrieval over embeddings.",
            "score": 0.78,
        },
    ]


def test_flat_representer_byte_identical_equivalence(sample_chunks):
    """Verify FlatRepresenter produces byte-identical context to assemble_context."""
    flat_rep = FlatRepresenter()
    result = flat_rep.represent("test query", sample_chunks)
    legacy_context = assemble_context(sample_chunks)

    assert result["context_string"] == legacy_context
    assert result["representation_type"] == "flat"
    assert result["representation_metadata"] == {}
    assert result["build_latency"] >= 0.0


def test_flat_representer_empty_chunks():
    flat_rep = FlatRepresenter()
    result = flat_rep.represent("test", [])
    assert result["context_string"] == "No relevant context found."
    assert result["representation_type"] == "flat"


def test_structured_representer_structure_and_continuity(sample_chunks):
    """Verify StructuredRepresenterV1 discovers sequential adjacency and shared keywords."""
    struct_rep = StructuredRepresenterV1()
    result = struct_rep.represent("test query", sample_chunks)

    assert result["representation_type"] == "structured_v1"
    assert "=== Structured Context Relationships ===" in result["context_string"]
    assert "=== Retrieved Evidence ===" in result["context_string"]
    assert "doc1_chunk_001" in result["context_string"]
    assert "doc1_chunk_002" in result["context_string"]

    meta = result["representation_metadata"]
    assert len(meta["nodes"]) == 2

    # doc1_chunk_001 is followed by doc1_chunk_002
    seq_edges = [e for e in meta["edges"] if e["relation"] == "immediately_precedes"]
    assert len(seq_edges) == 1
    assert seq_edges[0]["source"] == "doc1_chunk_001"
    assert seq_edges[0]["target"] == "doc1_chunk_002"


def test_structured_representer_empty_chunks():
    struct_rep = StructuredRepresenterV1()
    result = struct_rep.represent("test", [])
    assert result["context_string"] == "No relevant context found."
    assert result["representation_metadata"] == {"nodes": [], "edges": []}


def test_get_representer_factory():
    flat = get_representer("flat")
    assert isinstance(flat, FlatRepresenter)

    struct = get_representer("structured_v1")
    assert isinstance(struct, StructuredRepresenterV1)

    with pytest.raises(ValueError):
        get_representer("unknown_strategy")
