"""
SC-S4 Live Comparison API Server.

Minimal FastAPI service that executes both the lexical baseline
and the Aryntra Synapse UnifiedEvidenceEngine against the fixed
two-policy corpus, compares their outputs, and returns structured
results through the ADR-001 contract.

Start (from repository root):
    uvicorn experiments.synapse_compare.server.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path setup — required because baseline.py and synapse_adapter.py
# use bare imports that depend on their own directories being on sys.path.
# ---------------------------------------------------------------------------
SERVER_DIR = Path(__file__).resolve().parent
SC_DIR = SERVER_DIR.parent                # experiments/synapse_compare
SC_S1_DIR = SC_DIR / "sc_s1"
SC_S2_DIR = SC_DIR / "sc_s2"
REPO_ROOT = SC_DIR.parents[1]

for _p in [str(SC_S1_DIR), str(SC_S2_DIR), str(REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- Engine imports (after sys.path setup) ---
from baseline import load_corpus, retrieve                     # sc_s1
from schemas import (                                          # sc_s1
    ExperimentResult,
    DecisionInfo,
    EvaluationInfo,
    SCHEMA_VERSION,
    EXPERIMENT_ID,
    EXPECTED_CURRENT_DOCUMENT,
    SYSTEM_LABEL as BASELINE_LABEL,
)
from synapse_adapter import (                                  # sc_s2
    map_to_synapse_format,
    run_synapse_engine,
    normalize_engine_result,
    build_error_result,
    SYSTEM_LABEL as SYNAPSE_LABEL,
)
from comparison import compare as run_comparison               # sc_s2

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Synapse Compare — Live Engine API",
    version="0.1.0",
    description="SC-S4 live comparison of lexical baseline vs Aryntra Synapse.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Corpus — loaded once at startup from the canonical SC-S1 fixtures
# ---------------------------------------------------------------------------
FIXTURE_DIR = SC_S1_DIR / "fixtures"
_documents: list[dict] = load_corpus(FIXTURE_DIR)
_corpus_ids: list[str] = [d["document_id"] for d in _documents]


# ---------------------------------------------------------------------------
# Request / Response models  (ADR-001 contract)
# ---------------------------------------------------------------------------
class CompareRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language query to execute against both engines.",
    )
    top_k: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of documents for baseline retrieval.",
    )


class CompareResponse(BaseModel):
    run_id: str
    mode: str = "live"
    query: str
    corpus: dict[str, Any]
    baseline: dict[str, Any]
    synapse: dict[str, Any]
    comparison: dict[str, Any]
    evaluation: dict[str, Any]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/v1/compare", response_model=CompareResponse)
def compare_engines(request: CompareRequest) -> CompareResponse:
    """Execute both engines on the custom query and return comparison."""

    query = request.query.strip()
    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query must not be empty or whitespace-only.",
        )

    run_id = f"live-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()

    # ---- Baseline execution ----
    baseline_result: Optional[dict] = None
    baseline_error: Optional[str] = None
    baseline_status = "success"

    try:
        retrieval = retrieve(query, _documents, top_k=request.top_k)
        top_doc_id = retrieval.results[0].document_id
        top_doc = next(
            d for d in _documents if d["document_id"] == top_doc_id
        )
        decision = DecisionInfo(
            selected_evidence=[top_doc_id],
            output=(
                f"Based on top-ranked evidence ({top_doc_id}): "
                f"{top_doc['content']}"
            ),
        )
        selected_is_current = top_doc_id == EXPECTED_CURRENT_DOCUMENT
        evaluation = EvaluationInfo(
            expected_current_document=EXPECTED_CURRENT_DOCUMENT,
            selected_current_document=selected_is_current,
            status="PASS" if selected_is_current else "FAIL",
        )
        exp_result = ExperimentResult(
            schema_version=SCHEMA_VERSION,
            experiment_id=EXPERIMENT_ID,
            system=BASELINE_LABEL,
            query=query,
            corpus_documents=_corpus_ids,
            retrieval=retrieval,
            decision=decision,
            evaluation=evaluation,
        )
        baseline_result = exp_result.to_dict()
    except Exception as exc:
        baseline_status = "error"
        baseline_error = f"{type(exc).__name__}: {exc}"

    # ---- Synapse execution ----
    synapse_result: Optional[dict] = None
    synapse_error: Optional[str] = None
    synapse_status = "success"

    try:
        synapse_corpus = map_to_synapse_format(_documents)
        engine_result = run_synapse_engine(query, synapse_corpus)
        synapse_result = normalize_engine_result(engine_result, _documents)
    except Exception as exc:
        synapse_status = "error"
        synapse_error = f"{type(exc).__name__}: {exc}"
        synapse_result = build_error_result(query, exc)

    # ---- Comparison ----
    comparison_status = "not_available"
    comparison_result: dict[str, Any] = {}

    if (
        baseline_result is not None
        and synapse_status == "success"
        and synapse_result is not None
    ):
        try:
            comp = run_comparison(baseline_result, synapse_result)
            comparison_result = comp.to_dict()
            comparison_status = "completed"
        except Exception:
            comparison_status = "error"
    elif baseline_status == "error" and synapse_status == "error":
        comparison_status = "not_available"
    else:
        comparison_status = "partial"

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    return CompareResponse(
        run_id=run_id,
        mode="live",
        query=query,
        corpus={
            "id": "existing-policy-corpus",
            "version": "1.0",
            "documents": _corpus_ids,
        },
        baseline={
            "execution_status": baseline_status,
            "result": baseline_result,
            "error": baseline_error,
        },
        synapse={
            "execution_status": synapse_status,
            "result": synapse_result,
            "error": synapse_error,
        },
        comparison={
            "status": comparison_status,
            "result": comparison_result,
        },
        evaluation={
            "status": "not_applicable",
            "reason": "No applicable ground truth for custom queries.",
            "ground_truth_id": None,
            "metrics": None,
        },
        metadata={
            "baseline_engine": "lexical_token_overlap",
            "synapse_engine": "UnifiedEvidenceEngine",
            "corpus_documents": _corpus_ids,
            "execution_time_ms": elapsed_ms,
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "synapse-compare-live",
        "corpus_loaded": len(_documents),
        "documents": _corpus_ids,
    }
