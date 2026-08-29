"""
Aryntra Synapse - Sprint 16 Tests
Temporal & Version-Aware Evidence Selection.

Validates:
  - Query temporal intent classification
  - Evidence temporal metadata extraction
  - Temporal compatibility scoring
  - Chunk enrichment (additive, non-destructive)
  - Integration with S15 sufficiency
  - Integration with S14 assembly
  - Safety invariants (UNKNOWN -> neutral, no silent deletion)
  - All S1-S15 tests remain green
"""
import pytest
from app.evidence.temporal import (
    TemporalAnalyzer,
    TemporalState,
    QueryTemporalIntent,
    TemporalMetadata,
    TemporalCompatibilityResult,
)
from app.evidence.config import S16TemporalConfig


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def analyzer():
    return TemporalAnalyzer()


@pytest.fixture
def strict_analyzer():
    return TemporalAnalyzer(config=S16TemporalConfig.strict())


@pytest.fixture
def current_chunk():
    return {
        "chunk_id": "c1",
        "text": "The current pricing for Pro is $30/month as of 2025.",
        "score": 0.9,
        "timestamp": "2025-01-15",
    }


@pytest.fixture
def historical_chunk():
    return {
        "chunk_id": "c2",
        "text": "In 2022, the Pro plan was $20/month.",
        "score": 0.85,
    }


@pytest.fixture
def superseded_chunk():
    return {
        "chunk_id": "c3",
        "text": "Policy V2 supersedes V1. All users must comply.",
        "score": 0.80,
        "version": "2",
        "supersedes": "1",
    }


@pytest.fixture
def future_chunk():
    return {
        "chunk_id": "c4",
        "text": "Starting 2027, the new pricing will be $40/month.",
        "score": 0.75,
    }


@pytest.fixture
def unknown_chunk():
    return {
        "chunk_id": "c5",
        "text": "The pricing model includes Basic, Pro, and Enterprise tiers.",
        "score": 0.70,
    }


@pytest.fixture
def time_bounded_chunk():
    return {
        "chunk_id": "c6",
        "text": "This policy is effective from 2023-01-01 until 2024-12-31.",
        "score": 0.80,
    }


@pytest.fixture
def effective_date_chunk():
    return {
        "chunk_id": "c7",
        "text": "Published January 2026. Effective from 2026-03-01 the new rate applies.",
        "score": 0.85,
    }


# ── RQ2: Query Temporal Intent ───────────────────────────────────────

class TestQueryTemporalIntent:

    def test_current_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "What is the current price?"
        ) == QueryTemporalIntent.CURRENT

    def test_current_latest(self, analyzer):
        assert analyzer.extract_query_intent(
            "Show me the latest version"
        ) == QueryTemporalIntent.CURRENT

    def test_current_active(self, analyzer):
        assert analyzer.extract_query_intent(
            "What is the active policy?"
        ) == QueryTemporalIntent.CURRENT

    def test_historical_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "What was the pricing previously?"
        ) == QueryTemporalIntent.HISTORICAL

    def test_historical_legacy(self, analyzer):
        assert analyzer.extract_query_intent(
            "Show the legacy configuration"
        ) == QueryTemporalIntent.HISTORICAL

    def test_future_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "What will the price be next year?"
        ) == QueryTemporalIntent.FUTURE

    def test_future_planned(self, analyzer):
        assert analyzer.extract_query_intent(
            "What are the planned changes?"
        ) == QueryTemporalIntent.FUTURE

    def test_time_range_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "What changed between 2023 and 2025?"
        ) == QueryTemporalIntent.TIME_RANGE

    def test_point_in_time_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "What was the policy in 2023?"
        ) == QueryTemporalIntent.POINT_IN_TIME

    def test_unknown_query(self, analyzer):
        assert analyzer.extract_query_intent(
            "Explain the pricing model"
        ) == QueryTemporalIntent.UNKNOWN

    def test_unknown_generic(self, analyzer):
        assert analyzer.extract_query_intent(
            "How does authentication work?"
        ) == QueryTemporalIntent.UNKNOWN


# ── RQ1: Evidence Temporal Metadata ──────────────────────────────────

