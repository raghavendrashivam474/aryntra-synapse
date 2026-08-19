"""
app/retrieval/chunking.py

Aryntra Synapse — Sprint 0.2
Deterministic text chunking.

Responsibilities:
- Read a plain text document
- Split it into fixed-size chunks with configurable overlap
- Assign each chunk a deterministic ID
- Return structured chunk records

This module knows nothing about embeddings, FAISS, FastAPI or LLMs.
"""

from typing import List, Dict
from app.core.config import settings


def load_text(filepath: str) -> str:
    """
    Read a plain text file and return its contents as a string.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def chunk_text(
    text: str,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
    doc_id: str = "doc1",
) -> List[Dict]:
    """
    Split text into overlapping fixed-size character chunks.

    Each chunk is a dict:
        {
            "id":   "doc1_chunk_000",
            "text": "..."
        }

    Parameters
    ----------
    text         : raw document string
    chunk_size   : maximum characters per chunk
    chunk_overlap: characters repeated at the start of the next chunk
    doc_id       : prefix used when generating chunk IDs

    Returns
    -------
    List of chunk dicts, ordered by position in the document.
    """
    if not text or not text.strip():
        return []

    chunks = []
    start = 0
    index = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_text_slice = text[start:end].strip()

        if chunk_text_slice:
            chunk_id = f"{doc_id}_chunk_{index:03d}"
            chunks.append({
                "id":   chunk_id,
                "text": chunk_text_slice,
            })
            index += 1

        # Advance by chunk_size minus overlap
        step = chunk_size - chunk_overlap
        if step <= 0:
            step = chunk_size
        start += step

    return chunks


def load_and_chunk(
    filepath: str,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
    doc_id: str = "doc1",
) -> List[Dict]:
    """
    Convenience function: load a file and return its chunks.
    """
    text = load_text(filepath)
    return chunk_text(text, chunk_size, chunk_overlap, doc_id)
