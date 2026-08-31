# S21 Decision Archaeology Guide

## Overview
S21 extends the decision archaeology (S19) by recording exactly how various intelligence signals were composed into a final confidence score.

## New Archaeology Fields
In the `DecisionRecord` (JSON), look for the `calibration` block:

```json
"calibration": {
    "semantic_relevance": 0.8,
    "sufficiency_score": 0.0,
    "conflict_detected": false,
    "conflict_score": 0.0,
    "final_confidence": 0.48,
    "calibration_reason": "calibrated_ambiguous_or_conflicting_evidence"
}
How to Debug "Uncertainty"
If a decision is UNCERTAIN, check the archaeology:

If conflict_detected is true: The confidence was penalized by the sliding scale (S21 logic).
If sufficiency_score is 0.0: The system recognized relevance but felt the data was incomplete.
If final_confidence is 0.0: Check for deterministic_veto: true.