"""
SC-S2 Test Suite.

Tests the Synapse adapter, comparison logic, result contracts,
and regression safety against SC-S1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure paths are importable
SC_S2_DIR = Path(__file__).resolve().parent.parent
SC_S1_DIR = SC_S2_DIR.parent / "sc_s1"
REPO_ROOT = SC_S2_DIR.parents[2]

for p in [str(SC_S2_DIR), str(SC_S1_DIR), str(REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from synapse_adapter import (
    EXPERIMENT_ID,
    QUERY,
    EXPECTED_CURRENT_DOCUMENT,
    SYSTEM_LABEL,
    load_sc_s1_fixtures,
    map_to_synapse_format,
    normalize_engine_result,
    build_error_result,
)
from comparison import load_result, check_integrity, compare, ComparisonResult


# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------
FIXTURE_DIR = SC_S1_DIR / "fixtures"
BASELINE_RESULT_PATH = SC_S1_DIR / "results" / "sc_s1_result.json"
SYNAPSE_RESULT_PATH = SC_S2_DIR / "results" / "sc_s2_result.json"


# ===================================================================
# ADAPTER TESTS
# ===================================================================


class TestLoadFixtures:
    def test_loads_all_documents(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        assert len(docs) == 6

    def test_document_ids_preserved(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        ids = {d["document_id"] for d in docs}
        assert ids == {
            "ACCESS-CONTROL-V1",
            "AUTH-POLICY-V1",
            "AUTH-POLICY-V2",
            "AUTH-POLICY-V2-AMENDMENT",
            "PASSWORD-POLICY-V1",
            "SSO-GUIDELINE-V1",
        }

    def test_required_fields_present(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        for doc in docs:
            assert "document_id" in doc
            assert "version" in doc
            assert "publication_date" in doc
            assert "status" in doc
            assert "content" in doc

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_sc_s1_fixtures(tmp_path / "nonexistent")

    def test_query_matches_sc_s1(self):
        """The query must be identical to SC-S1's."""
        assert "authentication policy" in QUERY.lower()
        assert "currently in effect" in QUERY.lower()


