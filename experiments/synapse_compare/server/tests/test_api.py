"""
SC-S4 Backend API Tests.

Tests the live comparison endpoint: validation, execution,
partial failures, and response contract compliance.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure paths
SERVER_DIR = Path(__file__).resolve().parent.parent
SC_DIR = SERVER_DIR.parent
SC_S1 = SC_DIR / "sc_s1"
SC_S2 = SC_DIR / "sc_s2"
REPO_ROOT = SC_DIR.parents[1]

for _p in [str(SC_S1), str(SC_S2), str(REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.synapse_compare.server.main import app

client = TestClient(app)


# ===================================================================
# HEALTH
# ===================================================================
class TestHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["corpus_loaded"] == 2


# ===================================================================
# VALIDATION
# ===================================================================
class TestValidation:
    def test_empty_query_rejected(self):
        r = client.post("/api/v1/compare", json={"query": "", "top_k": 2})
        assert r.status_code == 422

    def test_whitespace_query_rejected(self):
        r = client.post("/api/v1/compare", json={"query": "   ", "top_k": 2})
        assert r.status_code == 422

    def test_missing_query_rejected(self):
        r = client.post("/api/v1/compare", json={"top_k": 2})
        assert r.status_code == 422

    def test_invalid_query_type_rejected(self):
        r = client.post("/api/v1/compare", json={"query": 123})
        assert r.status_code == 422

    def test_top_k_too_large_rejected(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 99})
        assert r.status_code == 422

    def test_top_k_zero_rejected(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 0})
        assert r.status_code == 422


# ===================================================================
# SUCCESSFUL EXECUTION
# ===================================================================
class TestSuccessfulExecution:
    def test_canonical_query_both_succeed(self):
        r = client.post("/api/v1/compare", json={
            "query": "What authentication policy is currently in effect for internal systems?",
            "top_k": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "live"
        assert data["baseline"]["execution_status"] == "success"
        assert data["synapse"]["execution_status"] == "success"
        assert data["comparison"]["status"] == "completed"
        assert data["evaluation"]["status"] == "not_applicable"

    def test_response_has_run_id(self):
        r = client.post("/api/v1/compare", json={"query": "test query", "top_k": 2})
        assert r.status_code == 200
        assert r.json()["run_id"].startswith("live-")

    def test_response_has_corpus_info(self):
        r = client.post("/api/v1/compare", json={"query": "test query", "top_k": 2})
        data = r.json()
        assert "AUTH-POLICY-V1" in data["corpus"]["documents"]
        assert "AUTH-POLICY-V2" in data["corpus"]["documents"]

    def test_baseline_result_structure(self):
        r = client.post("/api/v1/compare", json={"query": "authentication", "top_k": 2})
        bl = r.json()["baseline"]["result"]
        assert bl is not None
        assert bl["system"] == "baseline"
        assert "retrieval" in bl
        assert "decision" in bl

    def test_synapse_result_structure(self):
        r = client.post("/api/v1/compare", json={"query": "authentication", "top_k": 2})
        sy = r.json()["synapse"]["result"]
        assert sy is not None
        assert sy["system"] == "synapse"
        assert "signals" in sy
        assert "decision" in sy

    def test_comparison_has_notes(self):
        r = client.post("/api/v1/compare", json={
            "query": "What authentication policy is currently in effect for internal systems?",
            "top_k": 2,
        })
        comp = r.json()["comparison"]["result"]
        assert "notes" in comp
        assert len(comp["notes"]) > 0

    def test_evaluation_not_applicable_for_custom(self):
        r = client.post("/api/v1/compare", json={"query": "custom query", "top_k": 2})
        ev = r.json()["evaluation"]
        assert ev["status"] == "not_applicable"
        assert ev["ground_truth_id"] is None

    def test_metadata_has_timing(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 2})
        meta = r.json()["metadata"]
        assert "execution_time_ms" in meta
        assert meta["execution_time_ms"] >= 0

    def test_different_queries_produce_different_run_ids(self):
        r1 = client.post("/api/v1/compare", json={"query": "query one", "top_k": 2})
        r2 = client.post("/api/v1/compare", json={"query": "query two", "top_k": 2})
        assert r1.json()["run_id"] != r2.json()["run_id"]


# ===================================================================
# RESPONSE CONTRACT
# ===================================================================
class TestResponseContract:
    def test_all_top_level_keys_present(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 2})
        data = r.json()
        required = {"run_id", "mode", "query", "corpus", "baseline",
                     "synapse", "comparison", "evaluation", "metadata"}
        assert required.issubset(data.keys())

    def test_baseline_error_null_on_success(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 2})
        assert r.json()["baseline"]["error"] is None

    def test_synapse_error_null_on_success(self):
        r = client.post("/api/v1/compare", json={"query": "test", "top_k": 2})
        assert r.json()["synapse"]["error"] is None
