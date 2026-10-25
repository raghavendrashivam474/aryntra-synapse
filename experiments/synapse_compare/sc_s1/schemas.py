"""
SC-S1 Result Contract and Scenario Definition.

Defines the fixed scenario parameters and the data structures
used to capture baseline retrieval results in a machine-readable
format consumable by SC-S2.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Scenario constants  (single source of truth for SC-S1)
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0"
EXPERIMENT_ID = "SC-S1-TEMPORAL-001"
SCENARIO_NAME = "Current Authentication Policy"
QUERY = (
    "What authentication policy is currently in effect "
    "for internal systems?"
)
EXPECTED_CURRENT_DOCUMENT = "AUTH-POLICY-V2"
SYSTEM_LABEL = "baseline"

# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """One ranked document returned by the baseline."""
    document_id: str
    rank: int
    score: float


@dataclass
class RetrievalInfo:
    """Retrieval metadata and ranked results."""
    method: str
    top_k: int
    results: list[RetrievalResult]


@dataclass
class DecisionInfo:
    """The baseline's selected evidence and derived output."""
    selected_evidence: list[str]
    output: str


@dataclass
class EvaluationInfo:
    """Comparison of observed behavior against expected outcome."""
    expected_current_document: str
    selected_current_document: bool
    status: str  # "PASS" or "FAIL"


@dataclass
class ExperimentResult:
    """Top-level result object for the SC-S1 experiment."""
    schema_version: str
    experiment_id: str
    system: str
    query: str
    corpus_documents: list[str]
    retrieval: RetrievalInfo
    decision: DecisionInfo
    evaluation: EvaluationInfo

    def to_dict(self) -> dict:
        """Serialize to the canonical JSON-compatible dict."""
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "system": self.system,
            "query": self.query,
            "corpus": {
                "documents": self.corpus_documents,
            },
            "retrieval": {
                "method": self.retrieval.method,
                "top_k": self.retrieval.top_k,
                "results": [
                    {
                        "document_id": r.document_id,
                        "rank": r.rank,
                        "score": r.score,
                    }
                    for r in self.retrieval.results
                ],
            },
            "decision": {
                "selected_evidence": self.decision.selected_evidence,
                "output": self.decision.output,
            },
            "evaluation": {
                "expected_current_document": (
                    self.evaluation.expected_current_document
                ),
                "selected_current_document": (
                    self.evaluation.selected_current_document
                ),
                "status": self.evaluation.status,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")