"""
app/llm/ollama_provider.py

Aryntra Synapse — Sprint 1
Isolated LLM layer with pluggable context representation.

Responsibilities:
- Accept a question and retrieved chunks
- Delegate context representation to ContextRepresenter
- Construct a generic RAG prompt
- Call Ollama
- Return the answer, generation latency, and representation metadata
"""

import time
import ollama
from app.core.config import settings
from app.context.representation import BaseContextRepresenter, get_representer


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
    Legacy Sprint 0.2 flat assembly function preserved for reference and equivalence testing.
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
    """

    def __init__(
        self,
        model: str = settings.llm_model,
        host: str = settings.ollama_host,
        representer: BaseContextRepresenter = None,
    ):
        self.model = model
        self._client = ollama.Client(host=host)
        self.representer = representer or get_representer()

    def generate(
        self,
        question: str,
        retrieved_chunks: list[dict],
    ) -> dict:
        """
        Generate an answer from a question and retrieved context chunks.
        """
        represented = self.representer.represent(question, retrieved_chunks)
        context = represented["context_string"]

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
            "answer": answer,
            "generation_latency": round(generation_latency, 4),
            "context_length": len(context),
            "model": self.model,
            "representation_type": represented["representation_type"],
            "representation_metadata": represented["representation_metadata"],
            "representation_build_latency": represented["build_latency"],
        }
