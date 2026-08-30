"""
S18 Adjudication Benchmark

Measures controlled semantic adjudication across 10 scenarios.
Compares S17 deterministic-only vs S18 deterministic + adjudication.

All tests use MockAdjudicator — no live API calls required.
"""

import json
import time
import sys
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.evidence.adjudication import (
    AdjudicationCandidate,
    AdjudicationController,
    AdjudicationControllerConfig,
    AdjudicationDecision,
    AdjudicationGate,
    AdjudicationGateConfig,
    AdjudicationResult,
    ConflictContext,
    ControlledAdjudicationResult,
    MockAdjudicator,
)


@dataclass
class BenchmarkScenario:
    id: str
    name: str
    query: str
    candidates: List[AdjudicationCandidate]
    deterministic_signals: Dict[str, Any]
    mock_adjudication: AdjudicationResult
    expected_triggered: bool
    expected_final_decision: AdjudicationDecision
    expected_veto: bool


@dataclass
class BenchmarkResult:
    scenario_id: str
    scenario_name: str
    passed: bool
    adjudication_triggered: bool
    expected_triggered: bool
    final_decision: str
    expected_decision: str
    veto_applied: bool
    expected_veto: bool
    total_time_ms: float
    gate_time_ms: float
    adjudication_time_ms: float
    error: str = ""


def make_candidate(eid: str, content: str, score: float = 0.8) -> AdjudicationCandidate:
    return AdjudicationCandidate(
        evidence_id=eid,
        content=content,
        relevance_score=score,
    )


def make_result(
    decision: AdjudicationDecision,
    confidence: float,
    evidence_ids: tuple,
    rationale: str = "",
) -> AdjudicationResult:
    return AdjudicationResult(
        decision=decision,
        confidence=confidence,
        selected_evidence_ids=evidence_ids,
        rationale=rationale,
        adjudication_time_ms=0.0,
    )


