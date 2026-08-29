# Aryntra Synapse — Sprint 14 Handoff Report

**Version:** `v1.6.0`  
**Status:** Clean, all 244 tests passing.

---

## 1. New Modules Created in S14

1. `app/evidence/state.py`: Defines `EvidenceState` enum and `RelationalEvidenceState`.
2. `app/evidence/contradiction.py`: Deterministic non-LLM `ContradictionDetector`, `ConflictPair`, and `ConflictReport`.
3. `app/evidence/coverage.py`: Multi-concept `CoverageAnalyzer`, `ConceptFacet`, and `CoverageReport`.
4. `app/evidence/config.py`: `S14ResolutionConfig` with presets for baseline and ablations.
5. `app/evidence/assembly.py`: `EvidenceAssembler` for bounded greedy progressive evidence assembly.
6. `app/evidence/__init__.py`: Clean unified package exports.
7. `app/strategy/fallback.py`: Extended `ConfidenceGuard` with conflict penalty and coverage routing.

---

## 2. How to Run S14 Tests & Benchmarks

```powershell
# Run all unit and integration tests (244 tests)
pytest tests/ -v

# Run S14 specific tests only
pytest tests/test_s14_*.py -v

# Run the S14 8-configuration benchmark matrix (RQ1-RQ5)
python experiments/s14_matrix_runner.py
3. Recommended Entry Points for S15 Developers
app/evidence/assembly.py -> Review greedy selection loop and marginal coverage gain.
app/strategy/fallback.py -> Review how RESOLVE_CONFLICT and EXPAND_COVERAGE decisions are triggered.
data/s14/s14_matrix_results.json -> Review empirical numbers from the S14 matrix.