class TestEvidenceMetadata:

    def test_current_from_timestamp(self, analyzer, current_chunk):
        meta = analyzer.extract_evidence_metadata(current_chunk)
        assert meta.temporal_state == TemporalState.CURRENT
        assert meta.timestamp == "2025-01-15"

    def test_historical_from_year(self, analyzer, historical_chunk):
        meta = analyzer.extract_evidence_metadata(historical_chunk)
        assert meta.temporal_state == TemporalState.HISTORICAL
        assert "2022" in meta.years_mentioned

    def test_superseded_explicit(self, analyzer, superseded_chunk):
        meta = analyzer.extract_evidence_metadata(superseded_chunk)
        assert meta.temporal_state == TemporalState.SUPERSEDED
        assert meta.supersedes == "1"
        assert meta.version == "2"

    def test_time_bounded_range(self, analyzer, time_bounded_chunk):
        meta = analyzer.extract_evidence_metadata(time_bounded_chunk)
        assert meta.temporal_state == TemporalState.TIME_BOUNDED
        assert meta.effective_from == "2023-01-01"
        assert meta.effective_until == "2024-12-31"

    def test_effective_date_extraction(self, analyzer, effective_date_chunk):
        meta = analyzer.extract_evidence_metadata(effective_date_chunk)
        assert meta.effective_from == "2026-03-01"

    def test_unknown_no_metadata(self, analyzer, unknown_chunk):
        meta = analyzer.extract_evidence_metadata(unknown_chunk)
        assert meta.temporal_state == TemporalState.UNKNOWN

    def test_explicit_metadata_fields(self, analyzer):
        chunk = {
            "chunk_id": "x",
            "text": "Some text",
            "valid_from": "2024-01-01",
            "valid_until": "2025-12-31",
            "document_id": "doc-42",
        }
        meta = analyzer.extract_evidence_metadata(chunk)
        assert meta.temporal_state == TemporalState.TIME_BOUNDED
        assert meta.document_id == "doc-42"


# ── RQ3: Temporal Compatibility ──────────────────────────────────────

class TestTemporalCompatibility:

    def test_current_query_current_evidence(self, analyzer):
        meta = TemporalMetadata(temporal_state=TemporalState.CURRENT)
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.CURRENT, meta
        )
        assert result.compatibility_score >= 0.9

    def test_current_query_historical_evidence(self, analyzer):
        meta = TemporalMetadata(temporal_state=TemporalState.HISTORICAL)
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.CURRENT, meta
        )
        assert result.compatibility_score <= 0.4

    def test_historical_query_historical_evidence(self, analyzer):
        meta = TemporalMetadata(temporal_state=TemporalState.HISTORICAL)
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.HISTORICAL, meta
        )
        assert result.compatibility_score >= 0.9

    def test_current_query_superseded_evidence(self, analyzer):
        meta = TemporalMetadata(
            temporal_state=TemporalState.SUPERSEDED,
            supersedes="1",
        )
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.CURRENT, meta
        )
        assert result.compatibility_score <= 0.15

    def test_unknown_evidence_neutral(self, analyzer):
        """CRITICAL SAFETY: unknown evidence must NOT be penalized."""
        meta = TemporalMetadata(temporal_state=TemporalState.UNKNOWN)
        for intent in QueryTemporalIntent:
            result = analyzer.compute_compatibility(intent, meta)
            assert result.compatibility_score == pytest.approx(0.5, abs=0.05), \
                f"UNKNOWN evidence should be neutral for {intent}"

    def test_unknown_intent_neutral(self, analyzer):
        """CRITICAL SAFETY: unknown query intent must NOT filter."""
        for state in TemporalState:
            meta = TemporalMetadata(temporal_state=state)
            result = analyzer.compute_compatibility(
                QueryTemporalIntent.UNKNOWN, meta
            )
            assert result.compatibility_score == pytest.approx(0.5, abs=0.05), \
                f"UNKNOWN intent should be neutral for {state}"

    def test_time_range_time_bounded(self, analyzer):
        meta = TemporalMetadata(temporal_state=TemporalState.TIME_BOUNDED)
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.TIME_RANGE, meta
        )
        assert result.compatibility_score >= 0.8


# ── RQ4: Version Awareness ───────────────────────────────────────────

