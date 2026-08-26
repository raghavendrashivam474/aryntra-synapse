"""
S2 Context Compressor — compressed_v1

Deterministic, rule-based context compression applied after
retrieval and before generation.

Algorithm:
  1. Whitespace normalization
  2. Sentence-boundary truncation per chunk
  3. Structural marker removal
  4. Cross-chunk sentence deduplication

This module is intentionally simple and contains no LLM calls,
no external API dependencies, and no randomness.
"""

import re
from typing import List, Dict, Any
from difflib import SequenceMatcher


# ---------------------------------------------------------------------------
# Configuration defaults (overridable via environment / config)
# ---------------------------------------------------------------------------
DEFAULT_MAX_CHUNK_CHARS = 400
DEFAULT_DEDUP_THRESHOLD = 0.90


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_whitespace(text: str) -> str:
    """Collapse runs of 3+ newlines to 2; strip per-line."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines)


def _remove_structural_markers(text: str) -> str:
    """Remove S1-style structural headers if present."""
    patterns = [
        r'\[Source:[^\]]*\]',
        r'\[Relevance:[^\]]*\]',
        r'\[Chunk ID:[^\]]*\]',
        r'\[Score:[^\]]*\]',
        r'---+',
    ]
    for pat in patterns:
        text = re.sub(pat, '', text)
    return text.strip()


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """
    Truncate text to max_chars at the last sentence boundary.
    Sentence boundaries: '.', '!', '?' followed by space or end.
    If no boundary found, hard-truncate with ellipsis.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Find last sentence boundary within the truncated text
    boundaries = [m.end() for m in re.finditer(r'[.!?](?:\s|$)', truncated)]

    if boundaries:
        return truncated[:boundaries[-1]].strip()
    else:
        return truncated.rstrip() + '...'


def _extract_sentences(text: str) -> List[str]:
    """Split text into sentences (simple heuristic)."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _sentence_similarity(s1: str, s2: str) -> float:
    """Character-level similarity ratio between two sentences."""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_chunks(
    chunks: List[Dict[str, Any]],
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Compress a list of retrieved chunks.

    Each chunk dict is expected to have at minimum:
        - "chunk_id": str
        - "text": str
        - "score": float

    Returns a new list of chunk dicts with compressed "text" fields.
    Original chunk dicts are NOT mutated.

    Steps:
        1. Normalize whitespace
        2. Remove structural markers
        3. Truncate at sentence boundary
        4. Deduplicate sentences across chunks
    """
    if not chunks:
        return []

    compressed = []

    # --- Steps 1-3: per-chunk processing ---
    for chunk in chunks:
        text = chunk.get("text", "")

        text = _normalize_whitespace(text)
        text = _remove_structural_markers(text)
        text = _truncate_at_sentence(text, max_chunk_chars)

        compressed.append({
            "chunk_id": chunk.get("chunk_id", "unknown"),
            "text": text,
            "score": chunk.get("score", 0.0),
        })

    # --- Step 4: cross-chunk deduplication ---
    # Sort by score descending so higher-scored chunks keep their sentences
    compressed.sort(key=lambda c: c["score"], reverse=True)

    seen_sentences: List[str] = []

    for chunk in compressed:
        sentences = _extract_sentences(chunk["text"])
        kept_sentences = []

        for sent in sentences:
            is_duplicate = False
            for seen in seen_sentences:
                if _sentence_similarity(sent, seen) >= dedup_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept_sentences.append(sent)
                seen_sentences.append(sent)

        chunk["text"] = ' '.join(kept_sentences)

    # Re-sort by original chunk order (by chunk_id to be deterministic)
    # Actually, preserve retrieval order by re-sorting by score desc
    # (which matches retrieval order for FAISS cosine similarity)
    # The caller receives chunks in retrieval-score order.

    return compressed


def build_compressed_context(
    chunks: List[Dict[str, Any]],
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
) -> str:
    """
    Full pipeline: compress chunks and join into a single context string
    suitable for insertion into an LLM prompt.

    Returns the compressed context string.
    """
    if not chunks:
        return ""

    compressed = compress_chunks(
        chunks,
        max_chunk_chars=max_chunk_chars,
        dedup_threshold=dedup_threshold,
    )

    parts = []
    for i, chunk in enumerate(compressed, 1):
        if chunk["text"].strip():
            parts.append(f"[{i}] {chunk['text'].strip()}")

    return '\n\n'.join(parts)
