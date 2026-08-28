"""
app/retrieval/evidence_fingerprint.py

Aryntra Synapse — Sprint 7
Deterministic evidence fingerprinting for reuse detection.

Responsibilities:
- Normalize evidence text (whitespace only, no semantic transforms)
- Produce a stable SHA-256 fingerprint from normalized text
- Zero external dependencies beyond stdlib

This module is intentionally minimal. It answers exactly one question:
"Is this the same evidence text we have seen before?"

It does NOT answer:
- "Is this evidence semantically similar?" (S6/S8 territory)
- "Is this evidence sufficient?" (S5/S6 territory)
"""

import hashlib
import re
from typing import List, Dict, Any


class EvidenceFingerprint:
    """
    Deterministic evidence identity via normalization + SHA-256.

    Normalization rules (intentionally conservative):
    - Strip leading/trailing whitespace
    - Collapse internal whitespace runs to single space
    - Normalize line endings to \\n

    What is NOT normalized:
    - Case (FAISS != faiss for identity purposes)
    - Punctuation
    - Word order
    - Synonyms

    This ensures "same evidence" means literally the same text,
    not "similar meaning."
    """

    _WHITESPACE_RE = re.compile(r"\s+")

    def normalize(self, text: str) -> str:
        """Normalize text for stable fingerprinting."""
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.strip()
        text = self._WHITESPACE_RE.sub(" ", text)
        return text

    def fingerprint(self, text: str) -> str:
        """Produce a deterministic SHA-256 hex digest from normalized text."""
        normalized = self.normalize(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def fingerprint_batch(self, texts: List[str]) -> List[str]:
        """Fingerprint multiple texts."""
        return [self.fingerprint(t) for t in texts]

    def tag_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add a 'fingerprint' key to each chunk dict.
        Returns new dicts (does not mutate originals).
        """
        tagged = []
        for chunk in chunks:
            fp = self.fingerprint(chunk.get("text", ""))
            tagged.append({**chunk, "fingerprint": fp})
        return tagged
