import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.llm.ollama_provider import OllamaProvider
from app.core.config import settings

router = APIRouter()

_retriever = Retriever()
_llm = OllamaProvider()


def initialise_retriever() -> None:
    """Load the sample document, chunk it, and build the FAISS index."""
    chunks = load_and_chunk(settings.sample_document)
    _retriever.index_chunks(chunks)


class AskRequest(BaseModel):
    text: str = Field(..., description="The question to ask.")
    top_k: int = Field(
        default=settings.top_k,
        ge=1,
        description="Number of chunks to retrieve.",
    )


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float


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
    # S3 Progressive Context Additions
    expansion_steps: int = 0
    total_model_calls: int = 1
    initial_context_length: int = 0
    final_context_length: int = 0
    peak_context_length: int = 0
    cumulative_context_length: int = 0
    sufficiency_latency: float = 0.0


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    retriever_ready: bool
    chunk_count: int
    embedding_model: str
    llm_model: str
    context_representation: str


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        retriever_ready=_retriever.is_ready,
        chunk_count=_retriever.chunk_count,
        embedding_model=settings.embedding_model,
        llm_model=settings.llm_model,
        context_representation=settings.context_representation,
    )


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Question text cannot be empty.")

    if not _retriever.is_ready:
        raise HTTPException(status_code=503, detail="Retriever is not ready. No documents indexed.")

    t0 = time.perf_counter()

    # Retrieval
    retrieval_result = _retriever.query(request.text, top_k=request.top_k)
    retrieved_chunks = retrieval_result["results"]
    retrieval_latency = retrieval_result["retrieval_latency"]

    # Generation
    llm_result = _llm.generate(request.text, retrieved_chunks)

    total_latency = round(time.perf_counter() - t0, 4)

    return AskResponse(
        question=request.text,
        answer=llm_result["answer"],
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                score=c["score"],
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
        initial_context_length=llm_result.get("initial_context_length", llm_result["context_length"]),
        final_context_length=llm_result.get("final_context_length", llm_result["context_length"]),
        peak_context_length=llm_result.get("peak_context_length", llm_result["context_length"]),
        cumulative_context_length=llm_result.get("cumulative_context_length", llm_result["context_length"]),
        sufficiency_latency=llm_result.get("sufficiency_latency", 0.0),
    )