class TestVersionAwareness:

    def test_version_extraction(self, analyzer):
        chunk = {"chunk_id": "v", "text": "See V3.2 for details."}
        meta = analyzer.extract_evidence_metadata(chunk)
        assert meta.version == "3.2"

    def test_supersedes_extraction(self, analyzer):
        chunk = {
            "chunk_id": "s",
            "text": "This document replaces V1.0.",
        }
        meta = analyzer.extract_evidence_metadata(chunk)
        assert meta.supersedes == "1.0"
        assert meta.temporal_state == TemporalState.SUPERSEDED

    def test_version_boost_current(self, analyzer):
        meta = TemporalMetadata(
            temporal_state=TemporalState.CURRENT,
            version="3",
        )
        result = analyzer.compute_compatibility(
            QueryTemporalIntent.CURRENT, meta
        )
        assert result.compatibility_score >= 1.0


# ── Chunk Enrichment ─────────────────────────────────────────────────

class TestChunkEnrichment:

    def test_enrichment_additive(
        self, analyzer, current_chunk, historical_chunk, unknown_chunk
    ):
        chunks = [current_chunk, historical_chunk, unknown_chunk]
        original_count = len(chunks)
        enriched = analyzer.enrich_chunks("current price?", chunks, rerank=False)

        # Must not remove any chunks
        assert len(enriched) == original_count

        # All chunks must have temporal fields
        for c in enriched:
            assert "temporal_score" in c
            assert "temporal_state" in c
            assert "query_temporal_intent" in c
            assert "temporal_reason" in c

    def test_enrichment_preserves_order(
        self, analyzer, current_chunk, historical_chunk
    ):
        chunks = [current_chunk, historical_chunk]
        enriched = analyzer.enrich_chunks("test", chunks, rerank=False)
        assert enriched[0]["chunk_id"] == "c1"
        assert enriched[1]["chunk_id"] == "c2"

    def test_enrichment_preserves_original_fields(
        self, analyzer, current_chunk
    ):
        enriched = analyzer.enrich_chunks("test", [current_chunk], rerank=False)
        assert enriched[0]["score"] == 0.9
        assert enriched[0]["chunk_id"] == "c1"


# ── S15 Integration ──────────────────────────────────────────────────

class TestS15Integration:

    def test_sufficiency_with_temporal_scores(self):
        from app.evidence.sufficiency import SufficiencyEvaluator
        from app.evidence.coverage import CoverageAnalyzer
        from app.evidence.contradiction import ConflictReport

        evaluator = SufficiencyEvaluator()
        ca = CoverageAnalyzer()

        query = "What is the current pricing?"
        chunks = [
            {
                "chunk_id": "c1",
                "text": "Current pricing is $30/month in 2025.",
                "priority_score": 0.9,
                "temporal_score": 1.0,
            },
        ]
        cov = ca.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(
            query=query,
            selected_chunks=chunks,
            remaining_candidates=[],
            coverage_report=cov,
            conflict_report=conf,
        )
        assert "temporal" in result.signals
        assert result.signals["temporal"] >= 0.9

    def test_sufficiency_temporal_neutral_when_missing(self):
        from app.evidence.sufficiency import SufficiencyEvaluator
        from app.evidence.coverage import CoverageAnalyzer
        from app.evidence.contradiction import ConflictReport

        evaluator = SufficiencyEvaluator()
        ca = CoverageAnalyzer()

        query = "pricing model"
        chunks = [
            {
                "chunk_id": "c1",
                "text": "Basic and Pro tiers available.",
                "priority_score": 0.8,
            },
        ]
        cov = ca.evaluate(query, chunks)
        conf = ConflictReport(detected=False, conflict_score=0.0)

        result = evaluator.evaluate(
            query=query,
            selected_chunks=chunks,
            remaining_candidates=[],
            coverage_report=cov,
            conflict_report=conf,
        )
        # Should default to 0.5 (neutral), not crash
        assert result.signals["temporal"] == pytest.approx(0.5, abs=0.05)


# ── S14 Assembly Integration ─────────────────────────────────────────

