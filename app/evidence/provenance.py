"""
S19 — Provenance & Decision Archaeology

Turns the reasoning happening across S14–S18 into a first-class,
reproducible decision history.

Design principles:
    * S19 RECORDS intelligence; it does NOT invent intelligence.
    * Recording is observational and MUST NOT alter decisions.
    * If recording fails, evidence safety MUST NOT fail with it.
    * Bounded trace size — record meaningful transitions only.
    * LLM decisions can NEVER override deterministic safety;
      the record makes that veto explicit.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (kept as string values for stable JSON serialization)
# ---------------------------------------------------------------------------


class DecisionStage(str, Enum):
    """Pipeline stage that produced an event."""

    CANDIDATE = "candidate"        # candidate discovery / initial pool
    RANKING = "ranking"            # ranking / scoring (S14)
    TEMPORAL = "temporal"          # temporal analysis (S16)
    RELATIONSHIP = "relationship"  # inter-chunk relationships (S17)
    CONFLICT = "conflict"          # contradiction handling (S14)
    SUFFICIENCY = "sufficiency"    # sufficiency evaluation (S15)
    EXPANSION = "expansion"        # progressive assembly (S15)
    ADJUDICATION = "adjudication"  # semantic adjudication (S18)
    SAFETY = "safety"              # deterministic safety veto (S18)
    FINALIZATION = "finalization"  # final outcome


class DecisionAction(str, Enum):
    """What happened at the stage."""

    CONSIDER = "consider"
    SELECT = "select"
    REJECT = "reject"
    SUPERSEDE = "supersede"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    TEMPORAL_MATCH = "temporal_match"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    RELATE = "relate"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    EXPAND = "expand"
    STOP = "stop"
    INVOKE = "invoke"
    ACCEPT = "accept"
    ABSTAIN = "abstain"
    VETO = "veto"
    FINALIZE = "finalize"


class FinalStatus(str, Enum):
    """Final decision status."""

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    UNCERTAIN = "uncertain"
    ERROR = "error"


# ---------------------------------------------------------------------------
# DecisionEvent
# ---------------------------------------------------------------------------


@dataclass
class DecisionEvent:
    """
    One meaningful transition in the reasoning pipeline.

    Events are causal — they capture WHY, not just WHAT.
    Avoid recording thousands of micro-arithmetic updates; record
    decision-relevant transitions.
    """

    stage: str
    action: str
    reason: str
    evidence_id: Optional[str] = None
    related_evidence_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "action": self.action,
            "reason": self.reason,
            "evidence_id": self.evidence_id,
            "related_evidence_id": self.related_evidence_id,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionEvent":
        return cls(
            stage=data["stage"],
            action=data["action"],
            reason=data.get("reason", ""),
            evidence_id=data.get("evidence_id"),
            related_evidence_id=data.get("related_evidence_id"),
            metadata=dict(data.get("metadata", {})),
            timestamp=float(data.get("timestamp", time.time())),
        )


# ---------------------------------------------------------------------------
# Adjudication sub-record
# ---------------------------------------------------------------------------


@dataclass
class AdjudicationRecord:
    """S18 adjudication trace."""

    invoked: bool = False
    candidate_ids: List[str] = field(default_factory=list)
    decision: Optional[str] = None      # "accept" | "abstain" | None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    veto_applied: bool = False
    veto_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdjudicationRecord":
        return cls(
            invoked=bool(data.get("invoked", False)),
            candidate_ids=list(data.get("candidate_ids", [])),
            decision=data.get("decision"),
            confidence=data.get("confidence"),
            reason=data.get("reason"),
            veto_applied=bool(data.get("veto_applied", False)),
            veto_reason=data.get("veto_reason"),
        )


# ---------------------------------------------------------------------------
# DecisionRecord
# ---------------------------------------------------------------------------


@dataclass
class DecisionRecord:
    """
    First-class, reproducible history of one evidence decision.

    A DecisionRecord is the archaeological artifact of one query's
    trip through S14–S18. It should be sufficient to reconstruct
    the decision narrative WITHOUT re-running any intelligence.
    """

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    created_at: float = field(default_factory=time.time)

    candidate_ids: List[str] = field(default_factory=list)
    selected_ids: List[str] = field(default_factory=list)
    rejected_ids: List[str] = field(default_factory=list)

    events: List[DecisionEvent] = field(default_factory=list)

    adjudication: AdjudicationRecord = field(default_factory=AdjudicationRecord)

    final_status: Optional[str] = None
    final_confidence: Optional[float] = None
    final_reason: Optional[str] = None

    trace_complete: bool = False
    trace_truncated: bool = False

    # ---- introspection helpers -------------------------------------------------

    @property
    def candidate_count(self) -> int:
        return len(self.candidate_ids)

    def events_for_stage(self, stage: str) -> List[DecisionEvent]:
        return [e for e in self.events if e.stage == stage]

    @property
    def ranking_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.RANKING.value)

    @property
    def temporal_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.TEMPORAL.value)

    @property
    def relationship_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.RELATIONSHIP.value)

    @property
    def conflict_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.CONFLICT.value)

    @property
    def sufficiency_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.SUFFICIENCY.value)

    @property
    def expansion_events(self) -> List[DecisionEvent]:
        return self.events_for_stage(DecisionStage.EXPANSION.value)

    @property
    def safety_overrides(self) -> List[DecisionEvent]:
        return [
            e for e in self.events
            if e.stage == DecisionStage.SAFETY.value
            and e.action == DecisionAction.VETO.value
        ]

    # ---- serialization ---------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "query": self.query,
            "created_at": self.created_at,
            "candidate_ids": list(self.candidate_ids),
            "selected_ids": list(self.selected_ids),
            "rejected_ids": list(self.rejected_ids),
            "events": [e.to_dict() for e in self.events],
            "adjudication": self.adjudication.to_dict(),
            "final_status": self.final_status,
            "final_confidence": self.final_confidence,
            "final_reason": self.final_reason,
            "trace_complete": self.trace_complete,
            "trace_truncated": self.trace_truncated,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRecord":
        rec = cls(
            decision_id=data.get("decision_id", str(uuid.uuid4())),
            query=data.get("query", ""),
            created_at=float(data.get("created_at", time.time())),
            candidate_ids=list(data.get("candidate_ids", [])),
            selected_ids=list(data.get("selected_ids", [])),
            rejected_ids=list(data.get("rejected_ids", [])),
            events=[DecisionEvent.from_dict(e) for e in data.get("events", [])],
            adjudication=AdjudicationRecord.from_dict(data.get("adjudication", {})),
            final_status=data.get("final_status"),
            final_confidence=data.get("final_confidence"),
            final_reason=data.get("final_reason"),
            trace_complete=bool(data.get("trace_complete", False)),
            trace_truncated=bool(data.get("trace_truncated", False)),
        )
        return rec

    @classmethod
    def from_json(cls, payload: str) -> "DecisionRecord":
        return cls.from_dict(json.loads(payload))

    # ---- human-readable explanation -------------------------------------------

    def explain(self) -> str:
        """Produce a human-readable decision narrative."""
        lines: List[str] = []
        sep = "-" * 60
        lines.append(sep)
        lines.append("FINAL DECISION")
        lines.append(sep)
        lines.append(f"Decision ID : {self.decision_id}")
        lines.append(f"Query       : {self.query!r}")
        lines.append("")
        lines.append(f"Candidates  : {self.candidate_count} "
                     f"({', '.join(self.candidate_ids) if self.candidate_ids else '-'})")
        lines.append(f"Selected    : {', '.join(self.selected_ids) or '-'}")
        lines.append(f"Rejected    : {', '.join(self.rejected_ids) or '-'}")
        lines.append("")

        def _dump(title: str, events: List[DecisionEvent]) -> None:
            if not events:
                return
            lines.append(f"{title}:")
            for e in events:
                tag = e.evidence_id or "-"
                rel = f" -> {e.related_evidence_id}" if e.related_evidence_id else ""
                lines.append(f"  [{e.action}] {tag}{rel}: {e.reason}")
            lines.append("")

        _dump("Temporal", self.temporal_events)
        _dump("Relationships", self.relationship_events)
        _dump("Conflicts", self.conflict_events)
        _dump("Sufficiency", self.sufficiency_events)
        _dump("Expansion", self.expansion_events)

        adj = self.adjudication
        lines.append("Adjudication:")
        if not adj.invoked:
            lines.append("  Not invoked")
        else:
            lines.append(f"  Invoked with candidates: {', '.join(adj.candidate_ids) or '-'}")
            lines.append(f"  Decision   : {adj.decision}")
            lines.append(f"  Confidence : {adj.confidence}")
            lines.append(f"  Reason     : {adj.reason}")
        lines.append("")

        lines.append("Safety:")
        if adj.veto_applied:
            lines.append(f"  VETO APPLIED — {adj.veto_reason}")
        else:
            lines.append("  No veto")
        lines.append("")

        lines.append("Final:")
        lines.append(f"  Status     : {self.final_status}")
        lines.append(f"  Confidence : {self.final_confidence}")
        lines.append(f"  Reason     : {self.final_reason}")
        lines.append("")
        lines.append(f"Trace complete   : {self.trace_complete}")
        lines.append(f"Trace truncated  : {self.trace_truncated}")
        lines.append(sep)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DecisionRecorder
# ---------------------------------------------------------------------------


# Hard upper bound so a broken caller cannot explode a trace.
DEFAULT_MAX_EVENTS = 500


class DecisionRecorder:
    """
    Observational recorder used by the assembly pipeline.

    Contract:
        * NEVER raises out of record() — provenance failures degrade
          the trace, they do not break evidence safety.
        * NEVER mutates evidence, ranking, or adjudication results.
        * Bounded by max_events; further events increment
          `trace_truncated` and are dropped.
    """

    def __init__(
        self,
        query: str = "",
        decision_id: Optional[str] = None,
        max_events: int = DEFAULT_MAX_EVENTS,
    ) -> None:
        self.record = DecisionRecord(
            decision_id=decision_id or str(uuid.uuid4()),
            query=query,
        )
        self._max_events = max(1, int(max_events))

    # ---- generic ---------------------------------------------------------------

    def record_event(
        self,
        stage: str,
        action: str,
        reason: str,
        evidence_id: Optional[str] = None,
        related_evidence_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            if len(self.record.events) >= self._max_events:
                self.record.trace_truncated = True
                return
            self.record.events.append(
                DecisionEvent(
                    stage=str(stage),
                    action=str(action),
                    reason=str(reason),
                    evidence_id=evidence_id,
                    related_evidence_id=related_evidence_id,
                    metadata=dict(metadata or {}),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("provenance recording failed: %s", exc)

    # ---- candidate pool --------------------------------------------------------

    def record_candidates(self, candidate_ids: List[str]) -> None:
        try:
            self.record.candidate_ids = [str(c) for c in candidate_ids]
            for cid in self.record.candidate_ids:
                self.record_event(
                    stage=DecisionStage.CANDIDATE.value,
                    action=DecisionAction.CONSIDER.value,
                    reason="candidate in initial pool",
                    evidence_id=cid,
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("record_candidates failed: %s", exc)

    # ---- S14 conflict ----------------------------------------------------------

    def record_conflict(
        self, evidence_id: str, other_id: str, reason: str,
        resolved: bool = False, metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.record_event(
            stage=DecisionStage.CONFLICT.value,
            action=(
                DecisionAction.CONFLICT_RESOLVED.value if resolved
                else DecisionAction.CONFLICT_DETECTED.value
            ),
            reason=reason,
            evidence_id=evidence_id,
            related_evidence_id=other_id,
            metadata=metadata,
        )

    # ---- S15 sufficiency / expansion ------------------------------------------

    def record_sufficiency(
        self, sufficient: bool, reason: str,
        iteration: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        meta = dict(metadata or {})
        if iteration is not None:
            meta.setdefault("iteration", iteration)
        self.record_event(
            stage=DecisionStage.SUFFICIENCY.value,
            action=(
                DecisionAction.SUFFICIENT.value if sufficient
                else DecisionAction.INSUFFICIENT.value
            ),
            reason=reason,
            metadata=meta,
        )

    def record_expansion(
        self, reason: str, iteration: Optional[int] = None,
        added_ids: Optional[List[str]] = None,
    ) -> None:
        meta: Dict[str, Any] = {}
        if iteration is not None:
            meta["iteration"] = iteration
        if added_ids:
            meta["added_ids"] = list(added_ids)
        self.record_event(
            stage=DecisionStage.EXPANSION.value,
            action=DecisionAction.EXPAND.value,
            reason=reason,
            metadata=meta,
        )

    def record_stop(self, reason: str, iteration: Optional[int] = None) -> None:
        meta: Dict[str, Any] = {}
        if iteration is not None:
            meta["iteration"] = iteration
        self.record_event(
            stage=DecisionStage.EXPANSION.value,
            action=DecisionAction.STOP.value,
            reason=reason,
            metadata=meta,
        )

    # ---- S16 temporal ----------------------------------------------------------

    def record_temporal(
        self, evidence_id: str, compatible: bool, reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.record_event(
            stage=DecisionStage.TEMPORAL.value,
            action=(
                DecisionAction.TEMPORAL_MATCH.value if compatible
                else DecisionAction.TEMPORAL_MISMATCH.value
            ),
            reason=reason,
            evidence_id=evidence_id,
            metadata=metadata,
        )

    # ---- S17 relationships -----------------------------------------------------

    def record_relationship(
        self, evidence_id: str, related_id: str,
        relationship: str, reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        meta = dict(metadata or {})
        meta.setdefault("relationship", relationship)
        action = (
            DecisionAction.SUPERSEDE.value
            if relationship.lower() in {"supersede", "superseded_by", "supersedes"}
            else DecisionAction.RELATE.value
        )
        self.record_event(
            stage=DecisionStage.RELATIONSHIP.value,
            action=action,
            reason=reason,
            evidence_id=evidence_id,
            related_evidence_id=related_id,
            metadata=meta,
        )

    # ---- selection -------------------------------------------------------------

    def record_selection(self, evidence_id: str, reason: str) -> None:
        try:
            if evidence_id not in self.record.selected_ids:
                self.record.selected_ids.append(evidence_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("record_selection failed: %s", exc)
        self.record_event(
            stage=DecisionStage.RANKING.value,
            action=DecisionAction.SELECT.value,
            reason=reason,
            evidence_id=evidence_id,
        )

    def record_rejection(self, evidence_id: str, reason: str) -> None:
        try:
            if evidence_id not in self.record.rejected_ids:
                self.record.rejected_ids.append(evidence_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("record_rejection failed: %s", exc)
        self.record_event(
            stage=DecisionStage.RANKING.value,
            action=DecisionAction.REJECT.value,
            reason=reason,
            evidence_id=evidence_id,
        )

    # ---- S18 adjudication ------------------------------------------------------

    def record_adjudication_invoked(
        self, candidate_ids: List[str], reason: str,
    ) -> None:
        try:
            self.record.adjudication.invoked = True
            self.record.adjudication.candidate_ids = [str(c) for c in candidate_ids]
        except Exception as exc:  # pragma: no cover
            logger.warning("record_adjudication_invoked failed: %s", exc)
        self.record_event(
            stage=DecisionStage.ADJUDICATION.value,
            action=DecisionAction.INVOKE.value,
            reason=reason,
            metadata={"candidate_ids": list(candidate_ids)},
        )

    def record_adjudication_result(
        self, decision: str, confidence: Optional[float], reason: str,
    ) -> None:
        try:
            self.record.adjudication.decision = decision
            self.record.adjudication.confidence = confidence
            self.record.adjudication.reason = reason
        except Exception as exc:  # pragma: no cover
            logger.warning("record_adjudication_result failed: %s", exc)
        action = (
            DecisionAction.ACCEPT.value
            if str(decision).lower() == "accept"
            else DecisionAction.ABSTAIN.value
        )
        self.record_event(
            stage=DecisionStage.ADJUDICATION.value,
            action=action,
            reason=reason,
            metadata={"confidence": confidence},
        )

    def record_safety_veto(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Deterministic safety veto — this is authoritative and must
        appear in the trace whenever it overrides an LLM ACCEPT.
        """
        try:
            self.record.adjudication.veto_applied = True
            self.record.adjudication.veto_reason = reason
        except Exception as exc:  # pragma: no cover
            logger.warning("record_safety_veto failed: %s", exc)
        self.record_event(
            stage=DecisionStage.SAFETY.value,
            action=DecisionAction.VETO.value,
            reason=reason,
            metadata=metadata,
        )

    # ---- finalization ----------------------------------------------------------

    def finalize(
        self,
        status: str,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> DecisionRecord:
        try:
            self.record.final_status = str(status)
            self.record.final_confidence = confidence
            self.record.final_reason = reason
            self.record.trace_complete = True
        except Exception as exc:  # pragma: no cover
            logger.warning("finalize failed: %s", exc)
        self.record_event(
            stage=DecisionStage.FINALIZATION.value,
            action=DecisionAction.FINALIZE.value,
            reason=reason or "decision finalized",
            metadata={"status": status, "confidence": confidence},
        )
        return self.record


# ---------------------------------------------------------------------------
# Null recorder — used when provenance is disabled but callers still
# expect a recorder-shaped object. Never raises, never records.
# ---------------------------------------------------------------------------


class NullDecisionRecorder(DecisionRecorder):
    """No-op recorder for callers that don't want provenance overhead."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        super().__init__(query="", max_events=1)

    def record_event(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_candidates(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_conflict(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_sufficiency(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_expansion(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_stop(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_temporal(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_relationship(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_selection(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_rejection(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_adjudication_invoked(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_adjudication_result(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def record_safety_veto(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def finalize(self, *args: Any, **kwargs: Any) -> DecisionRecord:  # pragma: no cover
        return self.record


__all__ = [
    "DecisionStage",
    "DecisionAction",
    "FinalStatus",
    "DecisionEvent",
    "AdjudicationRecord",
    "DecisionRecord",
    "DecisionRecorder",
    "NullDecisionRecorder",
    "DEFAULT_MAX_EVENTS",
]
