"""
tests/test_api.py

Aryntra Synapse — Sprint 0.2
API layer tests.

Covers:
- GET /health
- POST /ask
- Edge cases
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.api.routes import initialise_retriever


@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient with the retriever initialised.
    """
    initialise_retriever()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_is_ok(self, client):
        data = response = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_retriever_ready(self, client):
        data = client.get("/health").json()
        assert data["retriever_ready"] is True

    def test_health_chunk_count_positive(self, client):
        data = client.get("/health").json()
        assert data["chunk_count"] > 0

    def test_health_contains_model_info(self, client):
        data = client.get("/health").json()
        assert "embedding_model" in data
        assert "llm_model" in data


# ---------------------------------------------------------------------------
# Ask tests
# ---------------------------------------------------------------------------

class TestAsk:

    def test_ask_returns_200(self, client):
        response = client.post("/ask", json={"text": "What is RAG?"})
        assert response.status_code == 200

    def test_ask_response_contains_answer(self, client):
        data = client.post("/ask", json={"text": "What is FAISS?"}).json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_ask_response_contains_retrieved_chunks(self, client):
        data = client.post("/ask", json={"text": "What is Ollama?"}).json()
        assert "retrieved_chunks" in data
        assert isinstance(data["retrieved_chunks"], list)

    def test_ask_chunks_have_required_fields(self, client):
        data = client.post("/ask", json={"text": "What is Mistral?"}).json()
        for chunk in data["retrieved_chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "score" in chunk

    def test_ask_respects_top_k(self, client):
        data = client.post("/ask", json={"text": "chunking", "top_k": 2}).json()
        assert len(data["retrieved_chunks"]) <= 2

    def test_ask_top_k_one(self, client):
        data = client.post("/ask", json={"text": "baseline", "top_k": 1}).json()
        assert len(data["retrieved_chunks"]) == 1

    def test_ask_contains_latency_fields(self, client):
        data = client.post("/ask", json={"text": "What is RAG?"}).json()
        assert "retrieval_latency" in data
        assert "generation_latency" in data
        assert "total_latency" in data

    def test_ask_latencies_are_non_negative(self, client):
        data = client.post("/ask", json={"text": "What is RAG?"}).json()
        assert data["retrieval_latency"] >= 0
        assert data["generation_latency"] >= 0
        assert data["total_latency"] >= 0

    def test_ask_contains_context_length(self, client):
        data = client.post("/ask", json={"text": "What is RAG?"}).json()
        assert "context_length" in data
        assert data["context_length"] > 0

    def test_ask_contains_model_name(self, client):
        data = client.post("/ask", json={"text": "What is RAG?"}).json()
        assert "model" in data

    def test_ask_num_chunks_retrieved_matches(self, client):
        data = client.post("/ask", json={"text": "What is RAG?", "top_k": 3}).json()
        assert data["num_chunks_retrieved"] == len(data["retrieved_chunks"])


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_question_returns_400(self, client):
        response = client.post("/ask", json={"text": ""})
        assert response.status_code == 400

    def test_whitespace_question_returns_400(self, client):
        response = client.post("/ask", json={"text": "   "})
        assert response.status_code == 400

    def test_no_obvious_match_still_returns_chunks(self, client):
        data = client.post(
            "/ask",
            json={"text": "xkqzwpvmbn gibberish query zzzzz"}
        ).json()
        assert isinstance(data["retrieved_chunks"], list)

    def test_top_k_exceeds_chunk_count_does_not_crash(self, client):
        response = client.post("/ask", json={"text": "What is RAG?", "top_k": 9999})
        assert response.status_code == 200
