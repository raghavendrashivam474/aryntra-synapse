import time
import logging
import ollama
from app.core.config import settings
from app.context.representation import BaseContextRepresenter, get_representer
from app.context.progressive import ProgressiveContextEngine, SUFFICIENCY_PROMPT_TEMPLATE
from app.context.workspace import EvidenceWorkspace
from app.context.sufficiency import SufficiencyEngine, SemanticSufficiencyEngine
from app.context.semantic_gate import SemanticGate
from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.retrieval.embeddings import EmbeddingModel
from app.context.compressor import build_compressed_context

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the question using only the context provided below.
If the context does not contain enough information to answer the question, say so clearly.
Do not invent facts that are not supported by the context.

Context:
{context}

Question:
{question}

Answer:"""


def assemble_context(retrieved_chunks: list[dict]) -> str:
    """Legacy Sprint 0.2 flat assembly function preserved for equivalence testing."""
    if not retrieved_chunks:
        return "No relevant context found."
    parts = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        parts.append(f"[Chunk {i}]\n{chunk['text']}")
    return "\n\n".join(parts)


class OllamaProvider:
    """
    Thin wrapper around the Ollama Python client.
    Supports static, progressive (S3), workspace (S4), selective (S5),
    semantic/blended sufficiency modes (S6), and priority management (S8).
    """

    def __init__(
        self,
        model: str = settings.llm_model,
        host: str = settings.ollama_host,
        representer: BaseContextRepresenter = None,
        embedding_model: EmbeddingModel = None,
    ):
        self.model = model
        self._client = ollama.Client(host=host)
        rep_name = settings.context_representation
        if rep_name in (
            "progressive_v1",
            "evidence_workspace_v1",
            "selective_v1",
            "semantic_v1",
            "blended_v1",
            "priority_v1",
        ):
            rep_name = "compressed_v1"
        self.representer = representer or get_representer(rep_name)

        self.progressive_engine = ProgressiveContextEngine(
            llm_provider=self,
            max_steps=settings.max_expansion_steps,
            initial_chunks=settings.initial_chunk_count,
        )

        self.sufficiency_engine = SufficiencyEngine(
            score_threshold=settings.sufficiency_score_threshold,
            coverage_threshold=settings.sufficiency_coverage_threshold,
        )

        # S6/S8: Reuse embedding model or instantiate default
        self._embedder = embedding_model or EmbeddingModel()
        self.semantic_gate = SemanticGate(self._embedder)

        self.semantic_engine = SemanticSufficiencyEngine(
            lexical_engine=self.sufficiency_engine,
            semantic_gate=self.semantic_gate,
            semantic_threshold=settings.semantic_sufficiency_threshold,
            mode="semantic_only",
        )

        self.blended_engine = SemanticSufficiencyEngine(
            lexical_engine=self.sufficiency_engine,
            semantic_gate=self.semantic_gate,
            semantic_threshold=settings.semantic_sufficiency_threshold,
            mode="blended",
        )

        # S8: Priority weights and engine
        weights = EvidencePriorityWeights(
            semantic_weight=settings.priority_semantic_weight,
            lexical_weight=settings.priority_lexical_weight,
            reuse_weight=settings.priority_reuse_weight,
            high_threshold=settings.priority_high_threshold,
            medium_threshold=settings.priority_medium_threshold,
        )
        self.priority_engine = EvidencePriorityEngine(
            embedding_model=self._embedder,
            weights=weights,
        )

    def generate_raw(self, prompt: str, context: list = None) -> dict:
        """Direct model generation for arbitrary prompts."""
        kwargs = {"model": self.model, "prompt": prompt}
        if context is not None:
            kwargs["context"] = context
        response = self._client.generate(**kwargs)
        return {
            "text": response.get("response", "").strip(),
            "ollama_context": response.get("context"),
        }

    def generate(self, question: str, retrieved_chunks: list[dict]) -> dict:
        rep_type = settings.context_representation.lower().strip()

        if rep_type in ("semantic_v1", "blended_v1", "priority_v1"):
            mode = "blended_v1" if rep_type in ("blended_v1", "priority_v1") else "semantic_v1"
            return self._generate_semantic_aware(question, retrieved_chunks, mode=mode)
        elif rep_type == "selective_v1":
            return self._generate_selective(question, retrieved_chunks)
        elif rep_type == "evidence_workspace_v1":
            return self._generate_workspace(question, retrieved_chunks)
        elif rep_type == "progressive_v1":
            return self._generate_progressive(question, retrieved_chunks)
        else:
            return self._generate_static(question, retrieved_chunks)

    # ── S6 / S8: Semantic-Aware Sufficiency Mode ──

    def _generate_semantic_aware(
        self, question: str, retrieved_chunks: list[dict], mode: str = "blended_v1"
    ) -> dict:
        """
        S6 / S8 semantic-aware selective promotion.
        Evaluates evidence sufficiency using semantic similarity (semantic_v1)
        or a hybrid lexical+semantic signal (blended_v1).
        Zero LLM calls for sufficiency gate.
        """
        engine = self.blended_engine if mode == "blended_v1" else self.semantic_engine

        workspace = EvidenceWorkspace(
            chunks=retrieved_chunks,
            max_active=settings.max_active_chunks,
        )

        if settings.enable_priority_routing:
            workspace.promote_priority_initial(fallback_count=settings.initial_chunk_count)
        else:
            workspace.promote_initial(count=settings.initial_chunk_count)

        expansion_steps = 0
        stop_reason = "unknown"
        sufficiency_log = []

        while True:
            active = workspace.active()

            # Sufficiency Check (Zero LLM calls)
            suff_result = engine.evaluate(question, active)
            sufficiency_log.append(suff_result.to_dict())

            if suff_result.is_sufficient:
                stop_reason = "evidence_sufficient"
                break

            if not workspace.has_available():
                stop_reason = "no_more_evidence"
                break

            if expansion_steps >= settings.max_expansion_steps:
                stop_reason = "max_expansion_reached"
                break

            # Promote next chunk
            workspace.promote_next(reason=suff_result.reason)
            expansion_steps += 1

        # Final generation (exactly 1 LLM call)
        final_context = workspace.build_active_context()
        gen_prompt = PROMPT_TEMPLATE.format(
            context=final_context, question=question
        )

        total_model_calls = 1
        t0 = time.perf_counter()
        gen_result = self.generate_raw(gen_prompt)
        gen_latency = round(time.perf_counter() - t0, 4)
        answer = gen_result["text"]

        ws_summary = workspace.summary()
        final_ctx_len = len(final_context)

        return {
            "answer": answer,
            "generation_latency": gen_latency,
            "context_length": final_ctx_len,
            "model": self.model,
            "representation_type": mode,
            "representation_metadata": ws_summary,
            "representation_build_latency": 0.0,
            "expansion_steps": expansion_steps,
            "total_model_calls": total_model_calls,
            "initial_context_length": ws_summary["promotion_history"][0]["new_context_length"] if ws_summary["promotion_history"] else 0,
            "final_context_length": final_ctx_len,
            "peak_context_length": final_ctx_len,
            "cumulative_context_length": final_ctx_len,
            "sufficiency_latency": 0.0,
            "new_context_length": ws_summary["total_new_context"],
            "repeated_context_length": 0,
            "workspace_active_chunks": ws_summary["active_chunks"],
            "workspace_available_chunks": ws_summary["available_chunks"],
            "promotion_history": ws_summary["promotion_history"],
            "reuse_ollama_context": False,
            "stop_reason": stop_reason,
            "sufficiency_log": sufficiency_log,
        }

    # ── S5: Selective Promotion Mode ──

    def _generate_selective(
        self, question: str, retrieved_chunks: list[dict]
    ) -> dict:
        """
        S5 selective promotion: uses deterministic sufficiency signals
        instead of LLM-based sufficiency checks.
        """
        workspace = EvidenceWorkspace(
            chunks=retrieved_chunks,
            max_active=settings.max_active_chunks,
        )

        if settings.enable_priority_routing:
            workspace.promote_priority_initial(fallback_count=settings.initial_chunk_count)
        else:
            workspace.promote_initial(count=settings.initial_chunk_count)

        total_model_calls = 0
        expansion_steps = 0
        stop_reason = "unknown"
        sufficiency_log = []

        while True:
            active = workspace.active()

            # S5: Deterministic sufficiency check (NO LLM call)
            suff_result = self.sufficiency_engine.evaluate(question, active)
            sufficiency_log.append(suff_result.to_dict())

            if suff_result.is_sufficient:
                stop_reason = "evidence_sufficient"
                break

            if not workspace.has_available():
                stop_reason = "no_more_evidence"
                break

            if expansion_steps >= settings.max_expansion_steps:
                stop_reason = "max_expansion_reached"
                break

            # Promote next chunk
            workspace.promote_next(reason=suff_result.reason)
            expansion_steps += 1

        # Final generation (exactly 1 LLM call)
        final_context = workspace.build_active_context()
        gen_prompt = PROMPT_TEMPLATE.format(
            context=final_context, question=question
        )

        total_model_calls = 1
        t0 = time.perf_counter()
        gen_result = self.generate_raw(gen_prompt)
        gen_latency = round(time.perf_counter() - t0, 4)
        answer = gen_result["text"]

        ws_summary = workspace.summary()
        final_ctx_len = len(final_context)

        return {
            "answer": answer,
            "generation_latency": gen_latency,
            "context_length": final_ctx_len,
            "model": self.model,
            "representation_type": "selective_v1",
            "representation_metadata": ws_summary,
            "representation_build_latency": 0.0,
            "expansion_steps": expansion_steps,
            "total_model_calls": total_model_calls,
            "initial_context_length": ws_summary["promotion_history"][0]["new_context_length"] if ws_summary["promotion_history"] else 0,
            "final_context_length": final_ctx_len,
            "peak_context_length": final_ctx_len,
            "cumulative_context_length": final_ctx_len,
            "sufficiency_latency": 0.0,
            "new_context_length": ws_summary["total_new_context"],
            "repeated_context_length": 0,
            "workspace_active_chunks": ws_summary["active_chunks"],
            "workspace_available_chunks": ws_summary["available_chunks"],
            "promotion_history": ws_summary["promotion_history"],
            "reuse_ollama_context": False,
            "stop_reason": stop_reason,
            "sufficiency_log": sufficiency_log,
        }

    # ── S4: Evidence Workspace Mode (retained) ──

    def _generate_workspace(
        self, question: str, retrieved_chunks: list[dict]
    ) -> dict:
        workspace = EvidenceWorkspace(
            chunks=retrieved_chunks,
            max_active=settings.max_active_chunks,
        )
        workspace.promote_initial(count=settings.initial_chunk_count)
        total_model_calls = 0
        total_sufficiency_latency = 0.0
        expansion_steps = 0
        ollama_ctx = None
        reuse_active = settings.reuse_ollama_context

        while True:
            active_context = workspace.build_active_context()
            suff_prompt = SUFFICIENCY_PROMPT_TEMPLATE.format(
                query=question, context=active_context
            )
            total_model_calls += 1
            t0 = time.perf_counter()
            if reuse_active and ollama_ctx is not None:
                suff_result = self.generate_raw(suff_prompt, context=ollama_ctx)
            else:
                suff_result = self.generate_raw(suff_prompt)
            suff_latency = round(time.perf_counter() - t0, 4)
            total_sufficiency_latency += suff_latency
            if reuse_active:
                ollama_ctx = suff_result.get("ollama_context")
            clean = suff_result["text"].strip().upper()
            is_sufficient = ("SUFFICIENT" in clean) and ("INSUFFICIENT" not in clean)
            if is_sufficient or not workspace.has_available():
                break
            if expansion_steps >= settings.max_expansion_steps:
                break
            workspace.promote_next(reason="insufficient_evidence")
            expansion_steps += 1

        final_context = workspace.build_active_context()
        gen_prompt = PROMPT_TEMPLATE.format(context=final_context, question=question)
        total_model_calls += 1
        t0 = time.perf_counter()
        gen_result = self.generate_raw(gen_prompt)
        gen_latency = round(time.perf_counter() - t0, 4)
        answer = gen_result["text"]
        ws_summary = workspace.summary()
        final_ctx_len = len(final_context)

        return {
            "answer": answer,
            "generation_latency": gen_latency,
            "context_length": final_ctx_len,
            "model": self.model,
            "representation_type": "evidence_workspace_v1",
            "representation_metadata": ws_summary,
            "representation_build_latency": 0.0,
            "expansion_steps": expansion_steps,
            "total_model_calls": total_model_calls,
            "initial_context_length": ws_summary["promotion_history"][0]["new_context_length"] if ws_summary["promotion_history"] else 0,
            "final_context_length": final_ctx_len,
            "peak_context_length": final_ctx_len,
            "cumulative_context_length": ws_summary["total_new_context"] + ws_summary["total_repeated_context"] + final_ctx_len,
            "sufficiency_latency": total_sufficiency_latency,
            "new_context_length": ws_summary["total_new_context"],
            "repeated_context_length": ws_summary["total_repeated_context"],
            "workspace_active_chunks": ws_summary["active_chunks"],
            "workspace_available_chunks": ws_summary["available_chunks"],
            "promotion_history": ws_summary["promotion_history"],
            "reuse_ollama_context": reuse_active,
            "stop_reason": "max_expansion_reached",
            "sufficiency_log": [],
        }

    # ── S3: Progressive Mode (retained) ──

    def _generate_progressive(
        self, question: str, retrieved_chunks: list[dict]
    ) -> dict:
        prog_result = self.progressive_engine.run(question, retrieved_chunks)
        context = prog_result["context_string"]
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
        t0 = time.perf_counter()
        response = self._client.generate(model=self.model, prompt=prompt)
        gen_latency = round(time.perf_counter() - t0, 4)
        answer = response.get("response", "").strip()
        total_model_calls = prog_result["total_model_calls"] + 1
        final_cum = prog_result["cumulative_context_length"] + len(context)
        final_peak = max(prog_result["peak_context_length"], len(context))

        return {
            "answer": answer, "generation_latency": gen_latency,
            "context_length": len(context), "model": self.model,
            "representation_type": "progressive_v1",
            "representation_metadata": {"stages": prog_result["stages"]},
            "representation_build_latency": 0.0,
            "expansion_steps": prog_result["expansion_steps"],
            "total_model_calls": total_model_calls,
            "initial_context_length": prog_result["initial_context_length"],
            "final_context_length": prog_result["final_context_length"],
            "peak_context_length": final_peak,
            "cumulative_context_length": final_cum,
            "sufficiency_latency": prog_result["sufficiency_latency"],
            "new_context_length": 0, "repeated_context_length": 0,
            "workspace_active_chunks": 0, "workspace_available_chunks": 0,
            "promotion_history": [], "reuse_ollama_context": False,
            "stop_reason": "progressive_complete", "sufficiency_log": [],
        }

    # ── Static Mode (S0.2 / S1 / S2) ──

    def _generate_static(
        self, question: str, retrieved_chunks: list[dict]
    ) -> dict:
        represented = self.representer.represent(question, retrieved_chunks)
        context = represented["context_string"]
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
        t0 = time.perf_counter()
        response = self._client.generate(model=self.model, prompt=prompt)
        gen_latency = round(time.perf_counter() - t0, 4)
        answer = response.get("response", "").strip()
        ctx_len = len(context)

        return {
            "answer": answer, "generation_latency": gen_latency,
            "context_length": ctx_len, "model": self.model,
            "representation_type": represented["representation_type"],
            "representation_metadata": represented["representation_metadata"],
            "representation_build_latency": represented["build_latency"],
            "expansion_steps": 0, "total_model_calls": 1,
            "initial_context_length": ctx_len, "final_context_length": ctx_len,
            "peak_context_length": ctx_len, "cumulative_context_length": ctx_len,
            "sufficiency_latency": 0.0,
            "new_context_length": ctx_len, "repeated_context_length": 0,
            "workspace_active_chunks": 0, "workspace_available_chunks": 0,
            "promotion_history": [], "reuse_ollama_context": False,
            "stop_reason": "static", "sufficiency_log": [],
        }
