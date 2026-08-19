"""
app/retrieval/embeddings.py

Aryntra Synapse — Sprint 0.2
Isolated embedding layer.

Responsibilities:
- Load a Sentence Transformer model
- Encode text strings into vectors

This module knows nothing about FAISS, chunking, FastAPI or LLMs.
It accepts text. It returns vectors. That is all.
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings


class EmbeddingModel:
    """
    Thin wrapper around a Sentence Transformer model.

    Usage
    -----
        model = EmbeddingModel()
        vector = model.embed("some text")
        vectors = model.embed_batch(["text one", "text two"])
    """

    def __init__(self, model_name: str = settings.embedding_model):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> np.ndarray:
        """
        Encode a single string into a float32 vector.

        Returns
        -------
        np.ndarray of shape (embedding_dim,)
        """
        vector = self._model.encode(text, convert_to_numpy=True)
        return vector.astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Encode a list of strings into a matrix of float32 vectors.

        Returns
        -------
        np.ndarray of shape (len(texts), embedding_dim)
        """
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return vectors.astype(np.float32)

    @property
    def dimension(self) -> int:
        """
        Return the embedding dimension for this model.
        Required when initialising the FAISS index.
        """
        return self._model.get_embedding_dimension()
