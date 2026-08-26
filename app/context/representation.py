"""
app/context/representation.py

Aryntra Synapse — Sprint 1 & Sprint 2
Context representation layer.

Responsibilities:
- Transform retrieved chunks into a represented context structure
- Support Flat representation (Sprint 0.2 / control baseline)
- Support Structured representation (Sprint 1 experimental: relational & topological structure)
- Support Compressed representation (Sprint 2 experimental: deterministic selective compression)
- Measure representation build latency
"""

import time
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.context.compressor import build_compressed_context, compress_chunks


class BaseContextRepresenter(ABC):
    """Abstract base class for context representation strategies."""

    @property
    @abstractmethod
    def representation_type(self) -> str:
        pass

    @abstractmethod
    def represent(self, query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Represent retrieved chunks for consumption by the LLM.

        Parameters
        ----------
        query : str
            The user question.
        chunks : list of dicts
            List of retrieval dicts with keys 'chunk_id', 'text', 'score'.

        Returns
        -------
        dict with keys:
            'context_string': str (the actual context injected into the prompt)
            'representation_type': str ('flat', 'structured_v1', 'compressed_v1', etc.)
            'representation_metadata': dict (metadata, compression stats, graph)
            'build_latency': float (latency in seconds)
        """
        pass


class FlatRepresenter(BaseContextRepresenter):
    """
    Baseline flat Top-K context representation.
    Byte-identical output to Sprint 0.2 assemble_context().
    """

    @property
    def representation_type(self) -> str:
        return "flat"

    def represent(self, query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        t0 = time.perf_counter()

        if not chunks:
            context_string = "No relevant context found."
        else:
            parts = []
            for i, chunk in enumerate(chunks, start=1):
                parts.append(f"[Chunk {i}]\n{chunk['text']}")
            context_string = "\n\n".join(parts)

        build_latency = round(time.perf_counter() - t0, 6)

        return {
            "context_string": context_string,
            "representation_type": self.representation_type,
            "representation_metadata": {},
            "build_latency": build_latency,
        }


class StructuredRepresenterV1(BaseContextRepresenter):
    """
    S1 Experimental Structured Context Representation.

    Preserves explicit relationships between retrieved chunks:
    1. Document topology & sequential continuity (Chunk X -> Chunk X+1)
    2. Relevance ranking and similarity weights
    3. Shared conceptual anchors / topical intersections across chunks
    """

    @property
    def representation_type(self) -> str:
        return "structured_v1"

    def _extract_chunk_index(self, chunk_id: str) -> int:
        match = re.search(r"chunk_(\d+)", chunk_id)
        return int(match.group(1)) if match else -1

    def _extract_keywords(self, text: str) -> set:
        stopwords = {
            "the", "and", "for", "that", "with", "this", "from",
            "which", "have", "been", "were", "when", "where", "what",
            "into", "more", "some", "used", "will", "first", "also",
            "than", "only", "does", "each", "other", "their", "about"
        }
        tokens = re.findall(r"[a-zA-Z0-9_\-]{3,}", text.lower())
        return {tok for tok in tokens if tok not in stopwords and not tok.isdigit()}

    def represent(self, query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        t0 = time.perf_counter()

        if not chunks:
            build_latency = round(time.perf_counter() - t0, 6)
            return {
                "context_string": "No relevant context found.",
                "representation_type": self.representation_type,
                "representation_metadata": {"nodes": [], "edges": []},
                "build_latency": build_latency,
            }

        nodes = []
        chunk_keywords = []
        chunk_indices = []

        for i, chunk in enumerate(chunks, start=1):
            cid = chunk.get("chunk_id", f"chunk_{i}")
            seq_idx = self._extract_chunk_index(cid)
            kws = self._extract_keywords(chunk.get("text", ""))

            chunk_indices.append(seq_idx)
            chunk_keywords.append(kws)

            nodes.append({
                "rank": i,
                "chunk_id": cid,
                "score": chunk.get("score", 0.0),
                "sequence_index": seq_idx,
            })

        edges = []
        relationship_notes = []

        for i in range(len(chunks)):
            for j in range(len(chunks)):
                if i != j and chunk_indices[i] >= 0 and chunk_indices[j] >= 0:
                    if chunk_indices[j] == chunk_indices[i] + 1:
                        edges.append({
                            "source": nodes[i]["chunk_id"],
                            "target": nodes[j]["chunk_id"],
                            "relation": "immediately_precedes",
                        })
                        relationship_notes.append(
                            f"• Document Continuity: [{nodes[i]['chunk_id']}] is immediately followed by [{nodes[j]['chunk_id']}] in source document."
                        )

        for i in range(len(chunks)):
            for j in range(i + 1, len(chunks)):
                shared = chunk_keywords[i].intersection(chunk_keywords[j])
                shared_sample = sorted(list(shared))[:4]
                if shared_sample:
                    edges.append({
                        "source": nodes[i]["chunk_id"],
                        "target": nodes[j]["chunk_id"],
                        "relation": "shares_concepts",
                        "shared_concepts": shared_sample,
                    })
                    relationship_notes.append(
                        f"• Conceptual Link [{nodes[i]['chunk_id']} & {nodes[j]['chunk_id']}]: relates via ({', '.join(shared_sample)})"
                    )

        lines = []
        lines.append("=== Structured Context Relationships ===")
        if relationship_notes:
            lines.extend(relationship_notes)
        else:
            lines.append("• Chunks represent distinct topical points.")

        lines.append("")
        lines.append("=== Retrieved Evidence ===")

        for i, chunk in enumerate(chunks, start=1):
            cid = chunk.get("chunk_id", f"chunk_{i}")
            score = chunk.get("score", 0.0)
            seq_info = f" | Seq #{chunk_indices[i-1]}" if chunk_indices[i-1] >= 0 else ""
            lines.append(f"[Evidence {i} | ID: {cid} | Score: {score}{seq_info}]")
            lines.append(chunk.get("text", ""))
            lines.append("")

        context_string = "\n".join(lines).strip()
        build_latency = round(time.perf_counter() - t0, 6)

        return {
            "context_string": context_string,
            "representation_type": self.representation_type,
            "representation_metadata": {
                "nodes": nodes,
                "edges": edges,
            },
            "build_latency": build_latency,
        }


class CompressedRepresenterV1(BaseContextRepresenter):
    """
    S2 Experimental Compressed Context Representation.

    Performs deterministic post-retrieval context compression:
    1. Whitespace & delimiter normalization
    2. Structural marker removal
    3. Sentence-boundary truncation (per chunk cap)
    4. Cross-chunk semantic sentence deduplication
    """

    def __init__(self, max_chunk_chars: int = 400, dedup_threshold: float = 0.90):
        self.max_chunk_chars = max_chunk_chars
        self.dedup_threshold = dedup_threshold

    @property
    def representation_type(self) -> str:
        return "compressed_v1"

    def represent(self, query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        t0 = time.perf_counter()

        if not chunks:
            build_latency = round(time.perf_counter() - t0, 6)
            return {
                "context_string": "No relevant context found.",
                "representation_type": self.representation_type,
                "representation_metadata": {"reduction_pct": 0.0, "original_length": 0, "compressed_length": 0},
                "build_latency": build_latency,
            }

        # Calculate original flat length for reduction metric
        flat_parts = [f"[Chunk {i}]\n{chunk['text']}" for i, chunk in enumerate(chunks, 1)]
        original_length = len("\n\n".join(flat_parts))

        # Build compressed context
        context_string = build_compressed_context(
            chunks=chunks,
            max_chunk_chars=self.max_chunk_chars,
            dedup_threshold=self.dedup_threshold,
        )

        compressed_length = len(context_string)
        reduction_pct = (
            round((original_length - compressed_length) / original_length * 100, 2)
            if original_length > 0 else 0.0
        )
        compression_ratio = (
            round(compressed_length / original_length, 4)
            if original_length > 0 else 1.0
        )

        build_latency = round(time.perf_counter() - t0, 6)

        return {
            "context_string": context_string,
            "representation_type": self.representation_type,
            "representation_metadata": {
                "original_length": original_length,
                "compressed_length": compressed_length,
                "reduction_pct": reduction_pct,
                "compression_ratio": compression_ratio,
                "max_chunk_chars": self.max_chunk_chars,
                "dedup_threshold": self.dedup_threshold,
            },
            "build_latency": build_latency,
        }


def get_representer(name: str = None) -> BaseContextRepresenter:
    """Factory function to obtain the configured context representer."""
    from app.core.config import settings
    rep_name = (name or settings.context_representation).lower().strip()

    if rep_name == "flat":
        return FlatRepresenter()
    elif rep_name == "structured_v1":
        return StructuredRepresenterV1()
    elif rep_name == "compressed_v1":
        return CompressedRepresenterV1()
    else:
        raise ValueError(
            f"Unknown context representation type: '{rep_name}'. Supported: 'flat', 'structured_v1', 'compressed_v1'"
        )
