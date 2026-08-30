"""
Aryntra Synapse — Sprint 17
Evidence Relationship Graph Tests.

Covers:
  R1 — Version chain supersession
  R2 — Explicit contradiction (consumes S14)
  R3 — Same document
  R4 — Temporal adjacency
  R5 — Mixed evidence coherence
  R6 — No false relationships (precision guard)
  R7 — Transitive supersession
  R8 — Graph bounds
  R9 — Assembly integration (non-regression)
"""
import pytest
from typing import List, Dict, Any

from app.evidence.relationships import (
    RelationshipAnalyzer,
    RelationshipType,
    Relationship,
    EvidenceGraph,
)
from app.evidence.config import S17RelationshipConfig, S14ResolutionConfig
from app.evidence.assembly import EvidenceAssembler


# ── Helpers ───────────────────────────────────────────────────────────

def _chunk(
    chunk_id: str,
    text: str = "Some evidence text about policy compliance.",
    score: float = 0.80,
    document_id: str = None,
    version: str = None,
    supersedes: str = None,
    effective_from: str = None,
    effective_until: str = None,
    parent_id: str = None,
    **extra,
) -> Dict[str, Any]:
    c = {
        "chunk_id": chunk_id,
        "text": text,
        "score": score,
        "priority_score": score,
    }
    if document_id is not None:
        c["document_id"] = document_id
    if version is not None:
        c["version"] = version
    if supersedes is not None:
        c["supersedes"] = supersedes
    if effective_from is not None:
        c["effective_from"] = effective_from
    if effective_until is not None:
        c["effective_until"] = effective_until
    if parent_id is not None:
        c["parent_id"] = parent_id
    c.update(extra)
    return c


# ── R1: Version Chain ────────────────────────────────────────────────

class TestVersionChain:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_v3_supersedes_v2(self):
        a = _chunk("c1", version="3", document_id="policy_v3")
        b = _chunk("c2", version="2", document_id="policy_v2")
        edges = self.analyzer.analyze_pair(a, b)
        supersedes = [e for e in edges if e.relation == RelationshipType.SUPERSEDES]
        assert any(e.source_id == "c1" and e.target_id == "c2" for e in supersedes)

    def test_v2_supersedes_v1(self):
        a = _chunk("c1", version="2", document_id="policy_v2")
        b = _chunk("c2", version="1", document_id="policy_v1")
        edges = self.analyzer.analyze_pair(a, b)
        supersedes = [e for e in edges if e.relation == RelationshipType.SUPERSEDES]
        assert any(e.source_id == "c1" and e.target_id == "c2" for e in supersedes)

    def test_full_chain_graph(self):
        chunks = [
            _chunk("v3", version="3", document_id="policy_v3"),
            _chunk("v2", version="2", document_id="policy_v2"),
            _chunk("v1", version="1", document_id="policy_v1"),
        ]
        graph = self.analyzer.build_graph(chunks)
        # v3 supersedes v2
        assert "v2" in graph.get_supersedes("v3")
        # v2 supersedes v1
        assert "v1" in graph.get_supersedes("v2")
        # Transitive: v3 supersedes v1
        assert "v1" in graph.get_supersedes("v3")

    def test_superseded_by_inverse(self):
        a = _chunk("c1", version="3", document_id="policy_v3")
        b = _chunk("c2", version="1", document_id="policy_v1")
        edges = self.analyzer.analyze_pair(a, b)
        superseded_by = [e for e in edges if e.relation == RelationshipType.SUPERSEDED_BY]
        assert any(e.source_id == "c2" and e.target_id == "c1" for e in superseded_by)

    def test_explicit_supersedes_metadata(self):
        a = _chunk("c1", version="2", supersedes="1")
        b = _chunk("c2", version="1")
        edges = self.analyzer.analyze_pair(a, b)
        supersedes = [e for e in edges if e.relation == RelationshipType.SUPERSEDES]
        assert len(supersedes) >= 1
        assert supersedes[0].confidence == 1.0


# ── R2: Contradiction (Consumes S14) ────────────────────────────────

