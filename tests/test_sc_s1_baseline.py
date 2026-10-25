"""
Tests for SC-S1 Conventional Retrieval Baseline.

Covers corpus loading, retrieval, ranking, evaluation,
serialization, and output consistency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — make experiment modules importable
# ---------------------------------------------------------------------------
SC_S1_DIR = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "synapse_compare" / "sc_s1"
)
sys.path.insert(0, str(SC_S1_DIR))

from schemas import (
    EXPECTED_CURRENT_DOCUMENT,
    EXPERIMENT_ID,
    QUERY,
    SCHEMA_VERSION,
    SYSTEM_LABEL,
    ExperimentResult,
    DecisionInfo,
    EvaluationInfo,
    RetrievalInfo,
    RetrievalResult,
)
from baseline import (
    RETRIEVAL_METHOD,
    load_corpus,
    retrieve,
    score_document,
    _tokenize,
)

FIXTURE_DIR = SC_S1_DIR / "fixtures"


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

class TestCorpusLoading:
    def test_loads_both_documents(self):
        docs = load_corpus(FIXTURE_DIR)
        assert len(docs) == 2
        ids = {d["document_id"] for d in docs}
        assert ids == {"AUTH-POLICY-V1", "AUTH-POLICY-V2"}

    def test_documents_have_required_fields(self):
        docs = load_corpus(FIXTURE_DIR)
        required = {"document_id", "version", "publication_date",
                    "status", "content"}
        for doc in docs:
            assert required.issubset(doc.keys())

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_corpus(tmp_path / "nonexistent")

    def test_empty_directory_raises(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="No JSON documents"):
            load_corpus(empty)

    def test_missing_fields_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"document_id": "x"}', encoding="utf-8")
        with pytest.raises(ValueError, match="missing required"):
            load_corpus(tmp_path)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_returns_documents_from_corpus(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs)
        corpus_ids = {d["document_id"] for d in docs}
        for r in info.results:
            assert r.document_id in corpus_ids

    def test_empty_query_raises(self):
        docs = load_corpus(FIXTURE_DIR)
        with pytest.raises(ValueError, match="non-empty"):
            retrieve("", docs)

    def test_whitespace_query_raises(self):
        docs = load_corpus(FIXTURE_DIR)
        with pytest.raises(ValueError, match="non-empty"):
            retrieve("   ", docs)

    def test_top_k_respected(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs, top_k=1)
        assert len(info.results) == 1

    def test_top_k_capped_at_corpus_size(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs, top_k=99)
        assert info.top_k == len(docs)


# ---------------------------------------------------------------------------
# Ranking determinism
# ---------------------------------------------------------------------------

class TestRanking:
    def test_deterministic_ordering(self):
        docs = load_corpus(FIXTURE_DIR)
        r1 = retrieve(QUERY, docs)
        r2 = retrieve(QUERY, docs)
        ids1 = [r.document_id for r in r1.results]
        ids2 = [r.document_id for r in r2.results]
        assert ids1 == ids2

    def test_ranks_are_sequential(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs)
        ranks = [r.rank for r in info.results]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_scores_descending(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs)
        scores = [r.score for r in info.results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Score validity
# ---------------------------------------------------------------------------

class TestScoreValidity:
    def test_scores_are_finite(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs)
        import math
        for r in info.results:
            assert math.isfinite(r.score)

    def test_scores_in_unit_interval(self):
        docs = load_corpus(FIXTURE_DIR)
        info = retrieve(QUERY, docs)
        for r in info.results:
            assert 0.0 <= r.score <= 1.0

    def test_score_document_empty_query(self):
        assert score_document(set(), "some text") == 0.0

    def test_score_document_full_overlap(self):
        tokens = _tokenize("hello world")
        assert score_document(tokens, "hello world") == 1.0


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def _build_result(self) -> ExperimentResult:
        docs = load_corpus(FIXTURE_DIR)
        retrieval = retrieve(QUERY, docs)
        return ExperimentResult(
            schema_version=SCHEMA_VERSION,
            experiment_id=EXPERIMENT_ID,
            system=SYSTEM_LABEL,
            query=QUERY,
            corpus_documents=[d["document_id"] for d in docs],
            retrieval=retrieval,
            decision=DecisionInfo(
                selected_evidence=[retrieval.results[0].document_id],
                output="test output",
            ),
            evaluation=EvaluationInfo(
                expected_current_document=EXPECTED_CURRENT_DOCUMENT,
                selected_current_document=False,
                status="FAIL",
            ),
        )

    def test_has_all_top_level_keys(self):
        d = self._build_result().to_dict()
        expected_keys = {
            "schema_version", "experiment_id", "system",
            "query", "corpus", "retrieval", "decision", "evaluation",
        }
        assert expected_keys == set(d.keys())

    def test_retrieval_has_results(self):
        d = self._build_result().to_dict()
        assert len(d["retrieval"]["results"]) > 0
        for r in d["retrieval"]["results"]:
            assert "document_id" in r
            assert "rank" in r
            assert "score" in r

    def test_evaluation_fields(self):
        d = self._build_result().to_dict()
        ev = d["evaluation"]
        assert "expected_current_document" in ev
        assert "selected_current_document" in ev
        assert "status" in ev


# ---------------------------------------------------------------------------
# Expected outcome
# ---------------------------------------------------------------------------

class TestExpectedOutcome:
    def test_expected_is_v2(self):
        assert EXPECTED_CURRENT_DOCUMENT == "AUTH-POLICY-V2"

    def test_v2_exists_in_corpus(self):
        docs = load_corpus(FIXTURE_DIR)
        ids = {d["document_id"] for d in docs}
        assert EXPECTED_CURRENT_DOCUMENT in ids


# ---------------------------------------------------------------------------
# Evaluation correctness
# ---------------------------------------------------------------------------

class TestEvaluationCorrectness:
    def test_honest_fail_when_v1_selected(self):
        docs = load_corpus(FIXTURE_DIR)
        retrieval = retrieve(QUERY, docs)
        top_id = retrieval.results[0].document_id
        selected_is_current = top_id == EXPECTED_CURRENT_DOCUMENT
        # The baseline selects V1 due to alphabetical tie-break,
        # so this should be False.  We record that honestly.
        assert selected_is_current is False

    def test_pass_when_v2_selected(self):
        # Simulate a scenario where V2 is top-ranked
        selected_is_current = "AUTH-POLICY-V2" == EXPECTED_CURRENT_DOCUMENT
        assert selected_is_current is True


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_json_is_valid(self):
        docs = load_corpus(FIXTURE_DIR)
        retrieval = retrieve(QUERY, docs)
        result = ExperimentResult(
            schema_version=SCHEMA_VERSION,
            experiment_id=EXPERIMENT_ID,
            system=SYSTEM_LABEL,
            query=QUERY,
            corpus_documents=[d["document_id"] for d in docs],
            retrieval=retrieval,
            decision=DecisionInfo(
                selected_evidence=[retrieval.results[0].document_id],
                output="test",
            ),
            evaluation=EvaluationInfo(
                expected_current_document=EXPECTED_CURRENT_DOCUMENT,
                selected_current_document=False,
                status="FAIL",
            ),
        )
        parsed = json.loads(result.to_json())
        assert parsed["schema_version"] == SCHEMA_VERSION

    def test_save_creates_file(self, tmp_path):
        docs = load_corpus(FIXTURE_DIR)
        retrieval = retrieve(QUERY, docs)
        result = ExperimentResult(
            schema_version=SCHEMA_VERSION,
            experiment_id=EXPERIMENT_ID,
            system=SYSTEM_LABEL,
            query=QUERY,
            corpus_documents=[d["document_id"] for d in docs],
            retrieval=retrieval,
            decision=DecisionInfo(
                selected_evidence=[retrieval.results[0].document_id],
                output="test",
            ),
            evaluation=EvaluationInfo(
                expected_current_document=EXPECTED_CURRENT_DOCUMENT,
                selected_current_document=False,
                status="FAIL",
            ),
        )
        out = tmp_path / "result.json"
        result.save(out)
        assert out.exists()
        parsed = json.loads(out.read_text(encoding="utf-8"))
        assert parsed["experiment_id"] == EXPERIMENT_ID


# ---------------------------------------------------------------------------
# Output consistency
# ---------------------------------------------------------------------------

class TestOutputConsistency:
    def test_result_file_matches_run(self):
        """Verify the saved result file matches a fresh execution."""
        result_path = SC_S1_DIR / "results" / "sc_s1_result.json"
        if not result_path.exists():
            pytest.skip("Result file not yet generated; run run_baseline.py first")

        saved = json.loads(result_path.read_text(encoding="utf-8"))

        # Re-execute
        docs = load_corpus(FIXTURE_DIR)
        retrieval = retrieve(QUERY, docs)
        top_id = retrieval.results[0].document_id

        assert saved["retrieval"]["results"][0]["document_id"] == top_id
        assert saved["evaluation"]["status"] in ("PASS", "FAIL")
        assert saved["experiment_id"] == EXPERIMENT_ID