"""
S18 — Controlled Semantic Adjudication

This module provides a gated semantic adjudication layer for resolving
ambiguous or conflicting evidence when deterministic signals alone cannot
safely determine the correct interpretation.

Architecture:
    Deterministic analysis → Ambiguity detected → Adjudication gate →
    LLM (bounded) → Structured judgment → ConfidenceGuard → Accept/Reject/Escalate

Safety invariant:
    LLM adjudication can resolve ambiguity but CANNOT override
    deterministic safety constraints. ConfidenceGuard remains authoritative.

The LLM is a consultation room, not the authority.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Decision vocabulary — deliberately small
# ---------------------------------------------------------------------------

class AdjudicationDecision(Enum):
    """Three possible adjudication outcomes. No more."""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    UNCERTAIN = "UNCERTAIN"


# ---------------------------------------------------------------------------
# Adjudication result — structured, validated
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdjudicationResult:
    """Immutable structured judgment from the adjudicator.

    Every field is validated before the result enters the control path.
    Free-form text is stored in `rationale` for traceability but has
    zero influence on the control decision.
    """
    decision: AdjudicationDecision
    confidence: float
    selected_evidence_ids: Tuple[str, ...]
    rationale: str
    adjudication_time_ms: float
    raw_response: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.decision, AdjudicationDecision):
            raise ValueError(f"Invalid decision type: {type(self.decision)}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.selected_evidence_ids, tuple):
            raise ValueError("selected_evidence_ids must be a tuple")


# ---------------------------------------------------------------------------
# Conflict context — what the deterministic layer identified
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConflictContext:
    """Deterministic signals packaged for the adjudicator.

    This is what the deterministic pipeline identified as ambiguous.
    The adjudicator receives ONLY this context, never the full corpus.
    """
    conflict_type: str  # e.g., "contradiction", "scope_ambiguity", "version_conflict"
    evidence_ids: Tuple[str, ...]
    relationship_signals: Dict[str, Any] = field(default_factory=dict)
    temporal_signals: Dict[str, Any] = field(default_factory=dict)
    confidence_gap: float = 0.0
    description: str = ""


# ---------------------------------------------------------------------------
# Evidence candidate — bounded view for the adjudicator
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdjudicationCandidate:
    """A single piece of evidence presented to the adjudicator.

    This is a deliberately limited view — only what the adjudicator
    needs to make a judgment about the specific conflict.
    """
    evidence_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0


# ---------------------------------------------------------------------------
# Adjudicator abstract interface
# ---------------------------------------------------------------------------

class EvidenceAdjudicator(ABC):
    """Abstract adjudicator interface.

    Implementations:
        - MockAdjudicator: deterministic, for testing
        - LLMAdjudicator: real LLM calls, for production

    The interface is provider-independent. Tests MUST NOT depend
    on a live API call.
    """

    @abstractmethod
    def adjudicate(
        self,
        query: str,
        candidates: List[AdjudicationCandidate],
        conflict_context: ConflictContext,
    ) -> AdjudicationResult:
        """Evaluate ambiguous candidates and return a structured judgment.

        Args:
            query: The original user query.
            candidates: Bounded list of evidence candidates (max enforced by gate).
            conflict_context: Deterministic signals describing the ambiguity.

        Returns:
            AdjudicationResult with validated structure.

        Raises:
            Nothing — implementations must catch all errors and return
            UNCERTAIN with safe defaults.
        """
        ...


# ---------------------------------------------------------------------------
# Adjudication gate — decides whether to invoke the adjudicator
# ---------------------------------------------------------------------------

@dataclass
class AdjudicationGateConfig:
    """Configuration for the adjudication gate.

    Controls when and how the LLM is invoked.
    """
    # Maximum candidates sent to adjudicator
    max_candidates: int = 3

    # Minimum confidence gap to trigger adjudication
    # If top candidates are this close, ambiguity is suspected
    min_confidence_gap_trigger: float = 0.15

    # Whether adjudication is enabled at all
    enabled: bool = True

    # Timeout for adjudication calls (seconds)
    timeout_seconds: float = 30.0

    # Minimum conflict severity to trigger (0.0 = always, 1.0 = never)
    min_conflict_severity: float = 0.3

    def __post_init__(self):
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        if self.max_candidates > 10:
            raise ValueError("max_candidates must be <= 10 (safety bound)")
        if not (0.0 <= self.min_confidence_gap_trigger <= 1.0):
            raise ValueError("min_confidence_gap_trigger must be [0.0, 1.0]")


@dataclass
class GateDecision:
    """Result of the adjudication gate evaluation."""
    should_adjudicate: bool
    reason: str
    trigger_signals: Dict[str, Any] = field(default_factory=dict)
    selected_candidates: List[AdjudicationCandidate] = field(default_factory=list)
    conflict_context: Optional[ConflictContext] = None


class AdjudicationGate:
    """Decides whether semantic adjudication is needed.

    This is the most important component of S18. It ensures the LLM
    is called ONLY when deterministic signals detect genuine ambiguity
    that cannot be resolved by existing analysis.

    The gate reuses existing S14-S17 signals rather than inventing
    a second conflict system.
    """

    def __init__(self, config: Optional[AdjudicationGateConfig] = None):
        self.config = config or AdjudicationGateConfig()
        self._call_count = 0
        self._skip_count = 0

    def evaluate(
        self,
        query: str,
        candidates: List[AdjudicationCandidate],
        deterministic_signals: Dict[str, Any],
    ) -> GateDecision:
        """Evaluate whether adjudication should be triggered.

        Args:
            query: Original query.
            candidates: All candidate evidence from retrieval.
            deterministic_signals: Signals from S14-S17 pipeline.
                Expected keys:
                    - has_conflict: bool
                    - conflict_type: str (optional)
                    - confidence_gap: float (optional)
                    - conflict_severity: float (optional)
                    - is_sufficient: bool (optional)
                    - relationship_conflicts: list (optional)
                    - unresolved_contradictions: list (optional)

        Returns:
            GateDecision with selected candidates if adjudication is needed.
        """
        if not self.config.enabled:
            self._skip_count += 1
            return GateDecision(
                should_adjudicate=False,
                reason="adjudication_disabled",
            )

        if not candidates:
            self._skip_count += 1
            return GateDecision(
                should_adjudicate=False,
                reason="no_candidates",
            )

        # Check for genuine conflict/ambiguity signals
        has_conflict = deterministic_signals.get("has_conflict", False)
        conflict_severity = deterministic_signals.get("conflict_severity", 0.0)
        confidence_gap = deterministic_signals.get("confidence_gap", 1.0)
        is_sufficient = deterministic_signals.get("is_sufficient", True)
        unresolved = deterministic_signals.get("unresolved_contradictions", [])
        relationship_conflicts = deterministic_signals.get("relationship_conflicts", [])

        trigger_signals = {
            "has_conflict": has_conflict,
            "conflict_severity": conflict_severity,
            "confidence_gap": confidence_gap,
            "is_sufficient": is_sufficient,
            "unresolved_count": len(unresolved),
            "relationship_conflict_count": len(relationship_conflicts),
        }

        # Decision logic — deterministic first
        should_adjudicate = False
        reason = "no_ambiguity_detected"

        # Trigger 1: Unresolved contradictions
        if unresolved and len(unresolved) > 0:
            should_adjudicate = True
            reason = "unresolved_contradictions"

        # Trigger 2: Conflict above severity threshold
        elif has_conflict and conflict_severity >= self.config.min_conflict_severity:
            should_adjudicate = True
            reason = "conflict_above_threshold"

        # Trigger 3: Confidence gap too narrow (ambiguous ranking)
        elif confidence_gap < self.config.min_confidence_gap_trigger:
            should_adjudicate = True
            reason = "narrow_confidence_gap"

        # Trigger 4: Relationship conflicts unresolved
        elif relationship_conflicts and len(relationship_conflicts) > 0:
            should_adjudicate = True
            reason = "relationship_conflicts"

        # Trigger 5: Explicitly insufficient but candidates exist
        elif not is_sufficient and len(candidates) >= 2:
            should_adjudicate = True
            reason = "insufficient_with_candidates"

        if not should_adjudicate:
            self._skip_count += 1
            return GateDecision(
                should_adjudicate=False,
                reason=reason,
                trigger_signals=trigger_signals,
            )

        # Select bounded candidates for adjudication
        selected = candidates[:self.config.max_candidates]

        # Build conflict context from deterministic signals
        conflict_type = deterministic_signals.get("conflict_type", "unknown")
        conflict_context = ConflictContext(
            conflict_type=conflict_type,
            evidence_ids=tuple(c.evidence_id for c in selected),
            relationship_signals={
                k: v for k, v in deterministic_signals.items()
                if k.startswith("rel_")
            },
            temporal_signals={
                k: v for k, v in deterministic_signals.items()
                if k.startswith("temp_")
            },
            confidence_gap=confidence_gap,
            description=deterministic_signals.get("conflict_description", ""),
        )

        self._call_count += 1
        return GateDecision(
            should_adjudicate=True,
            reason=reason,
            trigger_signals=trigger_signals,
            selected_candidates=selected,
            conflict_context=conflict_context,
        )

    @property
    def adjudication_rate(self) -> float:
        """Fraction of evaluations that triggered adjudication."""
        total = self._call_count + self._skip_count
        if total == 0:
            return 0.0
        return self._call_count / total

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "adjudication_calls": self._call_count,
            "skipped": self._skip_count,
            "adjudication_rate": self.adjudication_rate,
        }


# ---------------------------------------------------------------------------
# Response validator — structural validation of LLM output
# ---------------------------------------------------------------------------

class AdjudicationValidator:
    """Validates structured LLM output before it enters the control path.

    Invalid output → UNCERTAIN. No exceptions.
    """

    VALID_DECISIONS = {d.value for d in AdjudicationDecision}

    @classmethod
    def validate_raw_response(
        cls,
        raw: str,
        valid_evidence_ids: set,
    ) -> Tuple[bool, Optional[AdjudicationResult], str]:
        """Parse and validate a raw LLM response string.

        Args:
            raw: Raw string from LLM (expected JSON).
            valid_evidence_ids: Set of IDs that are valid candidates.

        Returns:
            (is_valid, result_or_none, error_message)
        """
        if not raw or not raw.strip():
            return False, None, "empty_response"

        # Parse JSON
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, TypeError) as e:
            return False, None, f"invalid_json: {e}"

        if not isinstance(data, dict):
            return False, None, "response_not_dict"

        # Validate decision
        decision_str = data.get("decision")
        if decision_str not in cls.VALID_DECISIONS:
            return False, None, f"invalid_decision: {decision_str}"

        # Validate confidence
        confidence = data.get("confidence")
        if confidence is None:
            return False, None, "missing_confidence"
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            return False, None, f"invalid_confidence: {confidence}"
        if not (0.0 <= confidence <= 1.0):
            return False, None, f"confidence_out_of_range: {confidence}"

        # Validate evidence IDs
        evidence_ids = data.get("selected_evidence_ids", [])
        if not isinstance(evidence_ids, list):
            return False, None, "evidence_ids_not_list"

        # Check all IDs are valid
        invalid_ids = [eid for eid in evidence_ids if eid not in valid_evidence_ids]
        if invalid_ids:
            return False, None, f"invalid_evidence_ids: {invalid_ids}"

        # Validate rationale (optional but should be string)
        rationale = data.get("reason", data.get("rationale", ""))
        if not isinstance(rationale, str):
            rationale = str(rationale)

        try:
            result = AdjudicationResult(
                decision=AdjudicationDecision(decision_str),
                confidence=confidence,
                selected_evidence_ids=tuple(evidence_ids),
                rationale=rationale,
                adjudication_time_ms=0.0,  # Will be set by caller
                raw_response=raw,
            )
            return True, result, ""
        except (ValueError, TypeError) as e:
            return False, None, f"result_construction_failed: {e}"


# ---------------------------------------------------------------------------
# Mock adjudicator — deterministic, for testing
# ---------------------------------------------------------------------------

class MockAdjudicator(EvidenceAdjudicator):
    """Deterministic adjudicator for testing.

    Does not make API calls. Behavior is controlled by injected responses.
    """

    def __init__(self):
        self._responses: List[AdjudicationResult] = []
        self._calls: List[Dict[str, Any]] = []
        self._default_decision = AdjudicationDecision.UNCERTAIN

    def set_response(self, result: AdjudicationResult):
        """Set the next response to return."""
        self._responses.append(result)

    def set_responses(self, results: List[AdjudicationResult]):
        """Set multiple responses (consumed in order)."""
        self._responses.extend(results)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> List[Dict[str, Any]]:
        return list(self._calls)

    def adjudicate(
        self,
        query: str,
        candidates: List[AdjudicationCandidate],
        conflict_context: ConflictContext,
    ) -> AdjudicationResult:
        start = time.perf_counter()

        self._calls.append({
            "query": query,
            "candidate_count": len(candidates),
            "candidate_ids": [c.evidence_id for c in candidates],
            "conflict_type": conflict_context.conflict_type,
        })

        elapsed_ms = (time.perf_counter() - start) * 1000

        if self._responses:
            result = self._responses.pop(0)
            # Update timing
            return AdjudicationResult(
                decision=result.decision,
                confidence=result.confidence,
                selected_evidence_ids=result.selected_evidence_ids,
                rationale=result.rationale,
                adjudication_time_ms=elapsed_ms,
                raw_response=result.raw_response,
            )

        return AdjudicationResult(
            decision=self._default_decision,
            confidence=0.0,
            selected_evidence_ids=(),
            rationale="mock_default_response",
            adjudication_time_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# LLM adjudicator — real implementation (provider-isolated)
# ---------------------------------------------------------------------------

class LLMProvider(Protocol):
    """Protocol for LLM providers. Provider-agnostic."""

    def complete(self, prompt: str, timeout: float) -> str:
        """Send prompt, receive raw string response."""
        ...


class LLMAdjudicator(EvidenceAdjudicator):
    """LLM-backed adjudicator.

    Sends a structured prompt to the LLM, validates the response,
    and returns a safe result. All errors → UNCERTAIN.
    """

    PROMPT_TEMPLATE = """You are an evidence adjudicator. Your task is to evaluate conflicting evidence and determine the most defensible interpretation.

