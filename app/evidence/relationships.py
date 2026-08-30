"""
Aryntra Synapse — Sprint 17
Evidence Relationship Graph & Coherent Evidence Assembly Engine.

Introduces a deterministic relationship layer that constructs an explicit
EvidenceGraph over candidate and selected evidence chunks.

Design Invariants:
  - Zero LLM / embedding calls.
  - Pairwise bounded analysis (O(n^2)) capped by candidate pool bounds.
  - Consumes existing S14 ContradictionDetector signals for CONTRADICTS edges.
  - Consumes existing S16 TemporalAnalyzer / TemporalMetadata for SUPERSEDES edges.
  - Preserves Safety Invariant: CONTRADICTS marks conflict structurally; it NEVER suppresses evidence.
  - Conservative on SUPPORTS/ELABORATES: edges created only upon explicit deterministic references.
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Tuple

from app.evidence.contradiction import ContradictionDetector, ConflictPair, ConflictType
from app.evidence.temporal import TemporalAnalyzer, TemporalMetadata, TemporalState

logger = logging.getLogger(__name__)


# ── Relationship Vocabulary ──────────────────────────────────────────

class RelationshipType(str, Enum):
    SUPERSEDES = "SUPERSEDES"
    SUPERSEDED_BY = "SUPERSEDED_BY"
    CONTRADICTS = "CONTRADICTS"
    SAME_DOCUMENT = "SAME_DOCUMENT"
    SAME_VERSION_CHAIN = "SAME_VERSION_CHAIN"
    TEMPORALLY_ADJACENT = "TEMPORALLY_ADJACENT"
    SUPPORTS = "SUPPORTS"
    ELABORATES = "ELABORATES"


# ── Relationship Edge Representation ─────────────────────────────────

@dataclass(frozen=True)
class Relationship:
    """A directed edge in the EvidenceGraph."""
    source_id: str
    target_id: str
    relation: RelationshipType
    confidence: float = 1.0
    evidence: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


# ── Evidence Graph Representation ────────────────────────────────────

@dataclass
class EvidenceGraph:
    """
    Lightweight, bounded relationship graph over candidate or selected chunks.
    """
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Relationship] = field(default_factory=list)

    def add_node(self, chunk_id: str, chunk_data: Dict[str, Any]) -> None:
        self.nodes[chunk_id] = chunk_data

    def add_edge(self, edge: Relationship, max_edges: Optional[int] = None) -> bool:
        """Add an edge if not already present and if within max_edges limit."""
        if max_edges is not None and len(self.edges) >= max_edges:
            return False
        # Avoid duplicate edges
        for existing in self.edges:
            if (
                existing.source_id == edge.source_id
                and existing.target_id == edge.target_id
                and existing.relation == edge.relation
            ):
                return False
        self.edges.append(edge)
        return True

    def get_edges_for(self, chunk_id: str) -> List[Relationship]:
        """Return all edges where chunk_id is either source or target."""
        return [
            e for e in self.edges
            if e.source_id == chunk_id or e.target_id == chunk_id
        ]

    def get_outgoing_edges(self, chunk_id: str) -> List[Relationship]:
        return [e for e in self.edges if e.source_id == chunk_id]

    def get_incoming_edges(self, chunk_id: str) -> List[Relationship]:
        return [e for e in self.edges if e.target_id == chunk_id]

    def get_relationships_by_type(self, relation: RelationshipType) -> List[Relationship]:
        return [e for e in self.edges if e.relation == relation]

    def get_superseded_by(self, chunk_id: str) -> List[str]:
        """Return IDs of chunks that supersede chunk_id."""
        return [
            e.source_id for e in self.edges
            if e.target_id == chunk_id and e.relation == RelationshipType.SUPERSEDES
        ]

    def get_supersedes(self, chunk_id: str) -> List[str]:
        """Return IDs of chunks superseded by chunk_id."""
        return [
            e.target_id for e in self.edges
            if e.source_id == chunk_id and e.relation == RelationshipType.SUPERSEDES
        ]

    def get_contradictions(self, chunk_id: str) -> List[str]:
        """Return IDs of chunks in factual contradiction with chunk_id."""
        contradicted = set()
        for e in self.edges:
            if e.relation == RelationshipType.CONTRADICTS:
                if e.source_id == chunk_id:
                    contradicted.add(e.target_id)
                elif e.target_id == chunk_id:
                    contradicted.add(e.source_id)
        return list(contradicted)

    def get_version_chain(self, chunk_id: str) -> List[str]:
        """Return IDs of all chunks in the same version chain."""
        chain_members = {chunk_id}
        for e in self.edges:
            if e.relation in (
                RelationshipType.SAME_VERSION_CHAIN,
                RelationshipType.SUPERSEDES,
                RelationshipType.SUPERSEDED_BY,
            ):
                if e.source_id in chain_members:
                    chain_members.add(e.target_id)
                if e.target_id in chain_members:
                    chain_members.add(e.source_id)
        return list(chain_members)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": {
                k: {
                    "chunk_id": k,
                    "document_id": v.get("document_id"),
                    "version": v.get("version"),
                    "temporal_state": v.get("temporal_state"),
                }
                for k, v in self.nodes.items()
            },
            "edges": [e.to_dict() for e in self.edges],
        }


# ── Relationship Analyzer ─────────────────────────────────────────────

class RelationshipAnalyzer:
    """
    Deterministic relationship detector and graph constructor.

    Extracts high-confidence deterministic relations between evidence chunks:
      1. SUPERSEDES / SUPERSEDED_BY (version lineage & explicit supersedes)
      2. CONTRADICTS (S14 conflict engine integration)
      3. SAME_DOCUMENT (document_id or doc source matching)
      4. SAME_VERSION_CHAIN (shared lineage / document root)
      5. TEMPORALLY_ADJACENT (contiguous chronological timestamps/years)
      6. SUPPORTS / ELABORATES (deterministic section/child references)
    """

    _VERSION_NUM_PATTERN = re.compile(r"\b[vV]?(\d+(?:\.\d+)*)\b")
    _SECTION_REF_PATTERN = re.compile(
        r"(?:section|clause|paragraph|part|appendix)\s+(\d+(?:\.\d+)*)",
        re.IGNORECASE,
    )
    _SEE_ALSO_PATTERN = re.compile(
        r"(?:see|ref|reference|refer to|elaborated in|detailed in)\s+(?:doc(?:ument)?\s+)?([a-zA-Z0-9_\-\.]+)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        config: Optional[Any] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
        temporal_analyzer: Optional[TemporalAnalyzer] = None,
    ):
        from app.evidence.config import S17RelationshipConfig
        self.config = config or S17RelationshipConfig()
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.temporal_analyzer = temporal_analyzer or TemporalAnalyzer()

    # ── Pairwise Analysis ─────────────────────────────────────────────

    def analyze_pair(
        self,
        chunk_a: Dict[str, Any],
        chunk_b: Dict[str, Any],
    ) -> List[Relationship]:
        """
        Analyze a pair of evidence chunks and return all deterministic relationships.
        """
        relationships: List[Relationship] = []
        id_a = str(chunk_a.get("chunk_id", chunk_a.get("id", "A")))
        id_b = str(chunk_b.get("chunk_id", chunk_b.get("id", "B")))

        if id_a == id_b:
            return []

        meta_a = self.temporal_analyzer.extract_evidence_metadata(chunk_a)
        meta_b = self.temporal_analyzer.extract_evidence_metadata(chunk_b)

        # ── 1. Document Identity & Lineage ──
        doc_a = meta_a.document_id or chunk_a.get("document_id") or chunk_a.get("source_doc")
        doc_b = meta_b.document_id or chunk_b.get("document_id") or chunk_b.get("source_doc")

        same_doc = False
        same_lineage = False

        if doc_a and doc_b:
            if doc_a == doc_b:
                same_doc = True
                same_lineage = True
            else:
                # Check root document ID (e.g. policy_v1 and policy_v2 -> root "policy")
                root_a = re.sub(r"[-_]?[vV]\d+.*$", "", str(doc_a)).strip().lower()
                root_b = re.sub(r"[-_]?[vV]\d+.*$", "", str(doc_b)).strip().lower()
                if root_a and root_b and root_a == root_b:
                    same_lineage = True

        if same_doc and getattr(self.config, "enable_same_doc_edges", True):
            relationships.append(
                Relationship(
                    source_id=id_a,
                    target_id=id_b,
                    relation=RelationshipType.SAME_DOCUMENT,
                    confidence=1.0,
                    evidence=f"Shared document_id: {doc_a}",
                    metadata={"document_id": doc_a},
                )
            )

        if same_lineage and not same_doc and getattr(self.config, "enable_version_chain_edges", True):
            relationships.append(
                Relationship(
                    source_id=id_a,
                    target_id=id_b,
                    relation=RelationshipType.SAME_VERSION_CHAIN,
                    confidence=0.95,
                    evidence=f"Shared document lineage root: {doc_a} ~ {doc_b}",
                    metadata={"doc_a": doc_a, "doc_b": doc_b},
                )
            )

        # ── 2. Version Lineage & Supersession ──
        if getattr(self.config, "enable_supersession_edges", True):
            supersession_edges = self._detect_supersession(
                id_a, id_b, chunk_a, chunk_b, meta_a, meta_b, same_lineage or same_doc
            )
            relationships.extend(supersession_edges)

        # ── 3. Factual Contradiction (Consumes S14 Detector) ──
        if getattr(self.config, "enable_contradiction_edges", True):
            conflicts = self.contradiction_detector.analyze_pair(chunk_a, chunk_b)
            if conflicts:
                top_conflict = max(conflicts, key=lambda c: c.overlap_score)
                relationships.append(
                    Relationship(
                        source_id=id_a,
                        target_id=id_b,
                        relation=RelationshipType.CONTRADICTS,
                        confidence=top_conflict.overlap_score,
                        evidence=top_conflict.description,
                        metadata={
                            "conflict_type": top_conflict.conflict_type.value,
                            "overlap_score": top_conflict.overlap_score,
                        },
                    )
                )

        # ── 4. Temporal Adjacency ──
        if getattr(self.config, "enable_temporal_adjacency_edges", True):
            temp_edge = self._detect_temporal_adjacency(
                id_a, id_b, meta_a, meta_b, same_lineage or same_doc
            )
            if temp_edge:
                relationships.append(temp_edge)

        # ── 5. Deterministic Elaboration / Support ──
        if getattr(self.config, "enable_elaboration_edges", True):
            elab_edges = self._detect_elaboration(id_a, id_b, chunk_a, chunk_b, doc_a, doc_b)
            relationships.extend(elab_edges)

        return relationships

    # ── Graph Construction ────────────────────────────────────────────

    def build_graph(self, chunks: List[Dict[str, Any]]) -> EvidenceGraph:
        """
        Construct an EvidenceGraph from a candidate or selected list of chunks.
        Bounded pairwise analysis O(n^2).
        """
        graph = EvidenceGraph()

        if not chunks:
            return graph

        # Cap analysis to max candidates to guarantee bounded execution
        max_nodes = getattr(self.config, "max_graph_nodes", 20)
        analyzed_chunks = chunks[:max_nodes]

        for chunk in analyzed_chunks:
            cid = str(chunk.get("chunk_id", chunk.get("id", "")))
            if cid:
                graph.add_node(cid, chunk)

        n = len(analyzed_chunks)
        max_edges = getattr(self.config, "max_relationship_edges", 50)

        for i in range(n):
            for j in range(i + 1, n):
                if graph.edge_count >= max_edges:
                    break
                pair_edges = self.analyze_pair(analyzed_chunks[i], analyzed_chunks[j])
                for edge in pair_edges:
                    if not graph.add_edge(edge, max_edges=max_edges):
                        break

        # Transitive supersession inference (if enabled and space permits)
        if getattr(self.config, "enable_transitive_supersession", True) and graph.edge_count < max_edges:
            self._apply_transitive_supersession(graph, max_edges=max_edges)

        return graph

    # ── Internal Detectors ────────────────────────────────────────────

    def _detect_supersession(
        self,
        id_a: str,
        id_b: str,
        chunk_a: Dict[str, Any],
        chunk_b: Dict[str, Any],
        meta_a: TemporalMetadata,
        meta_b: TemporalMetadata,
        related_lineage: bool,
    ) -> List[Relationship]:
        """Detect explicit and version-based supersession."""
        edges: List[Relationship] = []

        v_a = self._parse_version(meta_a.version or chunk_a.get("version"))
        v_b = self._parse_version(meta_b.version or chunk_b.get("version"))

        # Case 1: Explicit supersedes tag / metadata
        sup_a = str(meta_a.supersedes or chunk_a.get("supersedes", "")).strip()
        sup_b = str(meta_b.supersedes or chunk_b.get("supersedes", "")).strip()

        if sup_a:
            if sup_a == id_b or (v_b and str(v_b[0]) in sup_a):
                edges.append(
                    Relationship(
                        source_id=id_a,
                        target_id=id_b,
                        relation=RelationshipType.SUPERSEDES,
                        confidence=1.0,
                        evidence=f"Explicit supersession: chunk {id_a} supersedes {sup_a}",
                        metadata={"explicit": True},
                    )
                )
                edges.append(
                    Relationship(
                        source_id=id_b,
                        target_id=id_a,
                        relation=RelationshipType.SUPERSEDED_BY,
                        confidence=1.0,
                        evidence=f"Explicit supersession: chunk {id_a} supersedes {sup_a}",
                        metadata={"explicit": True},
                    )
                )
                return edges

        if sup_b:
            if sup_b == id_a or (v_a and str(v_a[0]) in sup_b):
                edges.append(
                    Relationship(
                        source_id=id_b,
                        target_id=id_a,
                        relation=RelationshipType.SUPERSEDES,
                        confidence=1.0,
                        evidence=f"Explicit supersession: chunk {id_b} supersedes {sup_b}",
                        metadata={"explicit": True},
                    )
                )
                edges.append(
                    Relationship(
                        source_id=id_a,
                        target_id=id_b,
                        relation=RelationshipType.SUPERSEDED_BY,
                        confidence=1.0,
                        evidence=f"Explicit supersession: chunk {id_b} supersedes {sup_b}",
                        metadata={"explicit": True},
                    )
                )
                return edges

        # Case 2: Version hierarchy (requires related lineage or shared doc context)
        if v_a is not None and v_b is not None and (related_lineage or v_a != v_b):
            if v_a > v_b:
                edges.append(
                    Relationship(
                        source_id=id_a,
                        target_id=id_b,
                        relation=RelationshipType.SUPERSEDES,
                        confidence=0.95,
                        evidence=f"Version comparison: v{v_a} > v{v_b}",
                        metadata={"version_newer": v_a, "version_older": v_b},
                    )
                )
                edges.append(
                    Relationship(
                        source_id=id_b,
                        target_id=id_a,
                        relation=RelationshipType.SUPERSEDED_BY,
                        confidence=0.95,
                        evidence=f"Version comparison: v{v_a} > v{v_b}",
                        metadata={"version_newer": v_a, "version_older": v_b},
                    )
                )
            elif v_b > v_a:
                edges.append(
                    Relationship(
                        source_id=id_b,
                        target_id=id_a,
                        relation=RelationshipType.SUPERSEDES,
                        confidence=0.95,
                        evidence=f"Version comparison: v{v_b} > v{v_a}",
                        metadata={"version_newer": v_b, "version_older": v_a},
                    )
                )
                edges.append(
                    Relationship(
                        source_id=id_a,
                        target_id=id_b,
                        relation=RelationshipType.SUPERSEDED_BY,
                        confidence=0.95,
                        evidence=f"Version comparison: v{v_b} > v{v_a}",
                        metadata={"version_newer": v_b, "version_older": v_a},
                    )
                )

        return edges

    def _detect_temporal_adjacency(
        self,
        id_a: str,
        id_b: str,
        meta_a: TemporalMetadata,
        meta_b: TemporalMetadata,
        related_lineage: bool,
    ) -> Optional[Relationship]:
        """Detect contiguous temporal sequence between related chunks."""
        if meta_a.years_mentioned and meta_b.years_mentioned:
            try:
                y_a = int(meta_a.years_mentioned[0])
                y_b = int(meta_b.years_mentioned[0])
                if abs(y_a - y_b) == 1:
                    src = id_a if y_a < y_b else id_b
                    tgt = id_b if y_a < y_b else id_a
                    return Relationship(
                        source_id=src,
                        target_id=tgt,
                        relation=RelationshipType.TEMPORALLY_ADJACENT,
                        confidence=0.85,
                        evidence=f"Consecutive years: {min(y_a, y_b)} -> {max(y_a, y_b)}",
                        metadata={"year_from": min(y_a, y_b), "year_to": max(y_a, y_b)},
                    )
            except (ValueError, IndexError):
                pass

        if meta_a.effective_until and meta_b.effective_from:
            if meta_a.effective_until == meta_b.effective_from:
                return Relationship(
                    source_id=id_a,
                    target_id=id_b,
                    relation=RelationshipType.TEMPORALLY_ADJACENT,
                    confidence=0.90,
                    evidence=f"Date continuity: {meta_a.effective_until}",
                    metadata={"transition_date": meta_a.effective_until},
                )
        if meta_b.effective_until and meta_a.effective_from:
            if meta_b.effective_until == meta_a.effective_from:
                return Relationship(
                    source_id=id_b,
                    target_id=id_a,
                    relation=RelationshipType.TEMPORALLY_ADJACENT,
                    confidence=0.90,
                    evidence=f"Date continuity: {meta_b.effective_until}",
                    metadata={"transition_date": meta_b.effective_until},
                )

        return None

    def _detect_elaboration(
        self,
        id_a: str,
        id_b: str,
        chunk_a: Dict[str, Any],
        chunk_b: Dict[str, Any],
        doc_a: Optional[str],
        doc_b: Optional[str],
    ) -> List[Relationship]:
        """Detect deterministic elaboration or support based on explicit references."""
        edges: List[Relationship] = []
        text_a = chunk_a.get("text", "")
        text_b = chunk_b.get("text", "")

        parent_a = chunk_a.get("parent_id")
        parent_b = chunk_b.get("parent_id")
        if parent_a and parent_a == id_b:
            edges.append(
                Relationship(
                    source_id=id_a,
                    target_id=id_b,
                    relation=RelationshipType.ELABORATES,
                    confidence=1.0,
                    evidence=f"Parent-child chunk link: child {id_a} -> parent {id_b}",
                    metadata={"parent_id": id_b},
                )
            )
        if parent_b and parent_b == id_a:
            edges.append(
                Relationship(
                    source_id=id_b,
                    target_id=id_a,
                    relation=RelationshipType.ELABORATES,
                    confidence=1.0,
                    evidence=f"Parent-child chunk link: child {id_b} -> parent {id_a}",
                    metadata={"parent_id": id_a},
                )
            )

        if text_a and (id_b in text_a or (doc_b and doc_b in text_a)):
            edges.append(
                Relationship(
                    source_id=id_a,
                    target_id=id_b,
                    relation=RelationshipType.ELABORATES,
                    confidence=0.85,
                    evidence=f"Explicit reference to {id_b} / {doc_b} in text",
                    metadata={"ref": id_b},
                )
            )
        if text_b and (id_a in text_b or (doc_a and doc_a in text_a)):
            edges.append(
                Relationship(
                    source_id=id_b,
                    target_id=id_a,
                    relation=RelationshipType.ELABORATES,
                    confidence=0.85,
                    evidence=f"Explicit reference to {id_a} / {doc_a} in text",
                    metadata={"ref": id_a},
                )
            )

        return edges

    def _apply_transitive_supersession(self, graph: EvidenceGraph, max_edges: int = 50) -> None:
        """
        Infer transitive supersession:
        If A SUPERSEDES B and B SUPERSEDES C, then A SUPERSEDES C.
        """
        direct_supersedes = [
            (e.source_id, e.target_id)
            for e in graph.get_relationships_by_type(RelationshipType.SUPERSEDES)
        ]

        transitive_edges: List[Relationship] = []
        for a, b in direct_supersedes:
            for b2, c in direct_supersedes:
                if b == b2 and a != c:
                    transitive_edges.append(
                        Relationship(
                            source_id=a,
                            target_id=c,
                            relation=RelationshipType.SUPERSEDES,
                            confidence=0.90,
                            evidence=f"Transitive supersession: {a} -> {b} -> {c}",
                            metadata={"via": b, "transitive": True},
                        )
                    )
                    transitive_edges.append(
                        Relationship(
                            source_id=c,
                            target_id=a,
                            relation=RelationshipType.SUPERSEDED_BY,
                            confidence=0.90,
                            evidence=f"Transitive supersession: {a} -> {b} -> {c}",
                            metadata={"via": b, "transitive": True},
                        )
                    )

        for edge in transitive_edges:
            if not graph.add_edge(edge, max_edges=max_edges):
                break

    @classmethod
    def _parse_version(cls, version_val: Any) -> Optional[Tuple[int, ...]]:
        """Parse version string or numeric into a comparable tuple of ints."""
        if version_val is None:
            return None
        v_str = str(version_val).strip()
        match = cls._VERSION_NUM_PATTERN.search(v_str)
        if not match:
            return None
        parts = match.group(1).split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return None
