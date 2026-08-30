"""
S19 — Provenance & Decision Archaeology tests.

These tests verify:
    * DecisionRecord / DecisionEvent construction & serialization
    * DecisionRecorder captures S14–S18 events
    * Safety veto is always traceable
    * Provenance failures do not break the pipeline
    * Bounded trace size
    * Round-trip serialization is stable
"""

from __future__ import annotations

import json

import pytest

from app.evidence.provenance import (
    AdjudicationRecord,
    DecisionAction,
    DecisionEvent,
    DecisionRecord,
    DecisionRecorder,
    DecisionStage,
    FinalStatus,
    NullDecisionRecorder,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class TestDecisionEvent:
    def test_construction_defaults(self):
        ev = DecisionEvent(stage="temporal", action="temporal_match", reason="ok")
        assert ev.stage == "temporal"
        assert ev.action == "temporal_match"
        assert ev.reason == "ok"
        assert ev.evidence_id is None
        assert ev.related_evidence_id is None
        assert ev.metadata == {}
        assert ev.timestamp > 0

    def test_roundtrip(self):
        ev = DecisionEvent(
            stage="relationship",
            action="supersede",
            reason="c2 newer",
            evidence_id="c1",
            related_evidence_id="c2",
            metadata={"k": 1},
        )
        data = ev.to_dict()
        ev2 = DecisionEvent.from_dict(data)
        assert ev2.stage == ev.stage
        assert ev2.action == ev.action
        assert ev2.reason == ev.reason
        assert ev2.evidence_id == ev.evidence_id
        assert ev2.related_evidence_id == ev.related_evidence_id
        assert ev2.metadata == ev.metadata


class TestAdjudicationRecord:
    def test_defaults(self):
        adj = AdjudicationRecord()
        assert adj.invoked is False
        assert adj.candidate_ids == []
        assert adj.decision is None
        assert adj.veto_applied is False

    def test_roundtrip(self):
        adj = AdjudicationRecord(
            invoked=True,
            candidate_ids=["c1", "c2"],
            decision="accept",
            confidence=0.91,
            reason="clear",
            veto_applied=True,
            veto_reason="temporal mismatch",
        )
        adj2 = AdjudicationRecord.from_dict(adj.to_dict())
        assert adj2 == adj


class TestDecisionRecordModel:
    def test_defaults(self):
        rec = DecisionRecord()
        assert rec.decision_id
        assert rec.query == ""
        assert rec.candidate_count == 0
        assert rec.selected_ids == []
        assert rec.rejected_ids == []
        assert rec.events == []
        assert rec.trace_complete is False
        assert rec.trace_truncated is False

    def test_missing_optional_fields_from_dict(self):
        rec = DecisionRecord.from_dict({})
        assert rec.decision_id
        assert rec.query == ""

    def test_events_for_stage(self):
        rec = DecisionRecord()
        rec.events.append(DecisionEvent(stage="temporal", action="a", reason="r"))
        rec.events.append(DecisionEvent(stage="conflict", action="a", reason="r"))
        assert len(rec.events_for_stage("temporal")) == 1
        assert len(rec.events_for_stage("conflict")) == 1

    def test_json_roundtrip(self):
        rec = DecisionRecord(query="q")
        rec.candidate_ids = ["c1", "c2"]
        rec.selected_ids = ["c2"]
        rec.rejected_ids = ["c1"]
        rec.events.append(DecisionEvent(stage="ranking", action="select", reason="best"))
        rec.adjudication = AdjudicationRecord(invoked=True, decision="accept", confidence=0.8)
        rec.final_status = "sufficient"
        rec.trace_complete = True

        payload = rec.to_json()
        json.loads(payload)  # parseable
        rec2 = DecisionRecord.from_json(payload)

        assert rec2.query == "q"
        assert rec2.candidate_ids == ["c1", "c2"]
        assert rec2.selected_ids == ["c2"]
        assert rec2.rejected_ids == ["c1"]
        assert len(rec2.events) == 1
        assert rec2.events[0].stage == "ranking"
        assert rec2.adjudication.invoked is True
        assert rec2.adjudication.decision == "accept"
        assert rec2.final_status == "sufficient"
        assert rec2.trace_complete is True

    def test_deterministic_event_ordering(self):
        rec = DecisionRecord()
        for i in range(5):
            rec.events.append(
                DecisionEvent(stage="ranking", action="select", reason=f"r{i}")
            )
        rec2 = DecisionRecord.from_json(rec.to_json())
        assert [e.reason for e in rec2.events] == [f"r{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class TestDecisionRecorderBasics:
    def test_records_candidates(self):
        r = DecisionRecorder(query="q")
        r.record_candidates(["c1", "c2", "c3"])
        assert r.record.candidate_count == 3
        assert len(r.record.events_for_stage(DecisionStage.CANDIDATE.value)) == 3

    def test_selection_and_rejection(self):
        r = DecisionRecorder(query="q")
        r.record_selection("c1", "best")
        r.record_rejection("c2", "temporal mismatch")
        assert r.record.selected_ids == ["c1"]
        assert r.record.rejected_ids == ["c2"]
        assert len(r.record.ranking_events) == 2

    def test_temporal_events(self):
        r = DecisionRecorder(query="q")
        r.record_temporal("c1", compatible=True, reason="in range")
        r.record_temporal("c2", compatible=False, reason="out of range")
        events = r.record.temporal_events
        actions = {e.action for e in events}
        assert DecisionAction.TEMPORAL_MATCH.value in actions
        assert DecisionAction.TEMPORAL_MISMATCH.value in actions

    def test_relationship_events(self):
        r = DecisionRecorder(query="q")
        r.record_relationship("c1", "c2", "supersede", "c2 is newer")
        r.record_relationship("c3", "c4", "same_document", "shared source")
        events = r.record.relationship_events
        assert any(e.action == DecisionAction.SUPERSEDE.value for e in events)
        assert any(e.action == DecisionAction.RELATE.value for e in events)

    def test_conflict_events(self):
        r = DecisionRecorder(query="q")
        r.record_conflict("c1", "c2", "contradiction")
        r.record_conflict("c1", "c2", "resolved via S17", resolved=True)
        events = r.record.conflict_events
        assert len(events) == 2
        actions = {e.action for e in events}
        assert DecisionAction.CONFLICT_DETECTED.value in actions
        assert DecisionAction.CONFLICT_RESOLVED.value in actions

    def test_sufficiency_and_expansion(self):
        r = DecisionRecorder(query="q")
        r.record_sufficiency(False, "coverage low", iteration=1)
        r.record_expansion("expand pool", iteration=1, added_ids=["c3"])
        r.record_sufficiency(True, "coverage complete", iteration=2)
        r.record_stop("sufficient reached", iteration=2)
        assert len(r.record.sufficiency_events) == 2
        assert len(r.record.expansion_events) == 2  # expand + stop

    def test_finalize_marks_complete(self):
        r = DecisionRecorder(query="q")
        rec = r.finalize(status=FinalStatus.SUFFICIENT.value, confidence=0.9, reason="ok")
        assert rec.trace_complete is True
        assert rec.final_status == "sufficient"
        assert rec.final_confidence == 0.9

    def test_explain_produces_text(self):
        r = DecisionRecorder(query="q")
        r.record_candidates(["c1", "c2"])
        r.record_selection("c1", "best")
        r.finalize(status="sufficient", reason="ok")
        text = r.record.explain()
        assert "FINAL DECISION" in text
        assert "c1" in text


# ---------------------------------------------------------------------------
# Adjudication (S18) + Safety veto — the critical invariant
# ---------------------------------------------------------------------------


class TestAdjudicationTrace:
    def test_adjudication_not_invoked_default(self):
        r = DecisionRecorder(query="q")
        r.finalize(status="sufficient")
        assert r.record.adjudication.invoked is False

    def test_adjudication_accept_flow(self):
        r = DecisionRecorder(query="q")
        r.record_adjudication_invoked(["c1", "c2"], reason="deterministic insufficient")
        r.record_adjudication_result("accept", 0.87, "clear evidence")
        assert r.record.adjudication.invoked is True
        assert r.record.adjudication.decision == "accept"
        assert r.record.adjudication.confidence == 0.87

    def test_safety_veto_is_always_traceable(self):
        """
        CRITICAL: even when LLM accepts, if deterministic safety vetoes,
        the trace must show ACCEPT + VETO + final UNCERTAIN.
        """
        r = DecisionRecorder(query="q")
        r.record_adjudication_invoked(["c1"], reason="needed")
        r.record_adjudication_result("accept", 0.95, "LLM accepted")
        r.record_safety_veto("temporal mismatch — deterministic safety")
        r.finalize(status=FinalStatus.UNCERTAIN.value, reason="safety veto applied")

        adj = r.record.adjudication
        assert adj.invoked is True
        assert adj.decision == "accept"
        assert adj.veto_applied is True
        assert adj.veto_reason is not None
        assert r.record.final_status == "uncertain"
        assert len(r.record.safety_overrides) == 1

    def test_veto_survives_serialization(self):
        r = DecisionRecorder(query="q")
        r.record_adjudication_invoked(["c1"], reason="needed")
        r.record_adjudication_result("accept", 0.95, "LLM accepted")
        r.record_safety_veto("safety")
        r.finalize(status="uncertain", reason="veto")

        rec2 = DecisionRecord.from_json(r.record.to_json())
        assert rec2.adjudication.veto_applied is True
        assert rec2.adjudication.decision == "accept"
        assert rec2.final_status == "uncertain"
        assert len(rec2.safety_overrides) == 1


# ---------------------------------------------------------------------------
# Safety / robustness
# ---------------------------------------------------------------------------


class TestRecorderRobustness:
    def test_recorder_never_raises_on_bad_input(self):
        r = DecisionRecorder(query="q")
        # Non-string inputs should not blow up (str-coerced)
        r.record_event(stage=DecisionStage.RANKING.value, action=DecisionAction.SELECT.value,
                       reason="ok", evidence_id=None)
        r.record_temporal("c1", True, "ok", metadata=None)
        r.record_relationship("c1", "c2", "supersede", "ok", metadata=None)
        # Should have events but never crashed
        assert len(r.record.events) >= 3

    def test_bounded_trace_size(self):
        r = DecisionRecorder(query="q", max_events=10)
        for i in range(50):
            r.record_event(stage="ranking", action="select", reason=f"r{i}")
        assert len(r.record.events) == 10
        assert r.record.trace_truncated is True

    def test_null_recorder_no_ops(self):
        r = NullDecisionRecorder()
        r.record_candidates(["c1", "c2"])
        r.record_selection("c1", "x")
        r.record_safety_veto("x")
        r.finalize(status="sufficient")
        # Null recorder must not accumulate events
        assert r.record.events == []


# ---------------------------------------------------------------------------
# S19 Benchmark scenarios (P1–P10)
# ---------------------------------------------------------------------------


class TestS19BenchmarkScenarios:
    """
    Named scenarios from the S19 brief.
    Each scenario validates a specific reasoning capture path.
    """

    def _finalized(self, r: DecisionRecorder, status: str = "sufficient") -> DecisionRecord:
        return r.finalize(status=status, reason="scenario")

    def test_p1_simple_decision(self):
        r = DecisionRecorder(query="obvious")
        r.record_candidates(["c1"])
        r.record_selection("c1", "single obvious candidate")
        rec = self._finalized(r)
        assert rec.trace_complete
        assert rec.selected_ids == ["c1"]

    def test_p2_multi_candidate(self):
        r = DecisionRecorder(query="multi")
        r.record_candidates(["c1", "c2", "c3"])
        r.record_selection("c2", "best")
        r.record_rejection("c1", "weaker")
        r.record_rejection("c3", "off-topic")
        rec = self._finalized(r)
        assert set(rec.selected_ids) == {"c2"}
        assert set(rec.rejected_ids) == {"c1", "c3"}

    def test_p3_temporal_selection(self):
        r = DecisionRecorder(query="Feb 2026 policy")
        r.record_candidates(["c1", "c2"])
        r.record_temporal("c1", False, "historical mismatch")
        r.record_temporal("c2", True, "in range")
        r.record_selection("c2", "temporally compatible")
        r.record_rejection("c1", "temporal mismatch")
        rec = self._finalized(r)
        assert any(e.action == DecisionAction.TEMPORAL_MISMATCH.value
                   for e in rec.temporal_events)

    def test_p4_version_chain_supersession(self):
        r = DecisionRecorder(query="policy latest")
        r.record_candidates(["c1", "c2", "c3"])
        r.record_relationship("c1", "c2", "supersede", "c2 is newer version")
        r.record_relationship("c2", "c3", "supersede", "c3 is newer version")
        r.record_selection("c3", "latest in chain")
        r.record_rejection("c1", "superseded")
        r.record_rejection("c2", "superseded")
        rec = self._finalized(r)
        supers = [e for e in rec.relationship_events
                  if e.action == DecisionAction.SUPERSEDE.value]
        assert len(supers) == 2

    def test_p5_contradiction(self):
        r = DecisionRecorder(query="contradiction")
        r.record_candidates(["c1", "c2"])
        r.record_conflict("c1", "c2", "contradiction")
        r.record_conflict("c1", "c2", "resolved via temporal precedence", resolved=True)
        r.record_selection("c2", "resolved winner")
        r.record_rejection("c1", "loser")
        rec = self._finalized(r)
        assert len(rec.conflict_events) == 2

    def test_p6_progressive_expansion(self):
        r = DecisionRecorder(query="needs more")
        r.record_candidates(["c1"])
        r.record_sufficiency(False, "coverage incomplete", iteration=1)
        r.record_expansion("expand pool", iteration=1, added_ids=["c2"])
        r.record_sufficiency(True, "sufficient", iteration=2)
        r.record_stop("done", iteration=2)
        r.record_selection("c1", "chosen")
        r.record_selection("c2", "chosen")
        rec = self._finalized(r)
        iters = [e.metadata.get("iteration") for e in rec.sufficiency_events]
        assert iters == [1, 2]

    def test_p7_adjudication(self):
        r = DecisionRecorder(query="ambiguous")
        r.record_candidates(["c1", "c2"])
        r.record_adjudication_invoked(["c1", "c2"], reason="deterministic insufficient")
        r.record_adjudication_result("accept", 0.9, "clear semantic winner")
        r.record_selection("c1", "adjudicator picked")
        rec = self._finalized(r)
        assert rec.adjudication.invoked is True
        assert rec.adjudication.decision == "accept"

    def test_p8_deterministic_veto_critical(self):
        """
        CRITICAL S19 invariant:
        LLM ACCEPT → deterministic VETO → final UNCERTAIN
        All three stages must appear in the trace.
        """
        r = DecisionRecorder(query="risky")
        r.record_candidates(["c1"])
        r.record_adjudication_invoked(["c1"], reason="deterministic insufficient")
        r.record_adjudication_result("accept", 0.95, "LLM accepted")
        r.record_safety_veto("deterministic safety: temporal invariant violated")
        rec = r.finalize(status=FinalStatus.UNCERTAIN.value,
                         reason="safety veto overrides LLM accept")

        # Trace shows accept
        adj_events = rec.events_for_stage(DecisionStage.ADJUDICATION.value)
        assert any(e.action == DecisionAction.ACCEPT.value for e in adj_events)
        # Trace shows veto
        veto_events = rec.safety_overrides
        assert len(veto_events) == 1
        # Final is UNCERTAIN
        assert rec.final_status == "uncertain"
        # Adjudication record itself carries veto flag
        assert rec.adjudication.veto_applied is True

    def test_p9_replay_roundtrip(self):
        r = DecisionRecorder(query="replay me")
        r.record_candidates(["c1", "c2"])
        r.record_temporal("c1", False, "mismatch")
        r.record_temporal("c2", True, "match")
        r.record_relationship("c1", "c2", "supersede", "newer")
        r.record_conflict("c1", "c2", "contradiction")
        r.record_sufficiency(True, "good enough")
        r.record_selection("c2", "winner")
        r.record_rejection("c1", "superseded + temporal mismatch")
        rec = r.finalize(status="sufficient", confidence=0.88, reason="ok")

        rec2 = DecisionRecord.from_json(rec.to_json())

        assert rec2.decision_id == rec.decision_id
        assert rec2.query == rec.query
        assert rec2.candidate_ids == rec.candidate_ids
        assert rec2.selected_ids == rec.selected_ids
        assert rec2.rejected_ids == rec.rejected_ids
        assert len(rec2.events) == len(rec.events)
        assert rec2.final_status == rec.final_status
        assert rec2.final_confidence == rec.final_confidence
        assert rec2.trace_complete is True

    def test_p10_complex_integrated_case(self):
        """All S14–S18 stages represented in a single trace."""
        r = DecisionRecorder(query="everything at once")
        r.record_candidates(["c1", "c2", "c3", "c4"])

        # S16 temporal
        r.record_temporal("c1", False, "too old")
        r.record_temporal("c2", True, "in range")
        r.record_temporal("c3", True, "in range")
        r.record_temporal("c4", False, "future-dated")

        # S17 relationships
        r.record_relationship("c1", "c2", "supersede", "c2 newer")
        r.record_relationship("c2", "c3", "same_document", "shared source")

        # S14 conflict
        r.record_conflict("c2", "c3", "contradiction")
        r.record_conflict("c2", "c3", "resolved via S17 relationship", resolved=True)

        # S15 sufficiency + expansion
        r.record_sufficiency(False, "coverage incomplete", iteration=1)
        r.record_expansion("bring in c3 neighborhood", iteration=1)
        r.record_sufficiency(True, "coverage OK", iteration=2)
        r.record_stop("done", iteration=2)

        # S18 adjudication
        r.record_adjudication_invoked(["c2", "c3"], reason="ambiguity remains")
        r.record_adjudication_result("accept", 0.91, "semantic winner")

        # Selection
        r.record_selection("c2", "adjudicated winner")
        r.record_rejection("c1", "superseded")
        r.record_rejection("c3", "adjudicator abstained")
        r.record_rejection("c4", "temporal mismatch")

        rec = r.finalize(status="sufficient", confidence=0.91, reason="integrated")

        # Verify every stage has at least one event
        for stage in [
            DecisionStage.CANDIDATE,
            DecisionStage.TEMPORAL,
            DecisionStage.RELATIONSHIP,
            DecisionStage.CONFLICT,
            DecisionStage.SUFFICIENCY,
            DecisionStage.EXPANSION,
            DecisionStage.ADJUDICATION,
            DecisionStage.RANKING,
            DecisionStage.FINALIZATION,
        ]:
            assert rec.events_for_stage(stage.value), f"missing events for {stage.value}"

        # Round-trip must remain lossless
        rec2 = DecisionRecord.from_json(rec.to_json())
        assert len(rec2.events) == len(rec.events)
        assert rec2.adjudication.invoked is True