class TestContradiction:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_status_contradiction(self):
        a = _chunk("c1", text="The policy is enabled and active for all users.")
        b = _chunk("c2", text="The policy is disabled and deprecated for all users.")
        edges = self.analyzer.analyze_pair(a, b)
        contradicts = [e for e in edges if e.relation == RelationshipType.CONTRADICTS]
        assert len(contradicts) >= 1

    def test_negation_contradiction(self):
        a = _chunk(
            "c1",
            text="Remote access is permitted for all employees during business hours.",
        )
        b = _chunk(
            "c2",
            text="Remote access is not permitted for employees during business hours.",
        )
        edges = self.analyzer.analyze_pair(a, b)
        contradicts = [e for e in edges if e.relation == RelationshipType.CONTRADICTS]
        assert len(contradicts) >= 1

    def test_contradiction_does_not_suppress(self):
        """Safety invariant: CONTRADICTS edge exists but does NOT remove chunks."""
        a = _chunk("c1", text="The system is enabled for production use.")
        b = _chunk("c2", text="The system is disabled for production use.")
        graph = self.analyzer.build_graph([a, b])
        assert graph.node_count == 2  # Both nodes preserved
        contradicts = graph.get_relationships_by_type(RelationshipType.CONTRADICTS)
        assert len(contradicts) >= 1  # Conflict structurally marked


# ── R3: Same Document ────────────────────────────────────────────────

class TestSameDocument:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_same_document_id(self):
        a = _chunk("c1", document_id="doc_123", text="Section 1 of the policy.")
        b = _chunk("c2", document_id="doc_123", text="Section 2 of the policy.")
        edges = self.analyzer.analyze_pair(a, b)
        same_doc = [e for e in edges if e.relation == RelationshipType.SAME_DOCUMENT]
        assert len(same_doc) == 1
        assert same_doc[0].confidence == 1.0

    def test_different_documents_no_same_doc_edge(self):
        a = _chunk("c1", document_id="doc_A")
        b = _chunk("c2", document_id="doc_B")
        edges = self.analyzer.analyze_pair(a, b)
        same_doc = [e for e in edges if e.relation == RelationshipType.SAME_DOCUMENT]
        assert len(same_doc) == 0


# ── R4: Temporal Adjacency ──────────────────────────────────────────

class TestTemporalAdjacency:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_consecutive_years(self):
        a = _chunk(
            "c1",
            text="In 2023 the policy was updated.",
            document_id="policy_2023",
        )
        b = _chunk(
            "c2",
            text="In 2024 the policy was revised.",
            document_id="policy_2024",
        )
        edges = self.analyzer.analyze_pair(a, b)
        adjacent = [e for e in edges if e.relation == RelationshipType.TEMPORALLY_ADJACENT]
        assert len(adjacent) >= 1

    def test_non_adjacent_years(self):
        a = _chunk("c1", text="In 2020 the policy was created.", document_id="p2020")
        b = _chunk("c2", text="In 2024 the policy was revised.", document_id="p2024")
        edges = self.analyzer.analyze_pair(a, b)
        adjacent = [e for e in edges if e.relation == RelationshipType.TEMPORALLY_ADJACENT]
        assert len(adjacent) == 0

    def test_effective_date_continuity(self):
        a = _chunk("c1", effective_from="2023-01-01", effective_until="2024-01-01")
        b = _chunk("c2", effective_from="2024-01-01", effective_until="2025-01-01")
        edges = self.analyzer.analyze_pair(a, b)
        adjacent = [e for e in edges if e.relation == RelationshipType.TEMPORALLY_ADJACENT]
        assert len(adjacent) >= 1


# ── R5: Mixed Evidence Coherence ─────────────────────────────────────

class TestMixedEvidence:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_mixed_pool_graph(self):
        chunks = [
            _chunk("current", version="3", document_id="policy_v3",
                   text="Current policy is active and enabled."),
            _chunk("old", version="1", document_id="policy_v1",
                   text="Old policy was active and enabled."),
            _chunk("contradictor",
                   text="The policy is disabled and deprecated for all users.",
                   document_id="other_doc"),
            _chunk("distractor",
                   text="The weather forecast predicts rain tomorrow.",
                   document_id="weather"),
        ]
        graph = self.analyzer.build_graph(chunks)
        assert graph.node_count == 4
        # current supersedes old
        assert "old" in graph.get_supersedes("current")
        # No false same-doc between unrelated
        same_doc_edges = graph.get_relationships_by_type(RelationshipType.SAME_DOCUMENT)
        for e in same_doc_edges:
            ids = {e.source_id, e.target_id}
            assert "distractor" not in ids or "contradictor" not in ids


# ── R6: No False Relationships ──────────────────────────────────────

