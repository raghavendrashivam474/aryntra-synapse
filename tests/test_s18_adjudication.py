"""
S18 Test Suite — Controlled Semantic Adjudication

Tests the complete adjudication pipeline:
A. No ambiguity → LLM not called
B. Genuine contradiction → correct resolution
C. False contradiction → adjudicator distinguishes scopes
D. Uncertain case → UNCERTAIN
E. Malformed LLM response → safe fallback
F. LLM timeout → safe fallback
G. Deterministic veto → LLM overridden
H. Candidate bound → enforced
I. Regression → existing tests unaffected
"""

import json
import time
import pytest
from typing import Any, Dict, List, Optional

from app.evidence.adjudication import (
    AdjudicationCandidate,
    AdjudicationController,
    AdjudicationControllerConfig,
    AdjudicationDecision,
    AdjudicationGate,
    AdjudicationGateConfig,
    AdjudicationResult,
    AdjudicationValidator,
    ConflictContext,
    ControlledAdjudicationResult,
    EvidenceAdjudicator,
    LLMAdjudicator,
    MockAdjudicator,
)


# ===================================================================
# Helpers
# ===================================================================

def make_candidate(eid: str, content: str = "", score: float = 0.8) -> AdjudicationCandidate:
    return AdjudicationCandidate(
        evidence_id=eid,
        content=content or f"Content for {eid}",
        relevance_score=score,
    )


def make_conflict_context(
    conflict_type: str = "contradiction",
    evidence_ids: tuple = ("c1", "c2"),
    **kwargs,
) -> ConflictContext:
    return ConflictContext(
        conflict_type=conflict_type,
        evidence_ids=evidence_ids,
        **kwargs,
    )


def make_result(
    decision: AdjudicationDecision = AdjudicationDecision.ACCEPT,
    confidence: float = 0.85,
    evidence_ids: tuple = ("c1",),
    rationale: str = "test",
) -> AdjudicationResult:
    return AdjudicationResult(
        decision=decision,
        confidence=confidence,
        selected_evidence_ids=evidence_ids,
        rationale=rationale,
        adjudication_time_ms=1.0,
    )


def signals_no_conflict() -> Dict[str, Any]:
    return {
        "has_conflict": False,
        "is_sufficient": True,
        "confidence_gap": 0.5,
    }


def signals_with_conflict(severity: float = 0.5) -> Dict[str, Any]:
    return {
        "has_conflict": True,
        "conflict_type": "contradiction",
        "conflict_severity": severity,
        "confidence_gap": 0.05,
        "is_sufficient": False,
        "unresolved_contradictions": ["c1_vs_c2"],
    }


class FakeLLMProvider:
    """Fake LLM provider for testing LLMAdjudicator."""

    def __init__(self):
        self.responses: List[str] = []
        self.calls: List[str] = []
        self.should_timeout = False
        self.should_raise = False
        self.raise_exception = None

    def complete(self, prompt: str, timeout: float) -> str:
        self.calls.append(prompt)
        if self.should_timeout:
            raise TimeoutError("LLM timeout")
        if self.should_raise:
            raise self.raise_exception or RuntimeError("LLM error")
        if self.responses:
            return self.responses.pop(0)
        return '{"decision": "UNCERTAIN", "confidence": 0.0, "selected_evidence_ids": [], "reason": "default"}'


# ===================================================================
# Test A: No ambiguity — LLM not called
# ===================================================================

class TestNoAmbiguity:
    """When deterministic analysis is sufficient, the LLM must NOT be called."""

    def test_sufficient_evidence_skips_adjudication(self):
        mock = MockAdjudicator()
        controller = AdjudicationController(adjudicator=mock)

        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_no_conflict()

        result = controller.process("What is the policy?", candidates, signals)

        assert result.adjudication_was_triggered is False
        assert mock.call_count == 0
        assert result.gate_reason == "no_ambiguity_detected"

    def test_no_candidates_skips_adjudication(self):
        mock = MockAdjudicator()
        controller = AdjudicationController(adjudicator=mock)

        result = controller.process("query", [], signals_no_conflict())

        assert result.adjudication_was_triggered is False
        assert mock.call_count == 0

    def test_disabled_gate_skips_adjudication(self):
        mock = MockAdjudicator()
        config = AdjudicationControllerConfig(
            gate_config=AdjudicationGateConfig(enabled=False)
        )
        controller = AdjudicationController(adjudicator=mock, config=config)

        candidates = [make_candidate("c1")]
        # Even with conflict signals, disabled gate skips
        result = controller.process("query", candidates, signals_with_conflict())

        assert result.adjudication_was_triggered is False
        assert mock.call_count == 0


