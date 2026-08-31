# Calibration Intelligence (S21)

## Overview
The Calibration module is the final arbiter of the Synapse pipeline. It takes raw scores from Temporal, Relationship, Conflict, and Sufficiency modules and composes them into a final `DecisionState` and `Confidence` score.

## The Calibration Formula
Confidence is calculated using a non-linear weighted blend:
`FinalConfidence = ((Relevance * 0.6) + (Sufficiency * 0.4)) * ConflictPenalty`

## Why this is necessary
Without calibration, the cumulative effect of safety-oriented modules leads to "Compounding Conservatism," where the system becomes too afraid to answer. S21 provides a disciplined way to be "cautiously confident."