import pytest
import os
import json
from experiments.s13_generalization_matrix import (
    load_distractor_pool,
    load_query_suite,
    generate_controlled_corpus,
    GeneralizationHarness,
    FailureSeverity,
)


def test_load_distractor_pool():
    pool = load_distractor_pool()
    assert isinstance(pool, dict)
    expected_keys = ["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"]
    for k in expected_keys:
        assert k in pool
        assert len(pool[k]) > 0


def test_load_query_suite():
    queries = load_query_suite()
    assert isinstance(queries, list)
    assert len(queries) == 7
    types = {q["type"] for q in queries}
    assert "Q1_factual" in types
    assert "Q4_multi_concept" in types
    assert "Q7_sparse" in types


def test_generate_controlled_corpus():
    pool = load_distractor_pool()
    queries = load_query_suite()
    q0 = queries[0]

    for target_size in [5, 25, 50, 100]:
        chunks, answer_ids = generate_controlled_corpus(
            query_item=q0,
            distractor_pool=pool,
            target_size=target_size,
            distractor_type="D1_random",
            seed=42
        )
        assert len(chunks) == target_size
        assert len(answer_ids) >= 1
        assert any(c["category"] == "answer_bearing" for c in chunks)
        assert any(c["category"] == "distractor" for c in chunks)


def test_generalization_harness_mini_sweep():
    harness = GeneralizationHarness()
    results = harness.run_full_matrix(
        corpus_sizes=[5],
        distractor_types=["D1_random", "D2_topic"],
        config_names=["calibrated_blend"]
    )
    assert "metadata" in results
    assert "evaluations" in results
    assert len(results["evaluations"]) == 14  # 1 corpus size * 2 distractors * 7 queries * 1 config
    assert "recovery_metrics" in results
    assert "summary_by_corpus" in results