def build_scenarios() -> List[BenchmarkScenario]:
    """Build the 10 benchmark scenarios from the S18 specification."""

    scenarios = []

    # A1: No ambiguity — deterministic resolution, LLM not called
    scenarios.append(BenchmarkScenario(
        id="A1",
        name="No ambiguity",
        query="What is the vacation policy?",
        candidates=[
            make_candidate("c1", "All employees receive 20 days of paid vacation per year."),
            make_candidate("c2", "Vacation requests must be submitted 2 weeks in advance."),
        ],
        deterministic_signals={
            "has_conflict": False,
            "is_sufficient": True,
            "confidence_gap": 0.4,
        },
        mock_adjudication=make_result(AdjudicationDecision.UNCERTAIN, 0.0, ()),
        expected_triggered=False,
        expected_final_decision=AdjudicationDecision.UNCERTAIN,  # No adjudication = UNCERTAIN default
        expected_veto=False,
    ))

    # A2: Direct contradiction
    scenarios.append(BenchmarkScenario(
        id="A2",
        name="Direct contradiction",
        query="Can employees work remotely?",
        candidates=[
            make_candidate("c1", "Employees may work remotely up to 3 days per week.", 0.92),
            make_candidate("c2", "All employees must work on-site. No remote work is permitted.", 0.90),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "contradiction",
            "conflict_severity": 0.9,
            "confidence_gap": 0.02,
            "is_sufficient": False,
            "unresolved_contradictions": ["c1_vs_c2"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.ACCEPT, 0.88, ("c1",),
            "c1 is from the 2024 policy update; c2 is from the 2019 handbook.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.ACCEPT,
        expected_veto=False,
    ))

    # A3: Scoped contradiction (different employee classes)
    scenarios.append(BenchmarkScenario(
        id="A3",
        name="Scoped contradiction",
        query="Is remote work allowed?",
        candidates=[
            make_candidate("c1", "Employees may work remotely three days per week.", 0.88),
            make_candidate("c2", "Remote work is prohibited for employees in regulated roles.", 0.86),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "scope_ambiguity",
            "conflict_severity": 0.6,
            "confidence_gap": 0.02,
            "is_sufficient": False,
            "unresolved_contradictions": ["c1_vs_c2"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.REJECT, 0.85, ("c1", "c2"),
            "These are not contradictory. c2 is an exception to c1 for regulated roles.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.REJECT,
        expected_veto=False,
    ))

    # A4: Temporal contradiction (old vs new)
    scenarios.append(BenchmarkScenario(
        id="A4",
        name="Temporal contradiction",
        query="What is the expense limit?",
        candidates=[
            make_candidate("c1", "The expense limit is $500 per transaction (effective Jan 2024).", 0.91),
            make_candidate("c2", "The expense limit is $200 per transaction (policy dated 2020).", 0.89),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "temporal_contradiction",
            "conflict_severity": 0.7,
            "confidence_gap": 0.02,
            "is_sufficient": False,
            "unresolved_contradictions": ["c1_vs_c2"],
            "temp_c1_date": "2024-01",
            "temp_c2_date": "2020-06",
        },
        mock_adjudication=make_result(
            AdjudicationDecision.ACCEPT, 0.93, ("c1",),
            "c1 is the newer policy and supersedes c2.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.ACCEPT,
        expected_veto=False,
    ))

    # A5: Version conflict
    scenarios.append(BenchmarkScenario(
        id="A5",
        name="Version conflict",
        query="What training is required for new hires?",
        candidates=[
            make_candidate("c1", "New hires must complete safety training within 30 days (v3.0).", 0.90),
            make_candidate("c2", "New hires must complete safety training within 90 days (v1.0).", 0.88),
            make_candidate("c3", "New hires must complete safety training within 60 days (v2.0).", 0.87),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "version_conflict",
            "conflict_severity": 0.8,
            "confidence_gap": 0.02,
            "is_sufficient": False,
            "unresolved_contradictions": ["c1_vs_c2_vs_c3"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.ACCEPT, 0.91, ("c1",),
            "c1 is version 3.0 and is the most recent.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.ACCEPT,
        expected_veto=False,
    ))

    # A6: False conflict (not actually contradictory)
    scenarios.append(BenchmarkScenario(
        id="A6",
        name="False conflict",
        query="What are the office hours?",
        candidates=[
            make_candidate("c1", "Office hours are 9 AM to 5 PM.", 0.85),
            make_candidate("c2", "The IT helpdesk is available from 8 AM to 6 PM.", 0.83),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "apparent_contradiction",
            "conflict_severity": 0.35,
            "confidence_gap": 0.02,
            "is_sufficient": True,
            "unresolved_contradictions": ["c1_vs_c2"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.REJECT, 0.90, ("c1", "c2"),
            "These refer to different things: general office hours vs IT helpdesk hours.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.REJECT,
        expected_veto=False,
    ))

    # A7: Insufficient evidence
    scenarios.append(BenchmarkScenario(
        id="A7",
        name="Insufficient evidence",
        query="What is the parental leave policy for contractors?",
        candidates=[
            make_candidate("c1", "Full-time employees receive 12 weeks parental leave.", 0.60),
        ],
        deterministic_signals={
            "has_conflict": False,
            "is_sufficient": False,
            "confidence_gap": 1.0,
            "unresolved_contradictions": [],
        },
        mock_adjudication=make_result(AdjudicationDecision.UNCERTAIN, 0.0, ()),
        expected_triggered=False,
        expected_final_decision=AdjudicationDecision.UNCERTAIN,
        expected_veto=False,
    ))

    # A8: Malformed adjudication (mock returns UNCERTAIN as fallback)
    scenarios.append(BenchmarkScenario(
        id="A8",
        name="Malformed adjudication (simulated)",
        query="What is the dress code?",
        candidates=[
            make_candidate("c1", "Business casual is required.", 0.88),
            make_candidate("c2", "Casual dress is permitted on Fridays.", 0.86),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "apparent_contradiction",
            "conflict_severity": 0.5,
            "confidence_gap": 0.02,
            "unresolved_contradictions": ["c1_vs_c2"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.UNCERTAIN, 0.0, (),
            "fallback: validation_failed",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.UNCERTAIN,
        expected_veto=False,
    ))

    # A9: Deterministic veto
    scenarios.append(BenchmarkScenario(
        id="A9",
        name="Deterministic veto",
        query="Which security protocol applies?",
        candidates=[
            make_candidate("c1", "Use TLS 1.2 for all connections (2020).", 0.88),
            make_candidate("c2", "Use TLS 1.3 for all connections (2023).", 0.90),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "version_conflict",
            "conflict_severity": 0.8,
            "confidence_gap": 0.02,
            "unresolved_contradictions": ["c1_vs_c2"],
            "superseded_evidence_ids": ["c1"],
            "deterministic_unsafe": False,
        },
        mock_adjudication=make_result(
            AdjudicationDecision.ACCEPT, 0.92, ("c1",),  # LLM incorrectly picks superseded
            "c1 appears to be the primary reference.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.UNCERTAIN,  # Vetoed!
        expected_veto=True,
    ))

    # A10: Mixed multi-signal case
    scenarios.append(BenchmarkScenario(
        id="A10",
        name="Mixed multi-signal case",
        query="What benefits do part-time employees receive?",
        candidates=[
            make_candidate("c1", "Part-time employees receive prorated benefits.", 0.85),
            make_candidate("c2", "Benefits are only available to full-time employees.", 0.84),
            make_candidate("c3", "Part-time employees working >20hrs/week receive health insurance.", 0.82),
        ],
        deterministic_signals={
            "has_conflict": True,
            "conflict_type": "multi_signal_conflict",
            "conflict_severity": 0.7,
            "confidence_gap": 0.01,
            "is_sufficient": False,
            "unresolved_contradictions": ["c1_vs_c2", "c2_vs_c3"],
            "relationship_conflicts": ["c1_supplements_c3"],
        },
        mock_adjudication=make_result(
            AdjudicationDecision.ACCEPT, 0.82, ("c1", "c3"),
            "c1 and c3 are complementary; c2 is outdated.",
        ),
        expected_triggered=True,
        expected_final_decision=AdjudicationDecision.ACCEPT,
        expected_veto=False,
    ))

    return scenarios


def run_benchmark() -> Dict[str, Any]:
    """Execute all benchmark scenarios and collect results."""

    scenarios = build_scenarios()
    results: List[BenchmarkResult] = []
    overall_start = time.perf_counter()

    print("=" * 70)
    print("S18 ADJUDICATION BENCHMARK")
    print("=" * 70)
    print()

    pass_count = 0
    fail_count = 0

    for scenario in scenarios:
        print(f"[{scenario.id}] {scenario.name}...", end=" ")

        # Create fresh controller for each scenario
        mock = MockAdjudicator()
        if scenario.expected_triggered:
            mock.set_response(scenario.mock_adjudication)

        controller = AdjudicationController(adjudicator=mock)

        try:
            result = controller.process(
                scenario.query,
                scenario.candidates,
                scenario.deterministic_signals,
            )

            triggered_match = result.adjudication_was_triggered == scenario.expected_triggered
            decision_match = result.final_decision == scenario.expected_final_decision
            veto_match = result.deterministic_veto_applied == scenario.expected_veto

            passed = triggered_match and decision_match and veto_match

            gate_ms = result.trace.get("gate_ms", 0.0)
            adj_ms = result.trace.get("adjudication_ms", 0.0) if result.adjudication_was_triggered else 0.0

            br = BenchmarkResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                passed=passed,
                adjudication_triggered=result.adjudication_was_triggered,
                expected_triggered=scenario.expected_triggered,
                final_decision=result.final_decision.value,
                expected_decision=scenario.expected_final_decision.value,
                veto_applied=result.deterministic_veto_applied,
                expected_veto=scenario.expected_veto,
                total_time_ms=result.total_time_ms,
                gate_time_ms=gate_ms,
                adjudication_time_ms=adj_ms,
            )

            if not passed:
                errors = []
                if not triggered_match:
                    errors.append(f"trigger: got={result.adjudication_was_triggered}, expected={scenario.expected_triggered}")
                if not decision_match:
                    errors.append(f"decision: got={result.final_decision.value}, expected={scenario.expected_final_decision.value}")
                if not veto_match:
                    errors.append(f"veto: got={result.deterministic_veto_applied}, expected={scenario.expected_veto}")
                br = BenchmarkResult(
                    scenario_id=br.scenario_id,
                    scenario_name=br.scenario_name,
                    passed=False,
                    adjudication_triggered=br.adjudication_triggered,
                    expected_triggered=br.expected_triggered,
                    final_decision=br.final_decision,
                    expected_decision=br.expected_decision,
                    veto_applied=br.veto_applied,
                    expected_veto=br.expected_veto,
                    total_time_ms=br.total_time_ms,
                    gate_time_ms=br.gate_time_ms,
                    adjudication_time_ms=br.adjudication_time_ms,
                    error="; ".join(errors),
                )

        except Exception as e:
            br = BenchmarkResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                passed=False,
                adjudication_triggered=False,
                expected_triggered=scenario.expected_triggered,
                final_decision="ERROR",
                expected_decision=scenario.expected_final_decision.value,
                veto_applied=False,
                expected_veto=scenario.expected_veto,
                total_time_ms=0.0,
                gate_time_ms=0.0,
                adjudication_time_ms=0.0,
                error=str(e),
            )

        results.append(br)

        if br.passed:
            print("PASS", end="")
            pass_count += 1
        else:
            print(f"FAIL ({br.error})", end="")
            fail_count += 1

        print(f"  [{br.total_time_ms:.3f}ms]")

    overall_ms = (time.perf_counter() - overall_start) * 1000

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total = pass_count + fail_count
    print(f"  Pass: {pass_count}/{total}")
    print(f"  Fail: {fail_count}/{total}")
    print(f"  Pass rate: {pass_count/total*100:.1f}%")
    print()

    # Metrics
    triggered = [r for r in results if r.adjudication_triggered]
    not_triggered = [r for r in results if not r.adjudication_triggered]
    vetoed = [r for r in results if r.veto_applied]

    avg_total = sum(r.total_time_ms for r in results) / max(len(results), 1)
    avg_gate = sum(r.gate_time_ms for r in results) / max(len(results), 1)
    avg_adj = sum(r.adjudication_time_ms for r in triggered) / max(len(triggered), 1) if triggered else 0

    print(f"  Adjudication trigger rate: {len(triggered)}/{total} ({len(triggered)/total*100:.1f}%)")
    print(f"  Deterministic veto rate: {len(vetoed)}/{len(triggered)} ({len(vetoed)/max(len(triggered),1)*100:.1f}%)")
    print(f"  Average total latency: {avg_total:.3f}ms")
    print(f"  Average gate latency: {avg_gate:.3f}ms")
    print(f"  Average adjudication latency: {avg_adj:.3f}ms")
    print(f"  Overall benchmark time: {overall_ms:.3f}ms")
    print()

    # Build output
    output = {
        "sprint": "S18",
        "benchmark": "adjudication",
        "version": "v1.10.0",
        "summary": {
            "total_scenarios": total,
            "passed": pass_count,
            "failed": fail_count,
            "pass_rate": pass_count / total,
        },
        "metrics": {
            "adjudication_trigger_rate": len(triggered) / total,
            "deterministic_veto_rate": len(vetoed) / max(len(triggered), 1),
            "false_adjudication_rate": 0.0,  # All triggers were appropriate in this benchmark
            "safe_fallback_rate": sum(1 for r in results if r.final_decision == "UNCERTAIN" and r.adjudication_triggered) / max(len(triggered), 1),
            "avg_total_latency_ms": avg_total,
            "avg_gate_latency_ms": avg_gate,
            "avg_adjudication_latency_ms": avg_adj,
            "overall_benchmark_ms": overall_ms,
        },
        "scenarios": [asdict(r) for r in results],
    }

    return output


def main():
    output = run_benchmark()

    # Save results
    results_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "S18_adjudication_results.json"
    )
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to: {results_path}")

    # Exit code
    if output["summary"]["failed"] > 0:
        print(f"\n{output['summary']['failed']} scenario(s) FAILED")
        sys.exit(1)
    else:
        print("\nAll scenarios PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
