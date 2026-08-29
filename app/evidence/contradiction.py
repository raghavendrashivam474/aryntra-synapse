"""
Aryntra Synapse — Sprint 14
Contradiction Detection Engine (Deterministic & Heuristic, Non-LLM).

Detects mutually incompatible claims across candidate evidence chunks:
- Polarity/negation mismatches on shared subject/predicate
- Numeric / metric disagreements
- Date / temporal disagreements
- Status / boolean contradictions (enabled vs disabled, active vs deprecated)
- Antonym / directional claim conflicts

IMPORTANT: Detects conflict presence and pairs; DOES NOT adjudicate truth.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Tuple, Set, Optional

from app.context.sufficiency import extract_keywords


class ConflictType(str, Enum):
    NEGATION = "negation"
    NUMERIC = "numeric"
    DATE = "date"
    STATUS = "status"
    ANTONYM = "antonym"


@dataclass(frozen=True)
class ConflictPair:
    chunk_a_id: str
    chunk_b_id: str
    conflict_type: ConflictType
    description: str
    overlap_score: float
    chunk_a_snippet: str = ""
    chunk_b_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_a_id": self.chunk_a_id,
            "chunk_b_id": self.chunk_b_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "overlap_score": round(self.overlap_score, 4),
            "chunk_a_snippet": self.chunk_a_snippet[:100],
            "chunk_b_snippet": self.chunk_b_snippet[:100],
        }


@dataclass
class ConflictReport:
    detected: bool
    conflict_score: float  # 0.0 (no conflict) to 1.0 (severe conflict)
    conflicts: List[ConflictPair] = field(default_factory=list)
    conflicted_chunk_ids: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "conflict_score": round(self.conflict_score, 4),
            "conflict_count": len(self.conflicts),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "conflicted_chunk_ids": list(self.conflicted_chunk_ids),
        }


class ContradictionDetector:
    """
    Deterministic heuristic contradiction detector.
    Analyzes pairwise evidence candidates for factual conflicts.
    """

    _NEGATION_TERMS = {
        "not", "no", "never", "cannot", "won't", "isn't", "aren't",
        "doesn't", "don't", "didn't", "unsupported", "disabled", "failed", "impossible"
    }

    _STATUS_PAIRS = [
        ({"enabled", "active", "supported", "available", "true", "success", "approved"},
         {"disabled", "deprecated", "unsupported", "unavailable", "false", "failed", "rejected"}),
        ({"increased", "rose", "growth", "expanded", "positive"},
         {"decreased", "dropped", "decline", "shrunk", "negative"}),
        ({"allowed", "permitted"}, {"forbidden", "prohibited", "blocked"}),
        ({"compatible"}, {"incompatible"}),
        ({"mandatory", "required"}, {"optional", "prohibited"}),
    ]

    _DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b")
    _NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%?\b")

    def __init__(self, topic_similarity_threshold: float = 0.30):
        self.topic_threshold = topic_similarity_threshold

    def analyze(self, chunks: List[Dict[str, Any]]) -> ConflictReport:
        """
        Analyze a list of evidence chunks for pairwise contradictions.
        """
        if len(chunks) < 2:
            return ConflictReport(detected=False, conflict_score=0.0)

        conflicts: List[ConflictPair] = []
        conflicted_ids: Set[str] = set()

        for i in range(len(chunks)):
            for j in range(i + 1, len(chunks)):
                pair_conflicts = self.analyze_pair(chunks[i], chunks[j])
                if pair_conflicts:
                    conflicts.extend(pair_conflicts)
                    conflicted_ids.add(chunks[i].get("chunk_id", str(i)))
                    conflicted_ids.add(chunks[j].get("chunk_id", str(j)))

        if not conflicts:
            return ConflictReport(
                detected=False,
                conflict_score=0.0,
                conflicts=[],
                conflicted_chunk_ids=set(),
            )

        # Scale score based on proportion of chunks conflicted and conflict severity
        total_chunks = len(chunks)
        proportion_conflicted = len(conflicted_ids) / total_chunks
        conflict_score = min(1.0, 0.4 * proportion_conflicted + 0.6 * min(1.0, len(conflicts) / max(1, total_chunks)))

        return ConflictReport(
            detected=True,
            conflict_score=conflict_score,
            conflicts=conflicts,
            conflicted_chunk_ids=conflicted_ids,
        )

    def analyze_pair(
        self,
        chunk_a: Dict[str, Any],
        chunk_b: Dict[str, Any],
    ) -> List[ConflictPair]:
        """Check if two chunks present conflicting statements on the same subject."""
        text_a = chunk_a.get("text", "")
        text_b = chunk_b.get("text", "")
        id_a = str(chunk_a.get("chunk_id", "A"))
        id_b = str(chunk_b.get("chunk_id", "B"))

        if not text_a or not text_b:
            return []

        kw_a = extract_keywords(text_a)
        kw_b = extract_keywords(text_b)

        if not kw_a or not kw_b:
            return []

        # Check topic overlap (Jaccard similarity on non-stopword keywords)
        intersection = kw_a & kw_b
        union = kw_a | kw_b
        jaccard = len(intersection) / len(union) if union else 0.0

        if jaccard < self.topic_threshold:
            # Not discussing the same topic with sufficient specificity
            return []

        conflicts = []

        # 1. Date / Year conflict on shared topic
        dates_a = set(self._DATE_PATTERN.findall(text_a))
        dates_b = set(self._DATE_PATTERN.findall(text_b))
        if dates_a and dates_b and dates_a != dates_b:
            # Different dates claimed on high topic overlap
            conflicts.append(ConflictPair(
                chunk_a_id=id_a,
                chunk_b_id=id_b,
                conflict_type=ConflictType.DATE,
                description=f"Temporal mismatch: {dates_a} vs {dates_b}",
                overlap_score=jaccard,
                chunk_a_snippet=text_a,
                chunk_b_snippet=text_b,
            ))

        # 2. Status / Antonym contradiction
        tokens_a_lower = {w.lower() for w in re.findall(r"\w+", text_a)}
        tokens_b_lower = {w.lower() for w in re.findall(r"\w+", text_b)}

        for pos_set, neg_set in self._STATUS_PAIRS:
            a_has_pos = bool(tokens_a_lower & pos_set)
            a_has_neg = bool(tokens_a_lower & neg_set)
            b_has_pos = bool(tokens_b_lower & pos_set)
            b_has_neg = bool(tokens_b_lower & neg_set)

            if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                conflicts.append(ConflictPair(
                    chunk_a_id=id_a,
                    chunk_b_id=id_b,
                    conflict_type=ConflictType.STATUS,
                    description=f"Opposing status claims detected on topic {list(intersection)[:3]}",
                    overlap_score=jaccard,
                    chunk_a_snippet=text_a,
                    chunk_b_snippet=text_b,
                ))
                break

        # 3. Explicit Negation mismatch on same core predicates
        neg_a = bool(tokens_a_lower & self._NEGATION_TERMS)
        neg_b = bool(tokens_b_lower & self._NEGATION_TERMS)
        if neg_a != neg_b and jaccard >= 0.40:
            conflicts.append(ConflictPair(
                chunk_a_id=id_a,
                chunk_b_id=id_b,
                conflict_type=ConflictType.NEGATION,
                description="Direct claim polarity mismatch (affirmative vs negated)",
                overlap_score=jaccard,
                chunk_a_snippet=text_a,
                chunk_b_snippet=text_b,
            ))

        # 4. Numeric disagreement
        nums_a = set(self._NUMBER_PATTERN.findall(text_a)) - dates_a
        nums_b = set(self._NUMBER_PATTERN.findall(text_b)) - dates_b
        if nums_a and nums_b and nums_a != nums_b and jaccard >= 0.45:
            conflicts.append(ConflictPair(
                chunk_a_id=id_a,
                chunk_b_id=id_b,
                conflict_type=ConflictType.NUMERIC,
                description=f"Metric value disagreement: {nums_a} vs {nums_b}",
                overlap_score=jaccard,
                chunk_a_snippet=text_a,
                chunk_b_snippet=text_b,
            ))

        return conflicts
