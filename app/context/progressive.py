import time
import logging
from typing import List, Dict, Any, Tuple
from app.context.compressor import build_compressed_context

logger = logging.getLogger(__name__)

MAX_EXPANSION_STEPS = 2
INITIAL_CHUNK_COUNT = 1

SUFFICIENCY_PROMPT_TEMPLATE = (
    "Given the following evidence and the user's question, "
    "do you have enough information to provide a complete and accurate answer?\n\n"
    "Question: {query}\n\n"
    "Evidence:\n{context}\n\n"
    "Respond with exactly one word: SUFFICIENT or INSUFFICIENT"
)


class ProgressiveContextEngine:
    """
    Bounded progressive context expansion engine.
    Operates strictly post-retrieval on already retrieved Top-K chunks.
    """

    def __init__(
        self,
        llm_provider,
        max_steps: int = MAX_EXPANSION_STEPS,
        initial_chunks: int = INITIAL_CHUNK_COUNT,
        max_chunk_chars: int = 400,
        dedup_threshold: float = 0.90,
    ):
        self.llm = llm_provider
        self.max_steps = max_steps
        self.initial_chunks = initial_chunks
        self.max_chunk_chars = max_chunk_chars
        self.dedup_threshold = dedup_threshold

    def build_stage_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Compress and format the active subset of chunks."""
        return build_compressed_context(
            chunks=chunks,
            max_chunk_chars=self.max_chunk_chars,
            dedup_threshold=self.dedup_threshold,
        )

    def evaluate_sufficiency(self, query: str, context: str) -> Tuple[bool, str, float]:
        """
        Prompt LLM to determine if active context is sufficient.
        Returns: (is_sufficient, raw_judgment, latency)
        """
        prompt = SUFFICIENCY_PROMPT_TEMPLATE.format(query=query, context=context)
        t0 = time.perf_counter()
        raw_judgment = self.llm.generate_raw(prompt)
        latency = round(time.perf_counter() - t0, 4)

        clean = raw_judgment.strip().upper()
        # Decision rule: SUFFICIENT must be present and INSUFFICIENT absent
        is_sufficient = ("SUFFICIENT" in clean) and ("INSUFFICIENT" not in clean)
        return is_sufficient, clean, latency

    def run(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Execute the progressive context lifecycle loop.
        """
        total_retrieved = len(retrieved_chunks)
        if total_retrieved == 0:
            return {
                "final_chunks": [],
                "context_string": "No relevant context found.",
                "expansion_steps": 0,
                "total_model_calls": 0,
                "initial_context_length": 0,
                "final_context_length": 0,
                "peak_context_length": 0,
                "cumulative_context_length": 0,
                "initial_context_chunks": 0,
                "final_context_chunks": 0,
                "sufficiency_latency": 0.0,
                "stages": [],
            }

        current_count = min(self.initial_chunks, total_retrieved)
        stages = []
        total_model_calls = 0
        cumulative_context_length = 0
        peak_context_length = 0
        total_sufficiency_latency = 0.0
        expansion_steps = 0

        initial_context_length = 0
        initial_context_chunks = current_count

        while True:
            active_chunks = retrieved_chunks[:current_count]
            stage_context = self.build_stage_context(active_chunks)
            ctx_len = len(stage_context)

            peak_context_length = max(peak_context_length, ctx_len)
            cumulative_context_length += ctx_len

            if expansion_steps == 0:
                initial_context_length = ctx_len

            stage_info = {
                "stage": expansion_steps + 1,
                "chunks_exposed": current_count,
                "context_length": ctx_len,
            }

            # If all retrieved chunks are already active, no need to query sufficiency
            if current_count >= total_retrieved:
                stage_info["sufficiency"] = "MAX_CHUNKS_REACHED"
                stage_info["sufficiency_latency"] = 0.0
                stages.append(stage_info)
                break

            # If max steps exceeded
            if expansion_steps >= self.max_steps:
                stage_info["sufficiency"] = "MAX_STEPS_REACHED"
                stage_info["sufficiency_latency"] = 0.0
                stages.append(stage_info)
                break

            # Evaluate sufficiency
            total_model_calls += 1
            is_suff, raw_judg, suff_lat = self.evaluate_sufficiency(query, stage_context)
            total_sufficiency_latency += suff_lat

            stage_info["sufficiency"] = "SUFFICIENT" if is_suff else "INSUFFICIENT"
            stage_info["raw_judgment"] = raw_judg
            stage_info["sufficiency_latency"] = suff_lat
            stages.append(stage_info)

            if is_suff:
                break

            # Expand to next stage
            expansion_steps += 1
            current_count = min(current_count + 1, total_retrieved)

        # Final context construction
        final_active_chunks = retrieved_chunks[:current_count]
        final_context_string = self.build_stage_context(final_active_chunks)

        return {
            "final_chunks": final_active_chunks,
            "context_string": final_context_string,
            "expansion_steps": expansion_steps,
            "total_model_calls": total_model_calls,
            "initial_context_length": initial_context_length,
            "final_context_length": len(final_context_string),
            "peak_context_length": max(peak_context_length, len(final_context_string)),
            "cumulative_context_length": cumulative_context_length,
            "initial_context_chunks": initial_context_chunks,
            "final_context_chunks": current_count,
            "sufficiency_latency": round(total_sufficiency_latency, 4),
            "stages": stages,
        }