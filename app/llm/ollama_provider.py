"""
app/llm/ollama_provider.py

Aryntra Synapse — Sprint 0.2
Isolated LLM layer.

Responsibilities:
- Accept a question and a context string
- Construct a generic RAG prompt
- Call Ollama
- Return the answer and generation latency

This module knows nothing about retrieval, FAISS, chunking or FastAPI.
It receives a question and a context string. It returns an answer.
"""

import time
import ollama
from app.core.config import settings


PROMPT_TEMPLATE = """\
You are a helpful assistant. Answer the question using only the context provided below.
If the context does not contain enough information to answer the question, say so clearly.
Do not invent facts that are not supported by the context.

Context:
{context}

Question:
{question}

Answer:"""


def assemble_context(retrieved_chunks: list[dict]) -> str:
    """
    Convert a list of retrieval result dicts into a plain context string.

    This is intentionally simple — the baseline concatenates Top-K chunks
    with labeled separators. No compression, no summarisation, no ranking.

    Parameters
    ----------
    retrieved_chunks : list of dicts with at least a "text" key

    Returns
    -------
    Formatted context string.
    """
    if not retrieved_chunks:
        return "No relevant context found."

    parts = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        parts.append(f"[Chunk {i}]\n{chunk['text']}")

    return "\n\n".join(parts)


class OllamaProvider:
    """
    Thin wrapper around the Ollama Python client.

    Usage
    -----
        provider = OllamaProvider()
        result = provider.generate(question, retrieved_chunks)
    """

    def __init__(
        self,
        model: str = settings.llm_model,
        host: str = settings.ollama_host,
    ):
        self.model = model
        self._client = ollama.Client(host=host)

    def generate(
        self,
        question: str,
        retrieved_chunks: list[dict],
    ) -> dict:
        """
        Generate an answer from a question and retrieved context chunks.

        Parameters
        ----------
        question         : the user question string
        retrieved_chunks : list of retrieval result dicts

        Returns
        -------
        dict with keys:
            "answer"              : generated answer string
            "generation_latency"  : seconds taken for generation
            "context_length"      : character length of assembled context
            "model"               : model name used
        """
        context = assemble_context(retrieved_chunks)
        prompt = PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        t0 = time.perf_counter()

        response = self._client.generate(
            model=self.model,
            prompt=prompt,
        )

        generation_latency = time.perf_counter() - t0

        answer = response.get("response", "").strip()

        return {
            "answer":             answer,
            "generation_latency": round(generation_latency, 4),
            "context_length":     len(context),
            "model":              self.model,
        }
