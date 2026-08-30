
ARYNTRA SYNAPSE — S19 BENCHMARK & EVALUATION REPORT
1. Overview
The S19 Benchmark Suite validates the completeness, fidelity, round-trip reproducibility, safety-veto traceability, and performance overhead of the provenance layer across 10 structured scenarios.

2. Benchmark Scenarios (P1–P10)
Scenario ID    Test Scenario    Description    Status
P1    Simple Decision    Single authoritative evidence candidate selection and finalization.    PASS
P2    Multi-Candidate Selection    Multiple candidates evaluated; selections and rejections recorded with reasons.    PASS
P3    Temporal Selection Trace    S16 temporal compatibility analysis and intent filtering recorded.    PASS
P4    Version Chain & Supersession    S17 relationship engine supersession resolution recorded.    PASS
P5    Contradiction Detection    S14 conflict detection and contradiction flagging recorded.    PASS
P6    Progressive Expansion    S15 sufficiency evaluation, stopping checks, and expansion steps recorded.    PASS
P7    Semantic Adjudication    S18 LLM adjudication invocation, candidates, confidence, and output captured.    PASS
P8    Deterministic Veto (CRITICAL)    Deterministic safety veto overriding semantic acceptance explicitly traced.    PASS
P9    Serialization / Deserialization Replay    Full JSON round-trip testing ensuring identical structural and byte fidelity.    PASS
P10    Integrated Full-Pipeline Archaeology    Complex combined scenario traversing all reasoning stages simultaneously.    PASS
3. Quantitative Performance & Overhead
Micro-benchmarks evaluated DecisionRecorder overhead over 5,000 iterations:

Target Overhead: < 1.0000 ms
Measured Overhead: 0.0244 ms per decision cycle
Performance Factor: ~40x faster than requirement
4. Benchmark Artifact Output
Results are recorded to experiments/s19_benchmark_results.json.