class TestNoFalseRelationships:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_unrelated_chunks_no_edges(self):
        a = _chunk("c1", text="The cat sat on the mat.", document_id="cats")
        b = _chunk("c2", text="Quantum computing uses qubits.", document_id="quantum")
        edges = self.analyzer.analyze_pair(a, b)
        # No supersession, no same-doc, no contradiction
        high_conf = [e for e in edges if e.confidence >= 0.8]
        assert len(high_conf) == 0

    def test_no_version_no_supersession(self):
        a = _chunk("c1", text="Policy A is good.", document_id="A")
        b = _chunk("c2", text="Policy B is good.", document_id="B")
        edges = self.analyzer.analyze_pair(a, b)
        supersedes = [e for e in edges if e.relation == RelationshipType.SUPERSEDES]
        assert len(supersedes) == 0


# ── R7: Transitive Supersession ──────────────────────────────────────

class TestTransitiveSupersession:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_transitive_v3_supersedes_v1(self):
        chunks = [
            _chunk("v3", version="3", document_id="p_v3"),
            _chunk("v2", version="2", document_id="p_v2"),
            _chunk("v1", version="1", document_id="p_v1"),
        ]
        graph = self.analyzer.build_graph(chunks)
        # Direct: v3->v2, v2->v1
        assert "v2" in graph.get_supersedes("v3")
        assert "v1" in graph.get_supersedes("v2")
        # Transitive: v3->v1
        assert "v1" in graph.get_supersedes("v3")

    def test_transitive_disabled(self):
        config = S17RelationshipConfig(enable_transitive_supersession=False)
        analyzer = RelationshipAnalyzer(config=config)
        chunks = [
            _chunk("v3", version="3", document_id="p_v3"),
            _chunk("v2", version="2", document_id="p_v2"),
            _chunk("v1", version="1", document_id="p_v1"),
        ]
        graph = analyzer.build_graph(chunks)
        # Direct edges still exist
        assert "v2" in graph.get_supersedes("v3")
        # But transitive v3->v1 should NOT exist (only direct v3->v2 and v2->v1)
        direct_v3_targets = [
            e.target_id for e in graph.get_outgoing_edges("v3")
            if e.relation == RelationshipType.SUPERSEDES
            and not e.metadata.get("transitive")
        ]
        # v1 should only appear via transitive (which is disabled)
        transitive_v3_targets = [
            e.target_id for e in graph.get_outgoing_edges("v3")
            if e.relation == RelationshipType.SUPERSEDES
            and e.metadata.get("transitive")
        ]
        assert "v1" not in transitive_v3_targets


# ── R8: Graph Bounds ────────────────────────────────────────────────

class TestGraphBounds:
    def setup_method(self):
        self.analyzer = RelationshipAnalyzer(config=S17RelationshipConfig())

    def test_empty_chunks(self):
        graph = self.analyzer.build_graph([])
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_single_chunk(self):
        graph = self.analyzer.build_graph([_chunk("c1")])
        assert graph.node_count == 1
        assert graph.edge_count == 0

    def test_max_nodes_cap(self):
        config = S17RelationshipConfig(max_graph_nodes=3)
        analyzer = RelationshipAnalyzer(config=config)
        chunks = [_chunk(f"c{i}") for i in range(10)]
        graph = analyzer.build_graph(chunks)
        assert graph.node_count <= 3

    def test_max_edges_cap(self):
        config = S17RelationshipConfig(max_relationship_edges=2)
        analyzer = RelationshipAnalyzer(config=config)
        chunks = [
            _chunk(f"c{i}", document_id="same_doc", version=str(i + 1))
            for i in range(5)
        ]
        graph = analyzer.build_graph(chunks)
        assert graph.edge_count <= 2


# ── R9: Assembly Integration (Non-Regression) ──────────────────────

