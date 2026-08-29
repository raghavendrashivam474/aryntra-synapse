import pytest
from experiments.s13_generalization_matrix import (
    classify_failure,
    FailureSeverity,
)


def test_classify_f0_no_failure():
    # Top-1 bearing, 100% recall
    sev = classify_failure(
        top1_bearing=True,
        top_k_recall=1.0,
        survival_rate=1.0,
        guard_triggered=False
    )
    assert sev == FailureSeverity.F0_NO_FAILURE


def test_classify_f1_selection_degradation():
    # Top-1 not bearing, but high recall (>= 0.66) and survived (>= 0.5)
    sev = classify_failure(
        top1_bearing=False,
        top_k_recall=0.75,
        survival_rate=0.80,
        guard_triggered=False
    )
    assert sev == FailureSeverity.F1_SELECTION_DEGRADATION


def test_classify_f2_deprioritized_recoverable():
    # Low initial recall, but survived or guard triggered for fallback
    sev = classify_failure(
        top1_bearing=False,
        top_k_recall=0.33,
        survival_rate=0.50,
        guard_triggered=True
    )
    assert sev == FailureSeverity.F2_DEPRIORITIZED_RECOVERABLE


def test_classify_f3_evidence_pruned():
    # Evidence completely pruned, guard not triggered, survival 0
    sev = classify_failure(
        top1_bearing=False,
        top_k_recall=0.0,
        survival_rate=0.0,
        guard_triggered=False
    )
    assert sev == FailureSeverity.F3_EVIDENCE_PRUNED


def test_classify_f4_contradictory_top():
    # Contradictory distractor placed at Top-1
    sev = classify_failure(
        top1_bearing=False,
        top_k_recall=0.0,
        survival_rate=0.0,
        guard_triggered=False,
        is_contradictory_top=True
    )
    assert sev == FailureSeverity.F4_DANGEROUS_UNSUPPORTED
