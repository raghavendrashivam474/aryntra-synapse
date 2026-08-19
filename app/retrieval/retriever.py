"""
app/retrieval/retriever.py

Aryntra Synapse — Sprint 0.2
FAISS index builder and query engine.

Responsibilities:
- Accept a list of chunk dicts
- Build a FAISS flat L2 index from their embeddings
- Accept a query string
- Return Top-K structured retrieval results

Retrieval result format:
    {
        "chunk_id": "doc1_chunk_003",
        "text":     "...",
        "score":    0.87
    }

This module knows nothing about FastAPI or LLMs.
It depends on EmbeddingModel and chunk dicts only.
"""

import time
import numpy as np
import faiss
from typing import List, Dict
from app.retrieval.embeddings import EmbeddingModel
from app.core.config import settings


class Retriever:
    """
    Builds a FAISS index from document chunks and retrieves
    the most relevant chunks for a given query.

    Usage
    -----
        retriever = Retriever()
        retriever.index_chunks(chunks)
        results = retriever.query("What is ...?", top_k=3)
    """

    def __init__(self, embedding_model: EmbeddingModel = None):
        self._embedding_model = embedding_model or EmbeddingModel()
        self._index = None
        self._chunks: List[Dict] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_chunks(self, chunks: List[Dict]) -> None:
        """
        Embed all chunks and build a FAISS flat L2 index.

        Parameters
        ----------
        chunks : list of dicts with keys "id" and "text"
        """
        if not chunks:
            self._index = None
            self._chunks = []
            return

        self._chunks = chunks
        texts = [chunk["text"] for chunk in chunks]
        vectors = self._embedding_model.embed_batch(texts)

        dimension = self._embedding_model.dimension
        self._index = faiss.IndexFlatL2(dimension)
        self._index.add(vectors)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        top_k: int = settings.top_k,
    ) -> Dict:
        """
        Retrieve the Top-K most similar chunks for a query string.

        Returns
        -------
        dict with keys:
            "results"           : list of retrieval result dicts
            "retrieval_latency" : seconds taken for this operation
        """
        if self._index is None or not self._chunks:
            return {
                "results": [],
                "retrieval_latency": 0.0,
            }

        # Clamp top_k to available chunks
        k = min(top_k, len(self._chunks))

        t0 = time.perf_counter()

        query_vector = self._embedding_model.embed(query_text)
        query_vector = query_vector.reshape(1, -1)

        distances, indices = self._index.search(query_vector, k)

        retrieval_latency = time.perf_counter() - t0

        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            # Convert L2 distance to a similarity-style score
            # Lower L2 distance = higher similarity
            score = float(1 / (1 + dist))
            results.append({
                "chunk_id": chunk["id"],
                "text":     chunk["text"],
                "score":    round(score, 4),
            })

        return {
            "results":           results,
            "retrieval_latency": round(retrieval_latency, 4),
        }

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._index is not None and len(self._chunks) > 0

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)