class TestAssemblyIntegration:
    def test_assembler_with_relationships_factory(self):
        assembler = EvidenceAssembler.with_relationships()
        assert assembler.relationship_analyzer is not None

    def test_assembly_preserves_s16_behavior(self):
        """S17 must not break S16 temporal enrichment."""
        assembler = EvidenceAssembler.with_relationships()
        query = "What is the current policy?"
        chunks = [
            _chunk("v3", text="Current policy v3 is active.", version="3",
                   document_id="policy_v3", score=0.90),
            _chunk("v1", text="Old policy v1 was active.", version="1",
                   document_id="policy_v1", score=0.85),
        ]
        result = assembler.assemble(query, chunks)
        assert len(result.selected_chunks) >= 1
        assert result.evidence_graph is not None
        assert result.evidence_graph.node_count >= 1

    def test_assembly_result_has_graph(self):
        assembler = EvidenceAssembler.with_relationships()
        query = "policy compliance"
        chunks = [
            _chunk("c1", text="Policy compliance is mandatory.", score=0.9),
            _chunk("c2", text="Policy compliance guidelines.", score=0.8),
        ]
        result = assembler.assemble(query, chunks)
        assert hasattr(result, "evidence_graph")
        assert result.evidence_graph is not None

    def test_assembly_empty_candidates(self):
        assembler = EvidenceAssembler.with_relationships()
        result = assembler.assemble("test", [])
        assert result.evidence_graph is not None
        assert result.evidence_graph.node_count == 0

    def test_conflict_preserved_in_graph(self):
        """CONTRADICTS edges must appear in graph without suppressing evidence."""
        assembler = EvidenceAssembler.with_relationships()
        query = "system status"
        chunks = [
            _chunk("c1", text="The system is enabled and active for production.",
                   score=0.9),
            _chunk("c2", text="The system is disabled and deprecated for production.",
                   score=0.85),
        ]
        result = assembler.assemble(query, chunks)
        graph = result.evidence_graph
        contradicts = graph.get_relationships_by_type(RelationshipType.CONTRADICTS)
        # Conflict should be structurally present
        if len(result.selected_chunks) >= 2:
            assert len(contradicts) >= 1

    def test_backward_compat_no_relationships(self):
        """When relationships disabled, assembler behaves like S16."""
        assembler = EvidenceAssembler.with_temporal()
        query = "current policy"
        chunks = [
            _chunk("c1", text="Current policy is active.", version="2", score=0.9),
            _chunk("c2", text="Old policy was active.", version="1", score=0.8),
        ]
        result = assembler.assemble(query, chunks)
        assert len(result.selected_chunks) >= 1
        # evidence_graph should be None or empty when no relationship analyzer
        if result.evidence_graph is not None:
            assert result.evidence_graph.edge_count == 0


# ── EvidenceGraph Unit Tests ─────────────────────────────────────────

class TestEvidenceGraph:
    def test_add_node_and_edge(self):
        g = EvidenceGraph()
        g.add_node("a", {"text": "hello"})
        g.add_node("b", {"text": "world"})
        g.add_edge(Relationship("a", "b", RelationshipType.SUPERSEDES))
        assert g.node_count == 2
        assert g.edge_count == 1

    def test_no_duplicate_edges(self):
        g = EvidenceGraph()
        g.add_node("a", {})
        g.add_node("b", {})
        e = Relationship("a", "b", RelationshipType.SUPERSEDES)
        g.add_edge(e)
        g.add_edge(e)
        assert g.edge_count == 1

    def test_get_contradictions(self):
        g = EvidenceGraph()
        g.add_node("a", {})
        g.add_node("b", {})
        g.add_edge(Relationship("a", "b", RelationshipType.CONTRADICTS))
        assert "b" in g.get_contradictions("a")
        assert "a" in g.get_contradictions("b")

    def test_to_dict(self):
        g = EvidenceGraph()
        g.add_node("a", {"document_id": "doc1"})
        d = g.to_dict()
        assert d["node_count"] == 1
        assert "a" in d["nodes"]

    def test_version_chain_lookup(self):
        g = EvidenceGraph()
        for cid in ["v1", "v2", "v3"]:
            g.add_node(cid, {})
        g.add_edge(Relationship("v3", "v2", RelationshipType.SUPERSEDES))
        g.add_edge(Relationship("v2", "v1", RelationshipType.SUPERSEDES))
        chain = g.get_version_chain("v3")
        assert set(chain) == {"v1", "v2", "v3"}


# ── Config Tests ─────────────────────────────────────────────────────

class TestS17Config:
    def test_balanced_defaults(self):
        cfg = S17RelationshipConfig.balanced()
        assert cfg.relationship_enabled is True
        assert cfg.relationship_weight > 0.0

    def test_disabled_mode(self):
        cfg = S17RelationshipConfig.disabled()
        assert cfg.relationship_enabled is False
        assert cfg.relationship_weight == 0.0

    def test_strict_mode(self):
        cfg = S17RelationshipConfig.strict()
        assert cfg.superseded_candidate_demotion > 0.2
