# S12 - Calibration & Robustness Specification

## Sprint
**S12 - Calibration & Robustness**
**Target:** v1.4.0

## Objective
Determine whether S11 quality loss is caused by small-corpus artifacts
and poorly calibrated evidence prioritization. Develop a calibrated
strategy that improves quality/latency trade-off.

## Research Questions
- **RQ1**: Does priority-based evidence selection become more reliable as corpus size increases?
- **RQ2**: Are the current semantic, lexical, and reuse weights correctly calibrated?
- **RQ3**: When does prioritization accidentally suppress answer-bearing evidence?
- **RQ4**: Does the LIGHT/STANDARD/DEEP strategy remain effective under varying conditions?
- **RQ5**: Can we find configurations that simultaneously improve quality, grounding, coverage, and latency?

## Components Built
1. `app/context/calibration.py` - PriorityCalibrationConfig, CalibrationMatrixGenerator, EvidenceSurvivalTracker
2. `app/strategy/fallback.py` - ConfidenceGuard, FallbackDecision
3. `experiments/s12_corpus_scaling.py` - RQ1 corpus scaling harness
4. `experiments/s12_calibration.py` - RQ2/RQ3 calibration matrix
5. `experiments/s12_robustness.py` - RQ4/RQ5 ablation framework

## Definition of Done
- [ ] Priority weights configurable
- [ ] Calibration experiments run automatically
- [ ] Multiple corpus sizes evaluated
- [ ] Evidence survival telemetry exists
- [ ] Fallback behavior implemented and testable
- [ ] Existing S7-S11 functionality intact
- [ ] Full test suite passes
