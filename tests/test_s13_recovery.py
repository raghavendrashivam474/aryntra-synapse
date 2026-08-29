import pytest
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from experiments.s13_generalization_matrix import (
    load_distractor_pool,
    load_query_suite,
    generate_controlled_corpus,
)


def test_confidence_guard_triggers_under_ambiguity():
    guard = ConfidenceGuard(min_score_margin=0.15)
    # Ambiguous scores with small margin between top 2 chunks
    ranked_chunks = [
        {"chunk_id": "c1", "text": "Something about synapse priority.", "priority_score": 0.65, "priority_class": "HIGH"},
        {"chunk_id": "c2", "text": "Synapse priority scoring formula details.", "priority_score": 0.63, "priority_class": "HIGH"},
    ]
    assessment = guard.assess(query="What is synapse priority?", ranked_chunks=ranked_chunks)
    assert assessment.decision in [FallbackDecision.FALLBACK_BROAD, FallbackDecision.FALLBACK_SKIP]


def test_recovery_rate_computation():
    # Simulate failures and recovery math
    evaluations = [
        {"top1_is_answer_bearing": True, "top_k_recall": 1.0, "recovered": False},
        {"top1_is_answer_bearing": False, "top_k_recall": 0.8, "recovered": True},
        {"top1_is_answer_bearing": False, "top_k_recall": 0.5, "recovered": True},
        {"top1_is_answer_bearing": False, "top_k_recall": 0.0, "recovered": False}, # unrecoverable
        {"top1_is_answer_bearing": False, "top_k_recall": 0.7, "recovered": False}, # failed recovery
    ]
    failures = [e for e in evaluations if not e["top1_is_answer_bearing"]]
    recoverable = [e for e in failures if e["top_k_recall"] > 0]
    recovered = [e for e in recoverable if e["recovered"]]

    assert len(failures) == 4
    assert len(recoverable) == 3
    assert len(recovered) == 2
    recovery_rate = len(recovered) / len(recoverable)
    assert round(recovery_rate, 2) == 0.67
