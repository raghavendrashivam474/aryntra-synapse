"""
SC-S2 Synapse Adapter.

Loads the canonical SC-S1 fixtures, maps them to the format expected
by UnifiedEvidenceEngine, invokes the real engine, and normalizes
the response into a structured result for comparison.

This adapter does NOT select evidence on behalf of Synapse.
It delegates all reasoning to the actual engine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is importable
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evidence.unified import UnifiedEvidenceEngine, UnifiedProcessResult

# ---------------------------------------------------------------------------
# Paths to canonical SC-S1 fixtures (reused, not duplicated)
# ---------------------------------------------------------------------------
SC_S1_FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent / "sc_s1" / "fixtures"
)

# ---------------------------------------------------------------------------
# Scenario constants (must match SC-S1 exactly)
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "SC-S1-TEMPORAL-001"
QUERY = (
    "What authentication policy is currently in effect "
    "for internal systems?"
)
EXPECTED_CURRENT_DOCUMENT = "AUTH-POLICY-V2"
SYSTEM_LABEL = "synapse"


# ---------------------------------------------------------------------------
# Fixture loading (reuses SC-S1 canonical fixtures)
# ---------------------------------------------------------------------------
def load_sc_s1_fixtures(fixture_dir: Path = SC_S1_FIXTURE_DIR) -> list[dict]:
    """Load the canonical SC-S1 policy fixtures.

    Returns the raw fixture dicts with their original field names
    (document_id, version, publication_date, status, content, supersedes).
    """
    if not fixture_dir.is_dir():
        raise FileNotFoundError(
            f"SC-S1 fixture directory not found: {fixture_dir}"
        )

    required_keys = {
        "document_id", "version", "publication_date",
        "status", "content",
    }
    documents: list[dict] = []

    for path in sorted(fixture_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        missing = required_keys - doc.keys()
        if missing:
            raise ValueError(
                f"{path.name} missing required fields: {missing}"
            )
        documents.append(doc)

    if not documents:
        raise ValueError(f"No JSON documents found in {fixture_dir}")

    return documents


# ---------------------------------------------------------------------------
# Corpus mapping: SC-S1 format -> Synapse engine format
# ---------------------------------------------------------------------------
def map_to_synapse_format(sc_s1_documents: list[dict]) -> list[dict]:
    """Convert SC-S1 fixture dicts to the format expected by the engine.

    Mapping:
        document_id    -> id
        content        -> text
        version, publication_date, status, supersedes -> metadata

    All metadata fields are preserved. Nothing is flattened into text.
    """
    synapse_corpus: list[dict] = []

    for doc in sc_s1_documents:
        synapse_doc = {
            "id": doc["document_id"],
            "text": doc["content"],
            "metadata": {
                "version": doc.get("version"),
                "publication_date": doc.get("publication_date"),
                "status": doc.get("status"),
                "supersedes": doc.get("supersedes"),
            },
        }
        synapse_corpus.append(synapse_doc)

    return synapse_corpus


# ---------------------------------------------------------------------------
# Engine invocation
# ---------------------------------------------------------------------------
def run_synapse_engine(
    query: str,
    synapse_corpus: list[dict],
) -> UnifiedProcessResult:
    """Invoke the real UnifiedEvidenceEngine and return its result.

    Does not catch engine exceptions — callers should handle failures
    to distinguish execution errors from evaluation outcomes.
    """
    engine = UnifiedEvidenceEngine()
    result = engine.process(query, synapse_corpus)
    return result


# ---------------------------------------------------------------------------
# Result normalization
# ---------------------------------------------------------------------------
def normalize_engine_result(
    engine_result: UnifiedProcessResult,
    sc_s1_documents: list[dict],
) -> dict:
    """Convert a UnifiedProcessResult into the SC-S2 result dict.

    Maps chunk_ids back to original document_ids for readability.
    Preserves all available engine signals without fabrication.
    """
    # Build a lookup from engine id -> original document_id
    id_lookup = {
        doc["document_id"]: doc["document_id"]
        for doc in sc_s1_documents
    }

    # Extract selected evidence IDs from engine output
    selected_ids = [
        e.get("chunk_id", "unknown")
        for e in engine_result.selected_evidence
    ]

    # Extract rejected evidence IDs
    rejected_ids = [
        e.get("chunk_id", "unknown")
        for e in engine_result.rejected_evidence
    ]

    # Determine decision output text
    # The engine returns a calibrated decision string (ANSWER/REJECT/UNCERTAIN)
    # We do NOT manufacture a policy statement from metadata.
    decision_output = engine_result.decision

    # Evaluate temporal correctness
    selected_is_current = EXPECTED_CURRENT_DOCUMENT in selected_ids
    eval_status = "PASS" if selected_is_current else "FAIL"

    # Build the result dict
    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "system": SYSTEM_LABEL,
        "query": engine_result.query,
        "corpus": {
            "documents": list(id_lookup.keys()),
        },
        "execution": {
            "status": "success",
            "pipeline_time_ms": round(engine_result.pipeline_time_ms, 2),
        },
        "retrieval": {
            "method": "synapse_unified_evidence_engine",
            "selected_evidence": selected_ids,
            "rejected_evidence": rejected_ids,
        },
        "decision": {
            "outcome": decision_output,
            "selected_evidence": selected_ids,
            "confidence": engine_result.confidence,
            "output": (
                f"Synapse decision: {decision_output} "
                f"(confidence: {engine_result.confidence:.2f})"
            ),
        },
        "signals": {
            "temporal_context": engine_result.temporal_context,
            "conflict_detected": engine_result.signals.get(
                "conflict_detected", False
            ),
            "conflict_score": engine_result.signals.get(
                "conflict_score", 0.0
            ),
            "adjudication_triggered": engine_result.signals.get(
                "adjudication_triggered", False
            ),
            "adjudication_decision": engine_result.signals.get(
                "adjudication_decision", "NONE"
            ),
            "safety_veto": engine_result.signals.get(
                "safety_veto", False
            ),
            "sufficiency_score": engine_result.signals.get(
                "sufficiency_score", 0.0
            ),
            "relationships": engine_result.relationships,
        },
        "evaluation": {
            "expected_current_document": EXPECTED_CURRENT_DOCUMENT,
            "selected_current_document": selected_is_current,
            "status": eval_status,
        },
    }

    return result


def build_error_result(query: str, error: Exception) -> dict:
    """Build a result dict representing an execution failure.

    Used when the engine raises an exception. Does not fabricate
    a decision or evaluation outcome.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "system": SYSTEM_LABEL,
        "query": query,
        "corpus": {
            "documents": ["AUTH-POLICY-V1", "AUTH-POLICY-V2"],
        },
        "execution": {
            "status": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
        "retrieval": {
            "method": "synapse_unified_evidence_engine",
            "selected_evidence": [],
            "rejected_evidence": [],
        },
        "decision": {
            "outcome": None,
            "selected_evidence": [],
            "confidence": None,
            "output": None,
        },
        "signals": {},
        "evaluation": {
            "expected_current_document": EXPECTED_CURRENT_DOCUMENT,
            "selected_current_document": False,
            "status": "NOT_EVALUATED",
        },
    }

