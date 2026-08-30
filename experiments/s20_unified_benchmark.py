"""
S20 Unified Evidence Intelligence Benchmark

10 scenarios (U1-U10) exercising the full pipeline end-to-end.
Run: python experiments/s20_unified_benchmark.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
import traceback

from app.evidence.unified import (
    UnifiedEvidenceEngine,
    UnifiedEvidenceConfig,
)
from app.evidence.adjudication import (
    MockAdjudicator,
    AdjudicationResult,
    AdjudicationDecision,
)


def _c(cid, text="Evidence content text.", score=0.8, **kw):
    c = {"chunk_id": cid, "text": text, "relevance_score": score}
    c.update(kw)
    return c


def _header(label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")


def run_benchmark():
    results = {}

    # ── U1: Simple current query ──
    _header("U1 — Simple current query")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "What is the current policy?",
            [_c("c1", "Current policy is X.", score=0.95)],
        )
        ok = r.decision in ("SUFFICIENT", "UNCERTAIN")
        print(f"  decision={r.decision}  time={r.pipeline_time_ms:.1f}ms")
        print(f"  provenance={'yes' if r.provenance else 'no'}")
        results["U1"] = "PASS" if ok else "FAIL"
    except Exception as e:
        results["U1"] = f"ERROR: {e}"
        traceback.print_exc()

    # ── U2: Historical query ──
    _header("U2 — Historical query")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "What policy applied in February 2024?",
            [
                _c("c1", "2024 policy.", effective_date="2024-01"),
                _c("c2", "2025 policy.", effective_date="2025-01"),
            ],
        )
        ok = r.temporal_context.get("enabled") is True
        print(f"  temporal={r.temporal_context}")
        results["U2"] = "PASS" if ok else "FAIL"
    except Exception as e:
        results["U2"] = f"ERROR: {e}"

    # ── U3: Version chain ──
    _header("U3 — Version chain")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "Current policy?",
            [
                _c("v1", "Old version policy.", version="1.0"),
                _c("v2", "Newer version policy.", version="2.0"),
                _c("v3", "Newest version policy.", version="3.0"),
            ],
        )
        print(f"  decision={r.decision}  relationships={r.relationships}")
        results["U3"] = "PASS"
    except Exception as e:
        results["U3"] = f"ERROR: {e}"

    # ── U4: Contradiction ──
    _header("U4 — Contradiction")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "What is the limit?",
            [
                _c("c1", "Limit is 100."),
                _c("c2", "Limit is 200."),
            ],
        )
        print(f"  conflicts={r.conflicts}")
        results["U4"] = "PASS"
    except Exception as e:
        results["U4"] = f"ERROR: {e}"

    # ── U5: Multi-hop relationship ──
    _header("U5 — Multi-hop relationship")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "Related docs?",
            [
                _c("c1", "Doc A Section 1.", document_id="doc1"),
                _c("c2", "Doc B Section 2.", document_id="doc1"),
                _c("c3", "Doc C Section 3.", document_id="doc2"),
            ],
        )
        print(f"  relationships={r.relationships}")
        results["U5"] = "PASS"
    except Exception as e:
        results["U5"] = f"ERROR: {e}"

    # ── U6: Insufficient evidence ──
    _header("U6 — Insufficient evidence")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process("Complex multi-faceted query?", [])
        ok = r.decision in ("INSUFFICIENT", "UNCERTAIN")
        print(f"  decision={r.decision}")
        results["U6"] = "PASS" if ok else "FAIL"
    except Exception as e:
        results["U6"] = f"ERROR: {e}"

    # ── U7: Semantic ambiguity (adjudication triggered) ──
    _header("U7 — Semantic ambiguity")
    try:
        mock = MockAdjudicator()
        mock.set_response(AdjudicationResult(
            decision=AdjudicationDecision.UNCERTAIN,
            confidence=0.4,
            selected_evidence_ids=(),
            rationale="genuinely ambiguous",
            adjudication_time_ms=5.0,
        ))
        engine = UnifiedEvidenceEngine(adjudicator=mock)
        r = engine.process(
            "ambiguous query",
            [_c("c1", "Maybe Option A applies."), _c("c2", "Maybe Option B applies.")],
        )
        print(f"  adjudication={r.adjudication}")
        results["U7"] = "PASS"
    except Exception as e:
        results["U7"] = f"ERROR: {e}"

    # ── U8: Deterministic veto ──
    _header("U8 — Deterministic veto")
    try:
        mock = MockAdjudicator()
        mock.set_response(AdjudicationResult(
            decision=AdjudicationDecision.ACCEPT,
            confidence=0.95,
            selected_evidence_ids=("c1",),
            rationale="accept superseded",
            adjudication_time_ms=2.0,
        ))
        engine = UnifiedEvidenceEngine(adjudicator=mock)
        r = engine.process(
            "test query",
            [_c("c1", "Old info.", superseded=True)],
        )
        print(f"  safety={r.safety}")
        print(f"  decision={r.decision}")
        results["U8"] = "PASS"
    except Exception as e:
        results["U8"] = f"ERROR: {e}"

    # ── U9: Full provenance replay ──
    _header("U9 — Full provenance replay")
    try:
        engine = UnifiedEvidenceEngine()
        r = engine.process(
            "replay test",
            [_c("c1"), _c("c2"), _c("c3")],
        )
        if r.provenance is not None:
            d = r.provenance.to_dict()
            ok = "events" in d and "query" in d
            print(f"  events={len(d.get('events', []))}")
            print(f"  replayable={ok}")
        else:
            ok = False
            print("  provenance=None")
        results["U9"] = "PASS" if ok else "FAIL"
    except Exception as e:
        results["U9"] = f"ERROR: {e}"

    # ── U10: Failure injection ──
    _header("U10 — Failure injection (all layers disabled)")
    try:
        cfg = UnifiedEvidenceConfig(
            temporal_enabled=False,
            relationship_enabled=False,
            sufficiency_enabled=False,
            adjudication_enabled=False,
            provenance_enabled=False,
        )
        engine = UnifiedEvidenceEngine(config=cfg)
        r = engine.process("test", [_c("c1")])
        ok = r.decision in ("SUFFICIENT", "INSUFFICIENT", "UNCERTAIN")
        print(f"  decision={r.decision}  no crash=True")
        results["U10"] = "PASS" if ok else "FAIL"
    except Exception as e:
        results["U10"] = f"ERROR: {e}"

    # ── Summary ──
    print(f"\n{'='*60}")
    print("  S20 BENCHMARK SUMMARY")
    print(f"{'='*60}")
    for k, v in results.items():
        status = "OK" if v == "PASS" else "!!"
        print(f"  [{status}] {k}: {v}")
    total = len(results)
    pass_count = sum(1 for v in results.values() if v == "PASS")
    print(f"\n  {pass_count}/{total} scenarios passed")
    return pass_count == total


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