class TestCorpusMapping:
    def test_maps_document_id_to_id(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        mapped = map_to_synapse_format(docs)
        ids = {d["id"] for d in mapped}
        assert "AUTH-POLICY-V1" in ids
        assert "AUTH-POLICY-V2" in ids

    def test_maps_content_to_text(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        mapped = map_to_synapse_format(docs)
        for m in mapped:
            assert "text" in m
            assert len(m["text"]) > 0

    def test_preserves_metadata(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        mapped = map_to_synapse_format(docs)
        for m in mapped:
            assert "metadata" in m
            meta = m["metadata"]
            assert "version" in meta
            assert "publication_date" in meta
            assert "status" in meta
            assert "supersedes" in meta

    def test_does_not_flatten_metadata_into_text(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        mapped = map_to_synapse_format(docs)
        for m in mapped:
            # Text should be the original content, not augmented
            assert "version" not in m["text"].lower()
            assert "publication_date" not in m["text"]

    def test_v2_supersedes_v1(self):
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        mapped = map_to_synapse_format(docs)
        v2 = next(m for m in mapped if m["id"] == "AUTH-POLICY-V2")
        assert v2["metadata"]["supersedes"] == "AUTH-POLICY-V1"


class TestBuildErrorResult:
    def test_error_result_structure(self):
        err = RuntimeError("test failure")
        result = build_error_result(QUERY, err)
        assert result["execution"]["status"] == "error"
        assert result["execution"]["error_type"] == "RuntimeError"
        assert result["decision"]["outcome"] is None
        assert result["decision"]["confidence"] is None
        assert result["evaluation"]["status"] == "NOT_EVALUATED"

    def test_error_result_preserves_experiment_id(self):
        err = ValueError("bad")
        result = build_error_result(QUERY, err)
        assert result["experiment_id"] == EXPERIMENT_ID
        assert result["system"] == SYSTEM_LABEL


class TestNormalizeEngineResult:
    def _make_mock_result(self, selected_ids=None, decision="ANSWER", confidence=0.8):
        """Create a mock UnifiedProcessResult."""
        mock = MagicMock()
        mock.query = QUERY
        mock.decision = decision
        mock.confidence = confidence
        mock.pipeline_time_ms = 5.0
        mock.selected_evidence = [{"chunk_id": eid} for eid in (selected_ids or ["AUTH-POLICY-V1"])]
        mock.rejected_evidence = [{"chunk_id": "AUTH-POLICY-V2"}]
        mock.temporal_context = {"query_intent": "current", "target_date": None}
        mock.relationships = {"node_count": 2, "edge_count": 1}
        mock.signals = {
            "conflict_detected": False,
            "conflict_score": 0.0,
            "adjudication_triggered": False,
            "adjudication_decision": "UNCERTAIN",
            "safety_veto": False,
            "sufficiency_score": 0.0,
        }
        mock.record = None
        return mock

    def test_pass_evaluation_when_v2_selected(self):
        mock = self._make_mock_result(selected_ids=["AUTH-POLICY-V2"])
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        result = normalize_engine_result(mock, docs)
        assert result["evaluation"]["selected_current_document"] is True
        assert result["evaluation"]["status"] == "PASS"

    def test_fail_evaluation_when_v1_selected(self):
        mock = self._make_mock_result(selected_ids=["AUTH-POLICY-V1"])
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        result = normalize_engine_result(mock, docs)
        assert result["evaluation"]["selected_current_document"] is False
        assert result["evaluation"]["status"] == "FAIL"

    def test_preserves_confidence(self):
        mock = self._make_mock_result(confidence=0.73)
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        result = normalize_engine_result(mock, docs)
        assert result["decision"]["confidence"] == 0.73

    def test_preserves_temporal_context(self):
        mock = self._make_mock_result()
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        result = normalize_engine_result(mock, docs)
        assert result["signals"]["temporal_context"]["query_intent"] == "current"

    def test_uncertain_decision_not_overridden(self):
        mock = self._make_mock_result(decision="UNCERTAIN", confidence=0.48)
        docs = load_sc_s1_fixtures(FIXTURE_DIR)
        result = normalize_engine_result(mock, docs)
        assert result["decision"]["outcome"] == "UNCERTAIN"
        assert result["decision"]["confidence"] == 0.48


# ===================================================================
# COMPARISON TESTS
# ===================================================================


class TestIntegrityChecks:
    def test_matching_results_pass(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        assert check_integrity(b, s) == "MATCH"

    def test_mismatched_experiment_id_detected(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        s["experiment_id"] = "WRONG-ID"
        assert "experiment_id mismatch" in check_integrity(b, s)

    def test_mismatched_query_detected(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        s["query"] = "Different query?"
        assert "query mismatch" in check_integrity(b, s)

    def test_mismatched_corpus_detected(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        s["corpus"]["documents"] = ["AUTH-POLICY-V1"]
        assert "corpus mismatch" in check_integrity(b, s)


class TestComparison:
    def test_comparison_loads_both_results(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        assert isinstance(comp, ComparisonResult)

    def test_input_integrity_match(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        assert comp.input_integrity == "MATCH"

    def test_both_fail_evaluation(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        assert comp.baseline_selected_current is False
        assert comp.synapse_selected_current is False
        assert comp.both_selected_current is False

    def test_evidence_selection_matches(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        # Both selected V1 in this run
        assert comp.evidence_selection_match is True

    def test_synapse_confidence_not_fabricated(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        assert comp.baseline.confidence is None
        assert comp.synapse.confidence is not None

    def test_comparison_serializes(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        j = comp.to_json()
        parsed = json.loads(j)
        assert parsed["experiment_id"] == EXPERIMENT_ID

    def test_notes_include_observations(self):
        b = load_result(BASELINE_RESULT_PATH)
        s = load_result(SYNAPSE_RESULT_PATH)
        comp = compare(b, s)
        assert len(comp.notes) > 0


# ===================================================================
# REGRESSION TESTS
# ===================================================================


class TestRegression:
    def test_sc_s1_result_unchanged(self):
        """The baseline result must still show FAIL with V1 selected."""
        b = load_result(BASELINE_RESULT_PATH)
        assert b["system"] == "baseline"
        assert b["evaluation"]["status"] == "FAIL"
        assert "AUTH-POLICY-V1" in b["decision"]["selected_evidence"]

    def test_sc_s1_result_has_correct_scores(self):
        b = load_result(BASELINE_RESULT_PATH)
        scores = [r["score"] for r in b["retrieval"]["results"]]
        assert scores == [0.5, 0.5]

    def test_synapse_result_exists(self):
        assert SYNAPSE_RESULT_PATH.is_file()

    def test_synapse_result_valid_json(self):
        with open(SYNAPSE_RESULT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["experiment_id"] == EXPERIMENT_ID
        assert data["system"] == "synapse"

    def test_synapse_result_has_execution_info(self):
        with open(SYNAPSE_RESULT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["execution"]["status"] == "success"
        assert "pipeline_time_ms" in data["execution"]