class TestAssemblyIntegration:

    def test_with_temporal_factory(self):
        from app.evidence.assembly import EvidenceAssembler
        assembler = EvidenceAssembler.with_temporal()
        assert assembler.temporal_analyzer is not None
        assert assembler.sufficiency_evaluator is not None

    def test_assembly_enriches_chunks(self):
        from app.evidence.assembly import EvidenceAssembler

        assembler = EvidenceAssembler.with_temporal()
        query = "What is the current pricing?"
        chunks = [
            {
                "chunk_id": "c1",
                "text": "Current Pro pricing is $30/month in 2025.",
                "score": 0.9,
                "priority_score": 0.9,
            },
            {
                "chunk_id": "c2",
                "text": "In 2021, the Pro plan cost $15/month.",
                "score": 0.7,
                "priority_score": 0.7,
            },
        ]
        result = assembler.assemble(query, chunks)

        # Temporal metrics should be populated
        assert result.metrics.temporal_score >= 0.0
        assert result.metrics.query_temporal_intent != "not_evaluated"

    def test_assembly_backward_compatible(self):
        """S14 assembler without temporal must still work."""
        from app.evidence.assembly import EvidenceAssembler

        assembler = EvidenceAssembler()
        query = "pricing"
        chunks = [
            {"chunk_id": "c1", "text": "Pro is $30.", "score": 0.9},
        ]
        result = assembler.assemble(query, chunks)
        assert result.metrics.temporal_score == -1.0
        assert result.metrics.query_temporal_intent == "not_evaluated"


# ── Safety Invariants ────────────────────────────────────────────────

class TestSafetyInvariants:

    def test_no_silent_deletion(self, analyzer):
        """Temporal analysis must NEVER reduce chunk count."""
        chunks = [
            {"chunk_id": f"c{i}", "text": f"Text {i}", "score": 0.5}
            for i in range(10)
        ]
        enriched = analyzer.enrich_chunks("current price?", chunks, rerank=False)
        assert len(enriched) == 10

    def test_missing_metadata_safe(self, analyzer):
        """Chunks with zero metadata must get neutral scores."""
        chunk = {"chunk_id": "bare", "text": "Just some text."}
        score = analyzer.score_chunk("What is the price?", chunk)
        assert score == pytest.approx(0.5, abs=0.05)

    def test_empty_chunks_safe(self, analyzer):
        enriched = analyzer.enrich_chunks("test", [], rerank=False)
        assert enriched == []


# ── Config ────────────────────────────────────────────────────────────

class TestS16Config:

    def test_default_config(self):
        cfg = S16TemporalConfig()
        assert cfg.temporal_weight == 0.25
        assert cfg.unknown_neutral_score == 0.50

    def test_strict_config(self):
        cfg = S16TemporalConfig.strict()
        assert cfg.temporal_weight == 0.35
        assert cfg.superseded_penalty == 0.05

    def test_relaxed_config(self):
        cfg = S16TemporalConfig.relaxed()
        assert cfg.temporal_weight == 0.10

    def test_compatibility_lookup(self):
        cfg = S16TemporalConfig()
        assert cfg.get_compatibility("current", "current") == 1.0
        assert cfg.get_compatibility("current", "superseded") == 0.10
        assert cfg.get_compatibility("nonexistent", "state") == 0.50


# ── Mixed Corpus ─────────────────────────────────────────────────────

class TestMixedCorpus:

    def test_current_query_prefers_current_evidence(self, analyzer):
        chunks = [
            {
                "chunk_id": "old",
                "text": "In 2019, pricing was $10/month.",
                "score": 0.95,
            },
            {
                "chunk_id": "new",
                "text": "Current pricing in 2025 is $30/month.",
                "score": 0.80,
                "timestamp": "2025-01-01",
            },
        ]
        enriched = analyzer.enrich_chunks(
            "What is the current price?", chunks, rerank=False
        )
        new_score = next(c for c in enriched if c["chunk_id"] == "new")["temporal_score"]
        old_score = next(c for c in enriched if c["chunk_id"] == "old")["temporal_score"]
        assert new_score > old_score

    def test_historical_query_prefers_old_evidence(self, analyzer):
        chunks = [
            {
                "chunk_id": "old",
                "text": "In 2019, pricing was $10/month.",
                "score": 0.80,
            },
            {
                "chunk_id": "new",
                "text": "Current pricing in 2025 is $30/month.",
                "score": 0.95,
                "timestamp": "2025-01-01",
            },
        ]
        enriched = analyzer.enrich_chunks(
            "What was the price in 2019?", chunks, rerank=False
        )
        old_score = next(c for c in enriched if c["chunk_id"] == "old")["temporal_score"]
        new_score = next(c for c in enriched if c["chunk_id"] == "new")["temporal_score"]
        assert old_score > new_score
