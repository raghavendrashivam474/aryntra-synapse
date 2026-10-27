"""
SC-S1 Conventional Retrieval Baseline.

Implements a simple, deterministic lexical retrieval-and-ranking
pipeline that operates independently of the Synapse engine.

Retrieval method:
    1. Lowercase and strip punctuation from query and document text.
    2. Tokenize on whitespace.
    3. Score each document as |query_tokens ∩ doc_tokens| / |query_tokens|.
    4. Rank descending by score; break ties alphabetically by document_id.

This baseline deliberately ignores document metadata (version, date,
status, supersedes) during retrieval and ranking.  Metadata is used
only during evaluation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from schemas import RetrievalResult, RetrievalInfo


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus(fixture_dir: Path) -> list[dict]:
    """Load all JSON policy documents from the fixture directory.

    Raises FileNotFoundError if the directory does not exist.
    Raises ValueError if a document is missing required fields.
    """
    if not fixture_dir.is_dir():
        raise FileNotFoundError(f"Fixture directory not found: {fixture_dir}")

    required_keys = {"document_id", "version", "publication_date",
                     "status", "content"}
    documents: list[dict] = []

    for path in sorted(fixture_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        missing = required_keys - doc.keys()
        if missing:
            raise ValueError(
                f"{path.name} missing required fields: {missing}"
            )
        documents.append(doc)

    if not documents:
        raise ValueError(f"No JSON documents found in {fixture_dir}")

    return documents


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

_PUNCT = re.compile(r"[^\w\s]")


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    cleaned = _PUNCT.sub("", text.lower())
    return set(cleaned.split())


# ---------------------------------------------------------------------------
# Retrieval + Ranking
# ---------------------------------------------------------------------------

RETRIEVAL_METHOD = "lexical_token_overlap"


def score_document(query_tokens: set[str], doc_text: str) -> float:
    """Fraction of query tokens found in the document text.

    Returns a float in [0.0, 1.0].  Returns 0.0 when the query
    is empty (avoids division by zero).
    """
    if not query_tokens:
        return 0.0
    doc_tokens = _tokenize(doc_text)
    overlap = query_tokens & doc_tokens
    return len(overlap) / len(query_tokens)


def retrieve(
    query: str,
    documents: list[dict],
    top_k: int = 2,
) -> RetrievalInfo:
    """Rank documents by lexical overlap with the query.

    Tie-breaking: alphabetical by document_id (ascending), which
    means the lexicographically earlier ID wins on equal scores.
    """
    if not query or not query.strip():
        raise ValueError("Query must be a non-empty string.")

    query_tokens = _tokenize(query)

    scored: list[tuple[float, str, dict]] = []
    for doc in documents:
        s = score_document(query_tokens, doc["content"])
        scored.append((s, doc["document_id"], doc))

    # Sort: highest score first, then alphabetical document_id for ties
    scored.sort(key=lambda t: (-t[0], t[1]))

    results = [
        RetrievalResult(
            document_id=doc_id,
            rank=rank,
            score=round(score, 6),
        )
        for rank, (score, doc_id, _doc) in enumerate(scored[:top_k], start=1)
    ]

    return RetrievalInfo(
        method=RETRIEVAL_METHOD,
        top_k=min(top_k, len(documents)),
        results=results,
    )