"""
Aryntra Synapse - Sprint 10
Adaptive Evidence Strategy Selection.

Responsibilities:
- Extract cheap deterministic signals from query/evidence state
- Evaluate candidate routing strategies
- Select LIGHT / STANDARD / DEEP processing paths
- Record full decision telemetry for observability
- Zero LLM calls; zero neural classifiers; fully deterministic
"""

from app.strategy.candidates import CANDIDATE_REGISTRY, StrategyDecision, StrategyPath
from app.strategy.selector import AdaptiveSelector, StrategyTelemetry
from app.strategy.signals import extract_query_signals

__all__ = [
    "CANDIDATE_REGISTRY",
    "AdaptiveSelector",
    "StrategyDecision",
    "StrategyPath",
    "StrategyTelemetry",
    "extract_query_signals",
]
