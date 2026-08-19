"""
tests/test_retrieval.py

Aryntra Synapse — Sprint 0.2
Retrieval layer tests.

Covers:
- Text loading
- Chunking behaviour
- Embedding generation
- FAISS index construction
- Query and result structure
- Edge cases
"""

import pytest
import numpy as np
from app.retrieval.chunking import load_text, chunk_text, load_and_chunk
from app.retrieval.embeddings import EmbeddingModel
from app.retrieval.retriever import Retriever
from app.core.config import settings


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------

class TestChunking:

    def test_chunk_text_returns_list(self):
        result = chunk_text("Hello world. This is a test document.")
        assert isinstance(result, list)

    def test_chunk_has_required_keys(self):
        result = chunk_text("Hello world. This is a test document.")
        assert len(result) > 0
        for chunk in result:
            assert "id" in chunk
            assert "text" in chunk

    def test_chunk_ids_are_unique(self):
        text = "word " * 300
        result = chunk_text(text)
        ids = [c["id"] for c in result]
        assert len(ids) == len(set(ids))

    def test_chunk_ids_use_doc_prefix(self):
        result = chunk_text("Hello world.", doc_id="testdoc")
        for chunk in result:
            assert chunk["id"].startswith("testdoc_chunk_")

    def test_empty_text_returns_empty_list(self):
        result = chunk_text("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = chunk_text("     \n\n   ")
        assert result == []

    def test_chunk_size_respected(self):
        text = "a" * 1000
        result = chunk_text(text, chunk_size=100, chunk_overlap=0)
        for chunk in result:
            assert len(chunk["text"]) <= 100

    def test_chunk_overlap_produces_more_chunks(self):
        text = "word " * 200
        no_overlap = chunk_text(text, chunk_size=100, chunk_overlap=0)
        with_overlap = chunk_text(text, chunk_size=100, chunk_overlap=50)
        assert len(with_overlap) >= len(no_overlap)

    def test_load_and_chunk_from_file(self):
        result = load_and_chunk(settings.sample_document)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_loaded_chunks_have_text(self):
        result = load_and_chunk(settings.sample_document)
        for chunk in result:
            assert chunk["text"].strip() != ""


# ---------------------------------------------------------------------------
# Embedding tests
# ---------------------------------------------------------------------------

class TestEmbeddings:

    @pytest.fixture(scope="class")
    @classmethod
    def model(cls):
        return EmbeddingModel()

    def test_embed_returns_array(self, model):
        vector = model.embed("test sentence")
        assert isinstance(vector, np.ndarray)

    def test_embed_dimension_matches_model(self, model):
        vector = model.embed("test sentence")
        assert vector.shape[0] == model.dimension

    def test_embed_batch_returns_matrix(self, model):
        texts = ["first sentence", "second sentence", "third sentence"]
        vectors = model.embed_batch(texts)
        assert isinstance(vectors, np.ndarray)
        assert vectors.shape[0] == len(texts)
        assert vectors.shape[1] == model.dimension

    def test_embed_dtype_is_float32(self, model):
        vector = model.embed("test")
        assert vector.dtype == np.float32


# ---------------------------------------------------------------------------
# Retriever tests
# ---------------------------------------------------------------------------

class TestRetriever:

    @pytest.fixture(scope="class")
    @classmethod
    def loaded_retriever(cls):
        retriever = Retriever()
        chunks = load_and_chunk(settings.sample_document)
        retriever.index_chunks(chunks)
        return retriever

    def test_retriever_is_ready_after_indexing(self, loaded_retriever):
        assert loaded_retriever.is_ready is True

    def test_chunk_count_is_positive(self, loaded_retriever):
        assert loaded_retriever.chunk_count > 0

    def test_query_returns_dict(self, loaded_retriever):
        result = loaded_retriever.query("What is FAISS?")
        assert isinstance(result, dict)

    def test_query_has_required_keys(self, loaded_retriever):
        result = loaded_retriever.query("What is FAISS?")
        assert "results" in result
        assert "retrieval_latency" in result

    def test_query_results_have_required_fields(self, loaded_retriever):
        result = loaded_retriever.query("What is FAISS?")
        for item in result["results"]:
            assert "chunk_id" in item
            assert "text" in item
            assert "score" in item

    def test_query_respects_top_k(self, loaded_retriever):
        result = loaded_retriever.query("What is RAG?", top_k=2)
        assert len(result["results"]) <= 2

    def test_query_top_k_one(self, loaded_retriever):
        result = loaded_retriever.query("What is Mistral?", top_k=1)
        assert len(result["results"]) == 1

    def test_query_top_k_exceeds_chunks(self, loaded_retriever):
        large_k = loaded_retriever.chunk_count + 100
        result = loaded_retriever.query("test", top_k=large_k)
        assert len(result["results"]) <= loaded_retriever.chunk_count

    def test_scores_are_positive(self, loaded_retriever):
        result = loaded_retriever.query("What is Ollama?")
        for item in result["results"]:
            assert item["score"] > 0

    def test_chunk_ids_correspond_to_real_chunks(self, loaded_retriever):
        result = loaded_retriever.query("What is chunking?")
        valid_ids = {c["id"] for c in loaded_retriever._chunks}
        for item in result["results"]:
            assert item["chunk_id"] in valid_ids

    def test_retrieval_latency_is_recorded(self, loaded_retriever):
        result = loaded_retriever.query("baseline")
        assert result["retrieval_latency"] >= 0.0

    def test_empty_retriever_returns_empty_results(self):
        empty_retriever = Retriever()
        result = empty_retriever.query("anything")
        assert result["results"] == []

    def test_empty_chunks_list(self):
        retriever = Retriever()
        retriever.index_chunks([])
        assert retriever.is_ready is False
