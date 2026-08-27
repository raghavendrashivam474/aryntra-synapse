import time
import ollama
from app.core.config import settings
from app.context.representation import BaseContextRepresenter, get_representer
from app.context.progressive import ProgressiveContextEngine


PROMPT_TEMPLATE = """You are a helpful assistant. Answer the question using only the context provided below.
If the context does not contain enough information to answer the question, say so clearly.
Do not invent facts that are not supported by the context.

Context:
{context}

Question:
{question}

Answer:"""


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
        self.representer = representer or get_representer(
            "compressed_v1" if settings.context_representation == "progressive_v1" else settings.context_representation
        )
        self.progressive_engine = ProgressiveContextEngine(
            llm_provider=self,
            max_steps=settings.max_expansion_steps,
            initial_chunks=settings.initial_chunk_count,
        )

    def generate_raw(self, prompt: str) -> str:
        """Direct model generation for arbitrary prompts (e.g. sufficiency evaluation)."""
        response = self._client.generate(
            model=self.model,
            prompt=prompt,
        )
        return response.get("response", "").strip()

    def generate(
        self,
        question: str,
        retrieved_chunks: list[dict],
    ) -> dict:
        """
        Generate an answer from a question and retrieved context chunks.
        Supports both static representation pipelines and S3 progressive context expansion.
        """
        rep_type = settings.context_representation.lower().strip()

        if rep_type == "progressive_v1":
            # Execute Progressive Context Lifecycle
            prog_result = self.progressive_engine.run(question, retrieved_chunks)
            context = prog_result["context_string"]

            prompt = PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            )

            t0 = time.perf_counter()
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
            )
            gen_latency = round(time.perf_counter() - t0, 4)
            answer = response.get("response", "").strip()

            # Final generation call is added to cumulative context and model calls
            total_model_calls = prog_result["total_model_calls"] + 1
            final_cum_context = prog_result["cumulative_context_length"] + len(context)
            final_peak_context = max(prog_result["peak_context_length"], len(context))

            return {
                "answer": answer,
                "generation_latency": gen_latency,
                "context_length": len(context),
                "model": self.model,
                "representation_type": "progressive_v1",
                "representation_metadata": {
                    "stages": prog_result["stages"],
                    "initial_context_chunks": prog_result["initial_context_chunks"],
                    "final_context_chunks": prog_result["final_context_chunks"],
                },
                "representation_build_latency": 0.0,
                "expansion_steps": prog_result["expansion_steps"],
                "total_model_calls": total_model_calls,
                "initial_context_length": prog_result["initial_context_length"],
                "final_context_length": prog_result["final_context_length"],
                "peak_context_length": final_peak_context,
                "cumulative_context_length": final_cum_context,
                "sufficiency_latency": prog_result["sufficiency_latency"],
            }

        # Static representation mode (flat, structured_v1, compressed_v1)
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
        generation_latency = round(time.perf_counter() - t0, 4)
        answer = response.get("response", "").strip()

        return {
            "answer": answer,
            "generation_latency": generation_latency,
            "context_length": len(context),
            "model": self.model,
            "representation_type": represented["representation_type"],
            "representation_metadata": represented["representation_metadata"],
            "representation_build_latency": represented["build_latency"],
            "expansion_steps": 0,
            "total_model_calls": 1,
            "initial_context_length": len(context),
            "final_context_length": len(context),
            "peak_context_length": len(context),
            "cumulative_context_length": len(context),
            "sufficiency_latency": 0.0,
        }