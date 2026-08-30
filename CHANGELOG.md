
Changelog
All notable changes to the Aryntra Synapse project will be documented in this file.

[v1.11.0] - Sprint S19: Provenance & Decision Archaeology
Added
Core Provenance Engine (app/evidence/provenance.py):
DecisionRecord and DecisionEvent models for unified causal decision history.
AdjudicationRecord for tracking S18 semantic adjudication results and vetoes.
DecisionRecorder for capturing multi-stage evidence reasoning.
NullDecisionRecorder providing a zero-cost no-op implementation.
Human-readable narrative generation via record.explain().
Full JSON serialization and deserialization (to_json() / from_json()).
Benchmark Suite (experiments/s19_provenance_benchmark.py):
Comprehensive P1–P10 benchmark runner verifying all reasoning transitions.
Micro-latency profiler confirming 0.0244 ms trace overhead.
Unit & Integration Suite (tests/test_s19_provenance.py):
34 new tests covering model serialization, stage event recording, safety veto traceability, and bounded trace caps.
Changed
Total passing test suite expanded from 403 to 437 tests with 0 regressions.
[v1.10.0] - Sprint S18: Controlled Semantic Adjudication
Implemented bounded semantic adjudication gate and LLM adjudicator abstraction.
Enforced strict deterministic safety veto guarantees.
[v1.9.0] - Sprint S17: Inter-Chunk Relationship Intelligence
Implemented version chains, supersession graphs, and contradiction relationship edges.
