import pytest
from app.evidence.coverage import CoverageAnalyzer, CoverageReport


class TestCoverageAnalyzer:

    @pytest.fixture
    def analyzer(self):
        return CoverageAnalyzer(min_facet_coverage_threshold=0.70)

    def test_empty_chunks_coverage(self, analyzer):
        report = analyzer.evaluate("What caused the outage and when did it occur?", [])
        assert not report.is_sufficient
        assert report.coverage_ratio == 0.0
        assert len(report.missing_concepts) > 0

    def test_multi_concept_facet_extraction(self, analyzer):
        query = "What caused the cluster timeout, when did it happen, and what was the outcome?"
        facets = analyzer.extract_facets(query)
        facet_names = [f.name for f in facets]
        assert "cause" in facet_names
        assert "time" in facet_names
        assert "outcome" in facet_names

    def test_partial_vs_full_coverage(self, analyzer):
        query = "What caused the crash, when did it happen, and what was the result?"
        single_chunk = [{"chunk_id": "1", "text": "The crash was caused by an out of memory exception in worker 4."}]
        report_single = analyzer.evaluate(query, single_chunk)
        assert report_single.coverage_ratio < 0.70
        assert not report_single.is_sufficient

        all_chunks = [
            {"chunk_id": "1", "text": "The crash was caused by an out of memory exception in worker 4."},
            {"chunk_id": "2", "text": "The incident occurred when timestamp was 2024-03-15 during scheduled batch jobs."},
            {"chunk_id": "3", "text": "The outcome result was an automatic rollback of the deployment pipeline."},
        ]
        report_all = analyzer.evaluate(query, all_chunks)
        assert report_all.coverage_ratio >= 0.70
        assert report_all.is_sufficient

    def test_marginal_coverage_gain(self, analyzer):
        query = "What caused the failure and what was the recovery outcome?"
        chunk_1 = {"chunk_id": "1", "text": "The failure was caused by corrupted disk sectors."}
        chunk_2 = {"chunk_id": "2", "text": "The recovery outcome restored 100% of data from replica."}

        gain = analyzer.marginal_coverage_gain(query, [chunk_1], chunk_2)
        assert gain > 0.0
