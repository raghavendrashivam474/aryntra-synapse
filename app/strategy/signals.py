"""
S10 - Cheap deterministic signal extraction for strategy selection.

All signals are computed WITHOUT embedding calls or LLM invocations.
They rely only on:
- Query text properties (length, keyword count)
- Chunk metadata (count, reuse status from S7)
- Cache statistics (hit rate from S9)
- Lexical overlap (keyword intersection with top chunk)
"""
from typing import Dict, Any, List, Optional
from app.context.sufficiency import extract_keywords


def extract_query_signals(
    query: str,
    chunks: List[Dict[str, Any]],
    reuse_metrics: Optional[Dict[str, Any]] = None,
    cache_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract cheap deterministic signals from query/evidence state.
    """
    reuse_metrics = reuse_metrics or {}
    cache_stats = cache_stats or {}

    query_tokens = query.split()
    query_keywords = extract_keywords(query)

    # Lexical overlap with first chunk (cheapest relevance proxy)
    first_chunk_lexical = 0.0
    if chunks and query_keywords:
        first_text = chunks[0].get("text", "")
        chunk_kw = extract_keywords(first_text)
        if chunk_kw:
            matched = query_keywords & chunk_kw
            first_chunk_lexical = len(matched) / len(query_keywords)

    # Average lexical overlap across all chunks
    avg_lexical = 0.0
    if chunks and query_keywords:
        overlaps = []
        for c in chunks:
            ckw = extract_keywords(c.get("text", ""))
            if ckw:
                overlaps.append(len(query_keywords & ckw) / len(query_keywords))
        avg_lexical = sum(overlaps) / len(overlaps) if overlaps else 0.0

    # Average chunk length
    avg_chunk_len = 0.0
    if chunks:
        avg_chunk_len = sum(len(c.get("text", "")) for c in chunks) / len(chunks)

    # Reuse count from chunk metadata
    reused_in_chunks = sum(
        1 for c in chunks if c.get("evidence_status") == "reused"
    )

    return {
        "query_length": len(query_tokens),
        "query_keyword_count": len(query_keywords),
        "query_char_length": len(query),
        "chunk_count": len(chunks),
        "reuse_rate": reuse_metrics.get("reuse_rate", 0.0),
        "reused_count": reuse_metrics.get("reused_count", reused_in_chunks),
        "cache_hit_rate": cache_stats.get("hit_rate", 0.0),
        "cache_hits": cache_stats.get("hits", 0),
        "cache_misses": cache_stats.get("misses", 0),
        "first_chunk_lexical_overlap": round(first_chunk_lexical, 4),
        "avg_lexical_overlap": round(avg_lexical, 4),
        "avg_chunk_length": round(avg_chunk_len, 1),
    }
