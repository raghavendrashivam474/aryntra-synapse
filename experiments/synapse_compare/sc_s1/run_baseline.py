#!/usr/bin/env python3
"""
SC-S1 Experiment Runner.

Executes the conventional retrieval baseline against the controlled
policy corpus, prints a terminal dashboard, and writes a
machine-readable result JSON.

Usage (from repository root):
    python experiments/synapse_compare/sc_s1/run_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# The script's own directory is already on sys.path when invoked
# directly, but we make it explicit for clarity and safety.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schemas import (
    SCHEMA_VERSION,
    EXPERIMENT_ID,
    SCENARIO_NAME,
    QUERY,
    EXPECTED_CURRENT_DOCUMENT,
    SYSTEM_LABEL,
    ExperimentResult,
    DecisionInfo,
    EvaluationInfo,
)
from baseline import load_corpus, retrieve, RETRIEVAL_METHOD


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIXTURE_DIR = SCRIPT_DIR / "fixtures"
RESULT_DIR = SCRIPT_DIR / "results"
RESULT_FILE = RESULT_DIR / "sc_s1_result.json"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
SEP = "=" * 57


def print_dashboard(result: ExperimentResult) -> None:
    """Print the terminal demonstration output."""
    print()
    print(SEP)
    print("ARYNTRA SYNAPSE \u2014 SYNAPSE COMPARE")
    print("SC-S1: THE FIRST VISIBLE COMPARISON")
    print(SEP)
    print()
    print(f"Scenario: {EXPERIMENT_ID}")
    print()
    print("Query:")
    print(f"  {result.query}")
    print()
    print("Corpus:")
    for doc_id in result.corpus_documents:
        print(f"  - {doc_id}")
    print()
    print("Baseline:")
    print(f"  {result.retrieval.method}")
    print()
    print("Retrieved evidence:")
    for r in result.retrieval.results:
        print(f"  {r.rank}. {r.document_id} | Score: {r.score}")
    print()
    print("Baseline output:")
    print(f"  {result.decision.output}")
    print()
    print("Expected current policy:")
    print(f"  {result.evaluation.expected_current_document}")
    print()
    print("Observed result:")
    sel = result.evaluation.selected_current_document
    status = result.evaluation.status
    print(f"  Selected current document: {sel}")
    print(f"  Evaluation status: {status}")
    print()
    print("Execution status: SUCCESS")
    print()
    print("Result file:")
    print(f"  {RESULT_FILE}")
    print(SEP)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Load corpus
    documents = load_corpus(FIXTURE_DIR)
    corpus_ids = [d["document_id"] for d in documents]

    # 2. Retrieve
    retrieval = retrieve(QUERY, documents, top_k=len(documents))

    # 3. Build decision from top-ranked evidence
    top_doc_id = retrieval.results[0].document_id
    top_doc = next(d for d in documents if d["document_id"] == top_doc_id)
    decision = DecisionInfo(
        selected_evidence=[top_doc_id],
        output=(f"Based on top-ranked evidence ({top_doc_id}): {top_doc['content']}"),
    )

    # 4. Evaluate against expected outcome
    selected_is_current = top_doc_id == EXPECTED_CURRENT_DOCUMENT
    evaluation = EvaluationInfo(
        expected_current_document=EXPECTED_CURRENT_DOCUMENT,
        selected_current_document=selected_is_current,
        status="PASS" if selected_is_current else "FAIL",
    )

    # 5. Assemble full result
    result = ExperimentResult(
        schema_version=SCHEMA_VERSION,
        experiment_id=EXPERIMENT_ID,
        system=SYSTEM_LABEL,
        query=QUERY,
        corpus_documents=corpus_ids,
        retrieval=retrieval,
        decision=decision,
        evaluation=evaluation,
    )

    # 6. Print dashboard
    print_dashboard(result)

    # 7. Save result JSON
    result.save(RESULT_FILE)
    print(f"Result saved to {RESULT_FILE}")


if __name__ == "__main__":
    main()
