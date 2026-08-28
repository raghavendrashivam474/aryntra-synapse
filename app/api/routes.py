import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.llm.ollama_provider import OllamaProvider
from app.core.config import settings

# S7: Cross-query evidence reuse
from app.context.evidence_store import EvidenceStore

# S8 / S9: Evidence Priority Engine with Optimization
from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.optimization.embedding_cache import EmbeddingCache
from app.optimization.semantic_gate import LexicalSemanticGate

router = APIRouter()

_retriever = Retriever()
_llm = OllamaProvider()
_evidence_store = EvidenceStore()  # S7: persistent across queries

# S9 Caches & Fast-path Gate
_query_cache = EmbeddingCache(max_entries=settings.embedding_cache_max_entries) if settings.enable_query_embedding_cache else None
_evidence_cache = EmbeddingCache(max_entries=settings.embedding_cache_max_entries) if settings.enable_evidence_embedding_cache else None
_semantic_gate = LexicalSemanticGate(
    high_confidence=settings.lexical_gate_high_confidence,
    low_confidence=settings.lexical_gate_low_confidence,
) if settings.enable_lexical_semantic_gate else None

_priority_engine = EvidencePriorityEngine(
    embedding_model=_retriever._embedding_model,
    weights=EvidencePriorityWeights(
        semantic_weight=settings.priority_semantic_weight,
        lexical_weight=settings.priority_lexical_weight,
        reuse_weight=settings.priority_reuse_weight,
        high_threshold=settings.priority_high_threshold,
        medium_threshold=settings.priority_medium_threshold,
    ),
    query_cache=_query_cache,
    evidence_cache=_evidence_cache,
    semantic_gate=_semantic_gate,
)


def initialise_retriever() -> None:
    chunks = load_and_chunk(settings.sample_document)
    _retriever.index_chunks(chunks)


class AskRequest(BaseModel):
    text: str = Field(..., description="The question to ask.")
    top_k: int = Field(default=settings.top_k, ge=1)


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    # Optional S7 / S8 metadata
    fingerprint: Optional[str] = None
    evidence_status: Optional[str] = None
    priority_score: Optional[float] = None
    priority_class: Optional[str] = None
    semantic_score: Optional[float] = None
    lexical_score: Optional[float] = None
    reuse_score: Optional[float] = None


class AskResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: list[RetrievedChunk]
    retrieval_latency: float
    generation_latency: float
    total_latency: float
    context_length: int
    num_chunks_retrieved: int
    model: str
    representation_type: str = "flat"
    representation_metadata: dict = Field(default_factory=dict)
    representation_build_latency: float = 0.0
    expansion_steps: int = 0
    total_model_calls: int = 1
    initial_context_length: int = 0
    final_context_length: int = 0
    peak_context_length: int = 0
    cumulative_context_length: int = 0
    sufficiency_latency: float = 0.0
    new_context_length: int = 0
    repeated_context_length: int = 0
    workspace_active_chunks: int = 0
    workspace_available_chunks: int = 0
    promotion_history: list = Field(default_factory=list)
    reuse_ollama_context: bool = False
    # S5 additions
    stop_reason: str = "unknown"
    sufficiency_log: list = Field(default_factory=list)
    # S7 additions — Evidence Reuse
    evidence_reuse_enabled: bool = False
    total_evidence_candidates: int = 0
    unique_evidence_candidates: int = 0
    reused_evidence_count: int = 0
    new_evidence_count: int = 0
    reuse_rate: float = 0.0
    fingerprinting_latency: float = 0.0
    workspace_lookup_latency: float = 0.0
    evidence_store_size: int = 0
    # S8 additions — Evidence Priority
    enable_priority_routing: bool = True
    priority_latency: float = 0.0
    high_priority_count: int = 0
    medium_priority_count: int = 0
    low_priority_count: int = 0
    active_evidence_count: int = 0
    retained_evidence_count: int = 0
    average_priority_score: float = 0.0
    # S9 additions — Processing Efficiency Telemetry
    semantic_calls: int = 0
    semantic_cache_hits: int = 0
    semantic_cache_misses: int = 0
    query_cache_hits: int = 0
    query_cache_misses: int = 0
    lexical_fast_path_hits: int = 0
    semantic_fallback_count: int = 0
    semantic_latency: float = 0.0
    cache_lookup_latency: float = 0.0


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    retriever_ready: bool
    chunk_count: int
    embedding_model: str
    llm_model: str
    context_representation: str
    # S7
    evidence_reuse_enabled: bool = False
    evidence_store_size: int = 0
    # S8
    enable_priority_routing: bool = True
    # S9
    enable_query_embedding_cache: bool = True
    enable_evidence_embedding_cache: bool = True
    enable_lexical_semantic_gate: bool = True


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok", app_name=settings.app_name, version=settings.app_version,
        retriever_ready=_retriever.is_ready, chunk_count=_retriever.chunk_count,
        embedding_model=settings.embedding_model, llm_model=settings.llm_model,
        context_representation=settings.context_representation,
        evidence_reuse_enabled=settings.evidence_reuse_enabled,
        evidence_store_size=_evidence_store.size,
        enable_priority_routing=settings.enable_priority_routing,
        enable_query_embedding_cache=settings.enable_query_embedding_cache,
        enable_evidence_embedding_cache=settings.enable_evidence_embedding_cache,
        enable_lexical_semantic_gate=settings.enable_lexical_semantic_gate,
    )


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Question text cannot be empty.")
    if not _retriever.is_ready:
        raise HTTPException(status_code=503, detail="Retriever is not ready.")

    t0 = time.perf_counter()
    retrieval_result = _retriever.query(request.text, top_k=request.top_k)
    retrieved_chunks = retrieval_result["results"]
    retrieval_latency = retrieval_result["retrieval_latency"]

    # ── S7: Evidence Reuse ──────────────────────────────────────────
    reuse_metrics_dict = {
        "total_candidates": 0,
        "unique_candidates": 0,
        "reused_count": 0,
        "new_count": 0,
        "reuse_rate": 0.0,
        "fingerprinting_latency": 0.0,
        "lookup_latency": 0.0,
    }

    if settings.evidence_reuse_enabled:
        tagged_chunks, reuse_metrics = _evidence_store.process(retrieved_chunks)
        reuse_metrics_dict = reuse_metrics.to_dict()
        retrieved_chunks = tagged_chunks

    # ── S8 / S9: Evidence Priority Ranking ─────────────────────────
    priority_metrics_dict = {
        "priority_latency": 0.0,
        "high_priority_count": 0,
        "medium_priority_count": 0,
        "low_priority_count": 0,
        "active_evidence_count": 0,
        "retained_evidence_count": 0,
        "average_priority_score": 0.0,
        "semantic_calls": 0,
        "semantic_cache_hits": 0,
        "semantic_cache_misses": 0,
        "query_cache_hits": 0,
        "query_cache_misses": 0,
        "lexical_fast_path_hits": 0,
        "semantic_fallback_count": 0,
        "semantic_latency": 0.0,
        "cache_lookup_latency": 0.0,
    }

    if settings.enable_priority_routing:
        ranked_chunks, priority_metrics = _priority_engine.rank(request.text, retrieved_chunks)
        priority_metrics_dict = priority_metrics.to_dict()
        retrieved_chunks = ranked_chunks

    llm_result = _llm.generate(request.text, retrieved_chunks)
    total_latency = round(time.perf_counter() - t0, 4)

    return AskResponse(
        question=request.text, answer=llm_result["answer"],
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                score=c["score"],
                fingerprint=c.get("fingerprint"),
                evidence_status=c.get("evidence_status"),
                priority_score=c.get("priority_score"),
                priority_class=c.get("priority_class"),
                semantic_score=c.get("semantic_score"),
                lexical_score=c.get("lexical_score"),
                reuse_score=c.get("reuse_score"),
            )
            for c in retrieved_chunks
        ],
        retrieval_latency=retrieval_latency,
        generation_latency=llm_result["generation_latency"],
        total_latency=total_latency,
        context_length=llm_result["context_length"],
        num_chunks_retrieved=len(retrieved_chunks),
        model=llm_result["model"],
        representation_type=llm_result.get("representation_type", "flat"),
        representation_metadata=llm_result.get("representation_metadata", {}),
        representation_build_latency=llm_result.get("representation_build_latency", 0.0),
        expansion_steps=llm_result.get("expansion_steps", 0),
        total_model_calls=llm_result.get("total_model_calls", 1),
        initial_context_length=llm_result.get("initial_context_length", 0),
        final_context_length=llm_result.get("final_context_length", 0),
        peak_context_length=llm_result.get("peak_context_length", 0),
        cumulative_context_length=llm_result.get("cumulative_context_length", 0),
        sufficiency_latency=llm_result.get("sufficiency_latency", 0.0),
        new_context_length=llm_result.get("new_context_length", 0),
        repeated_context_length=llm_result.get("repeated_context_length", 0),
        workspace_active_chunks=llm_result.get("workspace_active_chunks", 0),
        workspace_available_chunks=llm_result.get("workspace_available_chunks", 0),
        promotion_history=llm_result.get("promotion_history", []),
        reuse_ollama_context=llm_result.get("reuse_ollama_context", False),
        stop_reason=llm_result.get("stop_reason", "unknown"),
        sufficiency_log=llm_result.get("sufficiency_log", []),
        # S7 fields
        evidence_reuse_enabled=settings.evidence_reuse_enabled,
        total_evidence_candidates=reuse_metrics_dict["total_candidates"],
        unique_evidence_candidates=reuse_metrics_dict["unique_candidates"],
        reused_evidence_count=reuse_metrics_dict["reused_count"],
        new_evidence_count=reuse_metrics_dict["new_count"],
        reuse_rate=reuse_metrics_dict["reuse_rate"],
        fingerprinting_latency=reuse_metrics_dict["fingerprinting_latency"],
        workspace_lookup_latency=reuse_metrics_dict["lookup_latency"],
        evidence_store_size=_evidence_store.size,
        # S8 fields
        enable_priority_routing=settings.enable_priority_routing,
        priority_latency=priority_metrics_dict["priority_latency"],
        high_priority_count=priority_metrics_dict["high_priority_count"],
        medium_priority_count=priority_metrics_dict["medium_priority_count"],
        low_priority_count=priority_metrics_dict["low_priority_count"],
        active_evidence_count=priority_metrics_dict["active_evidence_count"],
        retained_evidence_count=priority_metrics_dict["retained_evidence_count"],
        average_priority_score=priority_metrics_dict["average_priority_score"],
        # S9 fields
        semantic_calls=priority_metrics_dict["semantic_calls"],
        semantic_cache_hits=priority_metrics_dict["semantic_cache_hits"],
        semantic_cache_misses=priority_metrics_dict["semantic_cache_misses"],
        query_cache_hits=priority_metrics_dict["query_cache_hits"],
        query_cache_misses=priority_metrics_dict["query_cache_misses"],
        lexical_fast_path_hits=priority_metrics_dict["lexical_fast_path_hits"],
        semantic_fallback_count=priority_metrics_dict["semantic_fallback_count"],
        semantic_latency=priority_metrics_dict["semantic_latency"],
        cache_lookup_latency=priority_metrics_dict["cache_lookup_latency"],
    )