QUERY: {query}

CONFLICT TYPE: {conflict_type}
CONFLICT DESCRIPTION: {conflict_description}

EVIDENCE CANDIDATES:
{candidates_text}

INSTRUCTIONS:
1. Evaluate the candidates in the context of the query.
2. Determine which interpretation is most supported.
3. Respond with ONLY a JSON object in this exact format:

{{
  "decision": "ACCEPT" or "REJECT" or "UNCERTAIN",
  "confidence": <float between 0.0 and 1.0>,
  "selected_evidence_ids": [<list of evidence IDs that support your decision>],
  "reason": "<brief explanation>"
}}

DECISION MEANINGS:
- ACCEPT: The first candidate's interpretation is correct/supported.
- REJECT: The first candidate's interpretation is contradicted/unsupported.
- UNCERTAIN: Evidence is genuinely ambiguous or insufficient.

Respond with ONLY the JSON object. No other text."""

    def __init__(
        self,
        provider: LLMProvider,
        timeout: float = 30.0,
    ):
        self._provider = provider
        self._timeout = timeout
        self._call_count = 0
        self._error_count = 0
        self._fallback_count = 0

    def adjudicate(
        self,
        query: str,
        candidates: List[AdjudicationCandidate],
        conflict_context: ConflictContext,
    ) -> AdjudicationResult:
        """Adjudicate using the LLM provider.

        All errors are caught and result in UNCERTAIN.
        Never raises exceptions into the control path.
        """
        start = time.perf_counter()
        self._call_count += 1

        try:
            # Build prompt
            candidates_text = self._format_candidates(candidates)
            prompt = self.PROMPT_TEMPLATE.format(
                query=query,
                conflict_type=conflict_context.conflict_type,
                conflict_description=conflict_context.description,
                candidates_text=candidates_text,
            )

            # Call LLM
            raw_response = self._provider.complete(prompt, self._timeout)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Validate response
            valid_ids = {c.evidence_id for c in candidates}
            is_valid, result, error = AdjudicationValidator.validate_raw_response(
                raw_response, valid_ids
            )

            if is_valid and result is not None:
                # Replace timing with actual
                return AdjudicationResult(
                    decision=result.decision,
                    confidence=result.confidence,
                    selected_evidence_ids=result.selected_evidence_ids,
                    rationale=result.rationale,
                    adjudication_time_ms=elapsed_ms,
                    raw_response=raw_response,
                )
            else:
                logger.warning(
                    "Adjudication response validation failed: %s", error
                )
                self._error_count += 1
                self._fallback_count += 1
                return self._uncertain_fallback(start, f"validation_failed: {error}")

        except TimeoutError:
            logger.warning("Adjudication timed out")
            self._error_count += 1
            self._fallback_count += 1
            return self._uncertain_fallback(start, "timeout")

        except Exception as e:
            logger.warning("Adjudication error: %s", e)
            self._error_count += 1
            self._fallback_count += 1
            return self._uncertain_fallback(start, f"error: {e}")

    def _format_candidates(self, candidates: List[AdjudicationCandidate]) -> str:
        parts = []
        for c in candidates:
            parts.append(
                f"[{c.evidence_id}] (relevance: {c.relevance_score:.3f})\n{c.content}"
            )
        return "\n\n".join(parts)

    def _uncertain_fallback(self, start_time: float, reason: str) -> AdjudicationResult:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return AdjudicationResult(
            decision=AdjudicationDecision.UNCERTAIN,
            confidence=0.0,
            selected_evidence_ids=(),
            rationale=f"fallback: {reason}",
            adjudication_time_ms=elapsed_ms,
        )

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "errors": self._error_count,
            "fallbacks": self._fallback_count,
            "error_rate": self._error_count / max(self._call_count, 1),
        }


# ---------------------------------------------------------------------------
# Adjudication controller — orchestrates gate + adjudicator + guard
# ---------------------------------------------------------------------------

@dataclass
class AdjudicationControllerConfig:
    """Configuration for the full adjudication pipeline."""
    gate_config: AdjudicationGateConfig = field(default_factory=AdjudicationGateConfig)

    # Minimum confidence from adjudicator to accept
    min_accept_confidence: float = 0.6

    # Whether ConfidenceGuard veto is enforced (MUST be True in production)
    enforce_deterministic_veto: bool = True


@dataclass(frozen=True)
class ControlledAdjudicationResult:
    """Final result after gate + adjudication + safety checks."""
    adjudication_was_triggered: bool
    gate_reason: str
    adjudication_result: Optional[AdjudicationResult]
    deterministic_veto_applied: bool
    final_decision: AdjudicationDecision
    final_confidence: float
    total_time_ms: float
    trace: Dict[str, Any] = field(default_factory=dict)


class AdjudicationController:
    """Orchestrates the full S18 pipeline:

    1. Adjudication gate evaluates whether LLM is needed
    2. If needed, bounded candidates go to adjudicator
    3. Result is validated
    4. Deterministic safety check (ConfidenceGuard integration point)
    5. Final decision respects deterministic authority

    Safety invariant: LLM cannot override deterministic safety.
    """

    def __init__(
        self,
        adjudicator: EvidenceAdjudicator,
        config: Optional[AdjudicationControllerConfig] = None,
        deterministic_safety_check: Optional[Any] = None,
    ):
        self.config = config or AdjudicationControllerConfig()
        self._gate = AdjudicationGate(self.config.gate_config)
        self._adjudicator = adjudicator
        self._deterministic_safety_check = deterministic_safety_check

        # Metrics
        self._total_queries = 0
        self._adjudications_triggered = 0
        self._adjudications_accepted = 0
        self._adjudications_vetoed = 0
        self._safe_fallbacks = 0
        self._total_deterministic_ms = 0.0
        self._total_adjudication_ms = 0.0

    def process(
        self,
        query: str,
        candidates: List[AdjudicationCandidate],
        deterministic_signals: Dict[str, Any],
    ) -> ControlledAdjudicationResult:
        """Run the full adjudication pipeline.

        Args:
            query: Original query.
            candidates: Evidence candidates from retrieval.
            deterministic_signals: Signals from S14-S17 deterministic pipeline.

        Returns:
            ControlledAdjudicationResult with full decision trace.
        """
        overall_start = time.perf_counter()
        self._total_queries += 1

        trace: Dict[str, Any] = {}

        # --- Gate evaluation ---
        gate_start = time.perf_counter()
        gate_decision = self._gate.evaluate(query, candidates, deterministic_signals)
        gate_ms = (time.perf_counter() - gate_start) * 1000
        trace["gate_ms"] = gate_ms
        trace["gate_reason"] = gate_decision.reason
        trace["gate_triggered"] = gate_decision.should_adjudicate

        if not gate_decision.should_adjudicate:
            total_ms = (time.perf_counter() - overall_start) * 1000
            self._total_deterministic_ms += total_ms
            return ControlledAdjudicationResult(
                adjudication_was_triggered=False,
                gate_reason=gate_decision.reason,
                adjudication_result=None,
                deterministic_veto_applied=False,
                final_decision=AdjudicationDecision.UNCERTAIN,
                final_confidence=0.0,
                total_time_ms=total_ms,
                trace=trace,
            )

        # --- Adjudication ---
        self._adjudications_triggered += 1
        selected = gate_decision.selected_candidates
        conflict_ctx = gate_decision.conflict_context

        assert conflict_ctx is not None, "Gate triggered but no conflict context"
        assert len(selected) <= self.config.gate_config.max_candidates, \
            f"Candidate bound violated: {len(selected)} > {self.config.gate_config.max_candidates}"

        trace["adjudication_candidate_count"] = len(selected)
        trace["adjudication_candidate_ids"] = [c.evidence_id for c in selected]

        adj_result = self._adjudicator.adjudicate(query, selected, conflict_ctx)
        trace["adjudication_decision"] = adj_result.decision.value
        trace["adjudication_confidence"] = adj_result.confidence
        trace["adjudication_ms"] = adj_result.adjudication_time_ms
        self._total_adjudication_ms += adj_result.adjudication_time_ms

        # --- Deterministic safety check ---
        deterministic_veto = False

        if self.config.enforce_deterministic_veto:
            deterministic_veto = self._apply_deterministic_veto(
                adj_result, deterministic_signals
            )
            trace["deterministic_veto"] = deterministic_veto

        # --- Final decision ---
        if deterministic_veto:
            self._adjudications_vetoed += 1
            final_decision = AdjudicationDecision.UNCERTAIN
            final_confidence = 0.0
            trace["final_reason"] = "deterministic_veto"
        elif adj_result.decision == AdjudicationDecision.UNCERTAIN:
            self._safe_fallbacks += 1
            final_decision = AdjudicationDecision.UNCERTAIN
            final_confidence = adj_result.confidence
            trace["final_reason"] = "adjudicator_uncertain"
        elif adj_result.confidence < self.config.min_accept_confidence:
            self._safe_fallbacks += 1
            final_decision = AdjudicationDecision.UNCERTAIN
            final_confidence = adj_result.confidence
            trace["final_reason"] = "confidence_below_threshold"
        else:
            self._adjudications_accepted += 1
            final_decision = adj_result.decision
            final_confidence = adj_result.confidence
            trace["final_reason"] = "accepted"

        total_ms = (time.perf_counter() - overall_start) * 1000

        return ControlledAdjudicationResult(
            adjudication_was_triggered=True,
            gate_reason=gate_decision.reason,
            adjudication_result=adj_result,
            deterministic_veto_applied=deterministic_veto,
            final_decision=final_decision,
            final_confidence=final_confidence,
            total_time_ms=total_ms,
            trace=trace,
        )

    def _apply_deterministic_veto(
        self,
        adj_result: AdjudicationResult,
        deterministic_signals: Dict[str, Any],
    ) -> bool:
        """Check if deterministic safety should veto the LLM decision.

        The LLM said ACCEPT, but deterministic signals say it's unsafe.
        This is the critical safety invariant of S18.
        """
        if adj_result.decision != AdjudicationDecision.ACCEPT:
            return False

        # If a custom safety check function is provided, use it
        if self._deterministic_safety_check is not None:
            try:
                is_safe = self._deterministic_safety_check(adj_result, deterministic_signals)
                return not is_safe
            except Exception as e:
                logger.warning("Deterministic safety check error: %s", e)
                return True  # Fail closed

        # Default deterministic veto rules
        # Rule 1: If deterministic layer flagged as unsafe
        if deterministic_signals.get("deterministic_unsafe", False):
            logger.info("Deterministic veto: flagged unsafe")
            return True

        # Rule 2: If supersession was detected but LLM accepted superseded evidence
        superseded_ids = set(deterministic_signals.get("superseded_evidence_ids", []))
        if superseded_ids and superseded_ids.intersection(adj_result.selected_evidence_ids):
            logger.info("Deterministic veto: accepted superseded evidence")
            return True

        # Rule 3: If confidence guard score is below hard floor
        guard_score = deterministic_signals.get("confidence_guard_score", None)
        if guard_score is not None and guard_score < 0.1:
            logger.info("Deterministic veto: guard score below hard floor")
            return True

        return False

    @property
    def metrics(self) -> Dict[str, Any]:
        """Comprehensive S18 metrics."""
        return {
            "total_queries": self._total_queries,
            "adjudications_triggered": self._adjudications_triggered,
            "adjudications_accepted": self._adjudications_accepted,
            "adjudications_vetoed": self._adjudications_vetoed,
            "safe_fallbacks": self._safe_fallbacks,
            "trigger_rate": (
                self._adjudications_triggered / max(self._total_queries, 1)
            ),
            "acceptance_rate": (
                self._adjudications_accepted / max(self._adjudications_triggered, 1)
            ),
            "veto_rate": (
                self._adjudications_vetoed / max(self._adjudications_triggered, 1)
            ),
            "fallback_rate": (
                self._safe_fallbacks / max(self._adjudications_triggered, 1)
            ),
            "avg_deterministic_ms": (
                self._total_deterministic_ms / max(
                    self._total_queries - self._adjudications_triggered, 1
                )
            ),
            "avg_adjudication_ms": (
                self._total_adjudication_ms / max(self._adjudications_triggered, 1)
            ),
            "gate_stats": self._gate.stats,
        }