# ===================================================================
# Test B: Genuine contradiction — correct resolution
# ===================================================================

class TestGenuineContradiction:
    """When real contradictions exist, adjudication should resolve them."""

    def test_contradiction_triggers_adjudication(self):
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.9,
            evidence_ids=("c1",),
            rationale="c1 is the current policy; c2 was superseded.",
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [
            make_candidate("c1", "Employees may work remotely three days per week."),
            make_candidate("c2", "Remote work is prohibited for all employees."),
        ]
        signals = signals_with_conflict()

        result = controller.process("What is the remote work policy?", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert mock.call_count == 1
        assert result.final_decision == AdjudicationDecision.ACCEPT
        assert result.final_confidence == 0.9

    def test_adjudicator_receives_correct_candidates(self):
        mock = MockAdjudicator()
        mock.set_response(make_result())

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        controller.process("query", candidates, signals)

        assert mock.call_count == 1
        call = mock.calls[0]
        assert call["candidate_count"] == 2
        assert "c1" in call["candidate_ids"]
        assert "c2" in call["candidate_ids"]


# ===================================================================
# Test C: False contradiction — scopes distinguished
# ===================================================================

class TestFalseContradiction:
    """Evidence that appears contradictory but actually refers to
    different scopes should be correctly classified."""

    def test_scope_disambiguation(self):
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.REJECT,
            confidence=0.88,
            evidence_ids=("c1", "c2"),
            rationale="c1 applies to general employees; c2 applies only to regulated roles. Not a true contradiction.",
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [
            make_candidate("c1", "Employees may work remotely three days per week."),
            make_candidate("c2", "Remote work is prohibited for employees in regulated roles."),
        ]
        signals = signals_with_conflict()
        signals["conflict_type"] = "scope_ambiguity"

        result = controller.process("Can I work remotely?", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.final_decision == AdjudicationDecision.REJECT


# ===================================================================
# Test D: Uncertain case — UNCERTAIN preserved
# ===================================================================

class TestUncertainCase:
    """When evidence is genuinely insufficient, UNCERTAIN must be the result."""

    def test_adjudicator_returns_uncertain(self):
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.UNCERTAIN,
            confidence=0.3,
            evidence_ids=(),
            rationale="Evidence is genuinely ambiguous.",
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_low_confidence_becomes_uncertain(self):
        """Even ACCEPT with low confidence should become UNCERTAIN."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.3,  # Below min_accept_confidence (0.6)
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        assert result.final_decision == AdjudicationDecision.UNCERTAIN
        assert result.trace["final_reason"] == "confidence_below_threshold"


# ===================================================================
# Test E: Malformed LLM response — safe fallback
# ===================================================================

class TestMalformedResponse:
    """Invalid LLM output must result in safe fallback, never propagate."""

    def test_invalid_json(self):
        valid_ids = {"c1", "c2"}
        is_valid, result, error = AdjudicationValidator.validate_raw_response(
            "Yeah, I think document B is probably better...", valid_ids
        )
        assert is_valid is False
        assert result is None
        assert "invalid_json" in error

    def test_empty_response(self):
        is_valid, result, error = AdjudicationValidator.validate_raw_response("", {"c1"})
        assert is_valid is False
        assert "empty_response" in error

    def test_missing_decision(self):
        raw = json.dumps({"confidence": 0.5, "selected_evidence_ids": []})
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, set())
        assert is_valid is False
        assert "invalid_decision" in error

    def test_invalid_decision_value(self):
        raw = json.dumps({
            "decision": "MAYBE",
            "confidence": 0.5,
            "selected_evidence_ids": [],
        })
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, set())
        assert is_valid is False
        assert "invalid_decision" in error

    def test_missing_confidence(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "selected_evidence_ids": [],
        })
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, set())
        assert is_valid is False
        assert "missing_confidence" in error

    def test_confidence_out_of_range(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "confidence": 1.5,
            "selected_evidence_ids": [],
        })
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, set())
        assert is_valid is False
        assert "confidence_out_of_range" in error

    def test_invalid_evidence_ids(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "confidence": 0.8,
            "selected_evidence_ids": ["c99"],
        })
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, {"c1"})
        assert is_valid is False
        assert "invalid_evidence_ids" in error

    def test_valid_response_parses(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "confidence": 0.87,
            "selected_evidence_ids": ["c1", "c2"],
            "reason": "c2 explicitly limits the broader policy in c1.",
        })
        is_valid, result, error = AdjudicationValidator.validate_raw_response(raw, {"c1", "c2"})
        assert is_valid is True
        assert result is not None
        assert result.decision == AdjudicationDecision.ACCEPT
        assert result.confidence == 0.87
        assert result.selected_evidence_ids == ("c1", "c2")

    def test_llm_adjudicator_malformed_response_falls_back(self):
        """LLMAdjudicator with malformed response → UNCERTAIN."""
        provider = FakeLLMProvider()
        provider.responses.append("totally not json {{{")

        adj = LLMAdjudicator(provider=provider)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        context = make_conflict_context()

        result = adj.adjudicate("query", candidates, context)

        assert result.decision == AdjudicationDecision.UNCERTAIN
        assert "fallback" in result.rationale


# ===================================================================
# Test F: LLM timeout — safe fallback
# ===================================================================

class TestLLMTimeout:
    """LLM unavailability must result in UNCERTAIN, never crash."""

    def test_timeout_returns_uncertain(self):
        provider = FakeLLMProvider()
        provider.should_timeout = True

        adj = LLMAdjudicator(provider=provider)
        candidates = [make_candidate("c1")]
        context = make_conflict_context()

        result = adj.adjudicate("query", candidates, context)

        assert result.decision == AdjudicationDecision.UNCERTAIN
        assert "timeout" in result.rationale

    def test_generic_error_returns_uncertain(self):
        provider = FakeLLMProvider()
        provider.should_raise = True
        provider.raise_exception = ConnectionError("network down")

        adj = LLMAdjudicator(provider=provider)
        candidates = [make_candidate("c1")]
        context = make_conflict_context()

        result = adj.adjudicate("query", candidates, context)

        assert result.decision == AdjudicationDecision.UNCERTAIN
        assert "error" in result.rationale

    def test_full_pipeline_llm_failure_falls_back(self):
        """Full controller pipeline: LLM fails → UNCERTAIN."""
        provider = FakeLLMProvider()
        provider.should_timeout = True

        adj = LLMAdjudicator(provider=provider)
        controller = AdjudicationController(adjudicator=adj)

        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN


# ===================================================================
# Test G: Deterministic veto — LLM cannot override safety
# ===================================================================

class TestDeterministicVeto:
    """THE most important S18 test.
    LLM says ACCEPT, but deterministic safety says NO → final is safe."""

    def test_veto_on_unsafe_flag(self):
        """deterministic_unsafe flag vetoes LLM ACCEPT."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.95,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["deterministic_unsafe"] = True

        result = controller.process("query", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN
        assert result.trace["final_reason"] == "deterministic_veto"

    def test_veto_on_superseded_evidence(self):
        """LLM accepts evidence that was deterministically superseded → veto."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.9,
            evidence_ids=("c2",),  # c2 is superseded
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["superseded_evidence_ids"] = ["c2"]

        result = controller.process("query", candidates, signals)

        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_veto_on_guard_score_below_floor(self):
        """ConfidenceGuard score below hard floor → veto."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.92,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["confidence_guard_score"] = 0.05  # Below 0.1 floor

        result = controller.process("query", candidates, signals)

        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_no_veto_when_safe(self):
        """LLM ACCEPT without safety flags → accepted."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.85,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        # No unsafe flags

        result = controller.process("query", candidates, signals)

        assert result.deterministic_veto_applied is False
        assert result.final_decision == AdjudicationDecision.ACCEPT

    def test_veto_only_applies_to_accept(self):
        """REJECT decisions are not vetoed (veto only prevents unsafe acceptance)."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.REJECT,
            confidence=0.9,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["deterministic_unsafe"] = True  # Would veto ACCEPT

        result = controller.process("query", candidates, signals)

        # REJECT is not vetoed — veto only blocks unsafe ACCEPT
        assert result.deterministic_veto_applied is False
        assert result.final_decision == AdjudicationDecision.REJECT

    def test_custom_safety_check(self):
        """Custom deterministic safety check function."""
        def strict_safety(adj_result, signals):
            # Custom rule: never accept if specific flag is set
            return not signals.get("requires_human_review", False)

        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.95,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(
            adjudicator=mock,
            deterministic_safety_check=strict_safety,
        )
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["requires_human_review"] = True

        result = controller.process("query", candidates, signals)

        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_safety_check_error_fails_closed(self):
        """If safety check itself errors, fail closed (veto)."""
        def broken_safety(adj_result, signals):
            raise RuntimeError("safety check crashed")

        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.95,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(
            adjudicator=mock,
            deterministic_safety_check=broken_safety,
        )
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN


# ===================================================================
# Test H: Candidate bound — enforced
# ===================================================================

class TestCandidateBound:
    """LLM must never receive more than the configured candidate limit."""

    def test_default_bound_is_3(self):
        config = AdjudicationGateConfig()
        assert config.max_candidates == 3

    def test_candidates_truncated_to_bound(self):
        mock = MockAdjudicator()
        mock.set_response(make_result())

        config = AdjudicationControllerConfig(
            gate_config=AdjudicationGateConfig(max_candidates=2)
        )
        controller = AdjudicationController(adjudicator=mock, config=config)

        # 5 candidates, but only 2 should reach adjudicator
        candidates = [make_candidate(f"c{i}") for i in range(5)]
        signals = signals_with_conflict()

        controller.process("query", candidates, signals)

        assert mock.call_count == 1
        assert mock.calls[0]["candidate_count"] == 2

    def test_bound_validation_rejects_too_high(self):
        with pytest.raises(ValueError, match="max_candidates must be <= 10"):
            AdjudicationGateConfig(max_candidates=50)

    def test_bound_validation_rejects_zero(self):
        with pytest.raises(ValueError, match="max_candidates must be >= 1"):
            AdjudicationGateConfig(max_candidates=0)


# ===================================================================
# Gate trigger tests
# ===================================================================

class TestAdjudicationGate:
    """Test the gate logic in isolation."""

    def test_no_conflict_no_trigger(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1")]
        decision = gate.evaluate("query", candidates, signals_no_conflict())
        assert decision.should_adjudicate is False

    def test_unresolved_contradiction_triggers(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = {"has_conflict": True, "unresolved_contradictions": ["c1_vs_c2"]}
        decision = gate.evaluate("query", candidates, signals)
        assert decision.should_adjudicate is True
        assert decision.reason == "unresolved_contradictions"

    def test_high_severity_conflict_triggers(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1")]
        signals = {
            "has_conflict": True,
            "conflict_severity": 0.8,
        }
        decision = gate.evaluate("query", candidates, signals)
        assert decision.should_adjudicate is True
        assert decision.reason == "conflict_above_threshold"

    def test_low_severity_conflict_does_not_trigger(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1")]
        signals = {
            "has_conflict": True,
            "conflict_severity": 0.1,  # Below default 0.3
        }
        decision = gate.evaluate("query", candidates, signals)
        assert decision.should_adjudicate is False

    def test_narrow_confidence_gap_triggers(self):
        gate = AdjudicationGate(AdjudicationGateConfig(min_confidence_gap_trigger=0.15))
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = {"confidence_gap": 0.05}  # Below 0.15
        decision = gate.evaluate("query", candidates, signals)
        assert decision.should_adjudicate is True
        assert decision.reason == "narrow_confidence_gap"

    def test_relationship_conflicts_trigger(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1")]
        signals = {"relationship_conflicts": ["rel_1"]}
        decision = gate.evaluate("query", candidates, signals)
        assert decision.should_adjudicate is True

    def test_gate_tracks_stats(self):
        gate = AdjudicationGate()
        candidates = [make_candidate("c1")]

        gate.evaluate("q1", candidates, signals_no_conflict())
        gate.evaluate("q2", candidates, signals_no_conflict())
        gate.evaluate("q3", candidates, signals_with_conflict())

        stats = gate.stats
        assert stats["skipped"] == 2
        assert stats["adjudication_calls"] == 1
        assert abs(stats["adjudication_rate"] - 1 / 3) < 0.01

    def test_selected_candidates_bounded(self):
        gate = AdjudicationGate(AdjudicationGateConfig(max_candidates=2))
        candidates = [make_candidate(f"c{i}") for i in range(10)]
        signals = signals_with_conflict()

        decision = gate.evaluate("query", candidates, signals)

        assert decision.should_adjudicate is True
        assert len(decision.selected_candidates) == 2


# ===================================================================
# Validator tests (additional edge cases)
# ===================================================================

class TestValidator:
    """Additional validator edge cases."""

    def test_response_not_dict(self):
        is_valid, _, error = AdjudicationValidator.validate_raw_response(
            '"just a string"', set()
        )
        assert is_valid is False
        assert "not_dict" in error

    def test_confidence_non_numeric(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "confidence": "high",
            "selected_evidence_ids": [],
        })
        is_valid, _, error = AdjudicationValidator.validate_raw_response(raw, set())
        assert is_valid is False
        assert "invalid_confidence" in error

    def test_evidence_ids_not_list(self):
        raw = json.dumps({
            "decision": "ACCEPT",
            "confidence": 0.8,
            "selected_evidence_ids": "c1",
        })
        is_valid, _, error = AdjudicationValidator.validate_raw_response(raw, {"c1"})
        assert is_valid is False
        assert "not_list" in error

    def test_all_three_decisions_valid(self):
        for decision in ["ACCEPT", "REJECT", "UNCERTAIN"]:
            raw = json.dumps({
                "decision": decision,
                "confidence": 0.5,
                "selected_evidence_ids": [],
                "reason": "test",
            })
            is_valid, result, _ = AdjudicationValidator.validate_raw_response(raw, set())
            assert is_valid is True
            assert result.decision == AdjudicationDecision(decision)


# ===================================================================
# Data class validation tests
# ===================================================================

class TestDataclassValidation:
    """Ensure data classes enforce their contracts."""

    def test_result_confidence_bounds(self):
        with pytest.raises(ValueError):
            AdjudicationResult(
                decision=AdjudicationDecision.ACCEPT,
                confidence=1.5,
                selected_evidence_ids=(),
                rationale="test",
                adjudication_time_ms=1.0,
            )

    def test_result_negative_confidence(self):
        with pytest.raises(ValueError):
            AdjudicationResult(
                decision=AdjudicationDecision.ACCEPT,
                confidence=-0.1,
                selected_evidence_ids=(),
                rationale="test",
                adjudication_time_ms=1.0,
            )

    def test_result_evidence_ids_must_be_tuple(self):
        with pytest.raises(ValueError):
            AdjudicationResult(
                decision=AdjudicationDecision.ACCEPT,
                confidence=0.5,
                selected_evidence_ids=["not", "a", "tuple"],
                rationale="test",
                adjudication_time_ms=1.0,
            )

    def test_result_frozen(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.confidence = 0.99


# ===================================================================
# LLMAdjudicator with FakeLLMProvider
# ===================================================================

class TestLLMAdjudicator:
    """Test the LLM adjudicator with fake provider."""

    def test_valid_llm_response(self):
        provider = FakeLLMProvider()
        provider.responses.append(json.dumps({
            "decision": "ACCEPT",
            "confidence": 0.87,
            "selected_evidence_ids": ["c1"],
            "reason": "c1 is the authoritative source.",
        }))

        adj = LLMAdjudicator(provider=provider)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        context = make_conflict_context()

        result = adj.adjudicate("query", candidates, context)

        assert result.decision == AdjudicationDecision.ACCEPT
        assert result.confidence == 0.87
        assert result.selected_evidence_ids == ("c1",)
        assert len(provider.calls) == 1

    def test_llm_stats_tracked(self):
        provider = FakeLLMProvider()
        # First call: valid
        provider.responses.append(json.dumps({
            "decision": "ACCEPT",
            "confidence": 0.8,
            "selected_evidence_ids": [],
        }))
        # Second call: malformed
        provider.responses.append("not json")

        adj = LLMAdjudicator(provider=provider)
        candidates = [make_candidate("c1")]
        context = make_conflict_context()

        adj.adjudicate("q1", candidates, context)
        adj.adjudicate("q2", candidates, context)

        stats = adj.stats
        assert stats["total_calls"] == 2
        assert stats["errors"] == 1
        assert stats["fallbacks"] == 1


# ===================================================================
# Metrics / reporting tests
# ===================================================================

class TestMetrics:
    """Controller metrics are correctly tracked."""

    def test_metrics_after_mixed_queries(self):
        mock = MockAdjudicator()
        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]

        # Query 1: no conflict → no adjudication
        controller.process("q1", candidates, signals_no_conflict())

        # Query 2: conflict → adjudication with ACCEPT
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.9,
            evidence_ids=("c1",),
        ))
        controller.process("q2", candidates, signals_with_conflict())

        # Query 3: conflict → adjudication with UNCERTAIN
        mock.set_response(make_result(
            decision=AdjudicationDecision.UNCERTAIN,
            confidence=0.2,
        ))
        controller.process("q3", candidates, signals_with_conflict())

        metrics = controller.metrics
        assert metrics["total_queries"] == 3
        assert metrics["adjudications_triggered"] == 2
        assert metrics["adjudications_accepted"] == 1
        assert metrics["safe_fallbacks"] == 1
        assert metrics["trigger_rate"] == pytest.approx(2 / 3, abs=0.01)


# ===================================================================
# Integration: Full pipeline end-to-end
# ===================================================================

class TestFullPipeline:
    """End-to-end tests of the complete S18 pipeline."""

    def test_easy_case_end_to_end(self):
        """Easy case: no ambiguity → deterministic only."""
        mock = MockAdjudicator()
        controller = AdjudicationController(adjudicator=mock)

        result = controller.process(
            "What is the vacation policy?",
            [make_candidate("c1", "Employees get 20 days of vacation.")],
            signals_no_conflict(),
        )

        assert result.adjudication_was_triggered is False
        assert mock.call_count == 0
        assert result.total_time_ms > 0

    def test_difficult_case_end_to_end(self):
        """Difficult case: conflict → adjudication → resolution."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.88,
            evidence_ids=("c1",),
            rationale="c1 is the updated policy from 2024.",
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [
            make_candidate("c1", "Remote work: 3 days/week (2024 policy)."),
            make_candidate("c2", "Remote work is not permitted (2019 policy)."),
        ]
        signals = signals_with_conflict()

        result = controller.process("Can I work remotely?", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.final_decision == AdjudicationDecision.ACCEPT
        assert result.final_confidence == 0.88
        assert result.deterministic_veto_applied is False

    def test_failure_case_end_to_end(self):
        """Failure case: LLM fails → safe fallback."""
        provider = FakeLLMProvider()
        provider.should_timeout = True

        adj = LLMAdjudicator(provider=provider)
        controller = AdjudicationController(adjudicator=adj)

        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_veto_case_end_to_end(self):
        """Veto case: LLM accepts, but deterministic safety says no."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.95,
            evidence_ids=("c2",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()
        signals["superseded_evidence_ids"] = ["c2"]

        result = controller.process("query", candidates, signals)

        assert result.adjudication_was_triggered is True
        assert result.deterministic_veto_applied is True
        assert result.final_decision == AdjudicationDecision.UNCERTAIN

    def test_decision_trace_complete(self):
        """Trace contains all expected diagnostic information."""
        mock = MockAdjudicator()
        mock.set_response(make_result(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.85,
            evidence_ids=("c1",),
        ))

        controller = AdjudicationController(adjudicator=mock)
        candidates = [make_candidate("c1"), make_candidate("c2")]
        signals = signals_with_conflict()

        result = controller.process("query", candidates, signals)

        trace = result.trace
        assert "gate_ms" in trace
        assert "gate_reason" in trace
        assert "gate_triggered" in trace
        assert "adjudication_candidate_count" in trace
        assert "adjudication_candidate_ids" in trace
        assert "adjudication_decision" in trace
        assert "adjudication_confidence" in trace
        assert "adjudication_ms" in trace
        assert "final_reason" in trace
