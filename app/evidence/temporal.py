"""
Aryntra Synapse - Sprint 16
Temporal & Version-Aware Evidence Analysis.

Adds temporal validity as a deterministic evidence selection signal.
Determines whether evidence is temporally appropriate for the query's
temporal intent without removing or silently suppressing any evidence.

Design invariants:
  - NEVER silently deletes evidence due to missing temporal metadata
  - UNKNOWN temporal status -> neutral compatibility (configurable, default 0.5)
  - All scoring is deterministic, zero LLM calls
  - Complements S14 contradiction detection (ConflictType.DATE), does not replace it
  - Extends S15 sufficiency as an additional signal
"""
import re
import logging
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────

class TemporalState(str, Enum):
    """Temporal classification of an evidence chunk."""
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"
    TIME_BOUNDED = "time_bounded"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class QueryTemporalIntent(str, Enum):
    """Temporal intent extracted from a user query."""
    CURRENT = "current"
    HISTORICAL = "historical"
    FUTURE = "future"
    TIME_RANGE = "time_range"
    POINT_IN_TIME = "point_in_time"
    UNKNOWN = "unknown"


# ── Data Classes ───────────────────────────────────────────────────────

@dataclass
class TemporalMetadata:
    """Structured temporal information extracted from an evidence chunk."""
    timestamp: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    version: Optional[str] = None
    supersedes: Optional[str] = None
    document_id: Optional[str] = None
    published_at: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    temporal_state: TemporalState = TemporalState.UNKNOWN
    years_mentioned: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "version": self.version,
            "supersedes": self.supersedes,
            "document_id": self.document_id,
            "published_at": self.published_at,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "temporal_state": self.temporal_state.value,
            "years_mentioned": self.years_mentioned,
        }


@dataclass
class TemporalCompatibilityResult:
    """Result of matching query temporal intent against evidence metadata."""
    compatibility_score: float
    query_intent: QueryTemporalIntent
    evidence_state: TemporalState
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compatibility_score": round(self.compatibility_score, 4),
            "query_intent": self.query_intent.value,
            "evidence_state": self.evidence_state.value,
            "reason": self.reason,
        }


# ── Analyzer ──────────────────────────────────────────────────────────

class TemporalAnalyzer:
    """
    Deterministic temporal and version-aware evidence analyzer.

    Extracts temporal metadata from evidence chunks, classifies query
    temporal intent, and computes temporal compatibility scores.

    All operations are regex/keyword-based. Zero LLM or embedding calls.
    """

    MONTH_MAP = {
        "january": "01", "jan": "01",
        "february": "02", "feb": "02",
        "march": "03", "mar": "03",
        "april": "04", "apr": "04",
        "may": "05",
        "june": "06", "jun": "06",
        "july": "07", "jul": "07",
        "august": "08", "aug": "08",
        "september": "09", "sep": "09", "sept": "09",
        "october": "10", "oct": "10",
        "november": "11", "nov": "11",
        "december": "12", "dec": "12",
    }

    # ── Query intent patterns ──
    _CURRENT_INDICATORS = {
        "current", "latest", "now", "today", "newest", "recent",
        "present", "active", "currently",
    }
    _CURRENT_PHRASES = [
        r"\bmost recent\b", r"\bup.to.date\b", r"\bas of now\b",
        r"\bright now\b", r"\bat present\b",
    ]

    _HISTORICAL_INDICATORS = {
        "previously", "formerly", "past", "history", "historical",
        "ago", "originally", "deprecated", "legacy", "prior", "back in",
    }
    _HISTORICAL_PHRASES = [
        r"\bused to\b", r"\bin the past\b", r"\bback in\b",
    ]
    _WEAK_HISTORICAL = {"was", "were", "old", "before", "earlier", "during", "in"}

    _FUTURE_INDICATORS = {
        "upcoming", "planned", "expected", "future",
        "scheduled", "projected", "anticipated",
    }
    _FUTURE_PHRASES = [
        r"\bwill be\b", r"\bgoing to\b", r"\bset to\b",
        r"\bslated for\b", r"\bnext (?:year|quarter|month)\b",
    ]

    _TIME_RANGE_PHRASES = [
        r"\bbetween\s+\d{4}\s+and\s+\d{4}\b",
        r"\bfrom\s+\d{4}\s+to\s+\d{4}\b",
        r"\bover the (?:past|last|next)\b",
    ]

    # ── Evidence extraction patterns ──
    _YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")
    _DATE_PATTERN = re.compile(r"\b((?:19|20)\d{2}-\d{2}-\d{2})\b")
    _MONTH_YEAR_PATTERN = re.compile(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+((?:19|20)\d{2})\b",
        re.IGNORECASE,
    )
    _VERSION_PATTERN = re.compile(
        r"\b[vV](?:ersion\s*)?(\d+(?:\.\d+)*)\b"
    )
    _DATE_RANGE_PATTERN = re.compile(
        r"(?:effective\s+|valid\s+)?(?:from|starting)\s+((?:19|20)\d{2}(?:-\d{2}-\d{2})?)\s+(?:until|through|to|ending)\s+((?:19|20)\d{2}(?:-\d{2}-\d{2})?)",
        re.IGNORECASE,
    )
    _EFFECTIVE_FROM_PATTERN = re.compile(
        r"(?:effective|valid)\s+(?:from|starting|as of)\s+((?:19|20)\d{2}(?:-\d{2}-\d{2})?)",
        re.IGNORECASE,
    )
    _EFFECTIVE_UNTIL_PATTERN = re.compile(
        r"(?:effective\s+|valid\s+)?(?:until|through|ending)\s+((?:19|20)\d{2}(?:-\d{2}-\d{2})?)",
        re.IGNORECASE,
    )
    _SUPERSEDES_PATTERN = re.compile(
        r"(?:supersedes?|replaces?|obsoletes?)\s+[vV]?(?:ersion\s*)?(\d+(?:\.\d+)*)",
        re.IGNORECASE,
    )

    def __init__(self, config: Optional[Any] = None):
        if config is None:
            from app.evidence.config import S16TemporalConfig
            config = S16TemporalConfig()
        self.config = config

    # ── Public API ────────────────────────────────────────────────────

    def extract_query_intent(self, query: str) -> QueryTemporalIntent:
        """Classify the temporal intent of a user query."""
        q_lower = query.lower()
        tokens = set(re.findall(r"\w+", q_lower))

        # 1. Time range (most specific)
        for pattern in self._TIME_RANGE_PHRASES:
            if re.search(pattern, q_lower):
                return QueryTemporalIntent.TIME_RANGE

        # 2. Future
        if tokens & self._FUTURE_INDICATORS:
            return QueryTemporalIntent.FUTURE
        if any(re.search(p, q_lower) for p in self._FUTURE_PHRASES):
            return QueryTemporalIntent.FUTURE

        # 3. Strong Historical indicators
        if tokens & self._HISTORICAL_INDICATORS or any(re.search(p, q_lower) for p in self._HISTORICAL_PHRASES):
            years = self._YEAR_PATTERN.findall(q_lower)
            if years and not tokens & {"history", "historical", "past"}:
                return QueryTemporalIntent.POINT_IN_TIME
            return QueryTemporalIntent.HISTORICAL

        # 4. Current
        if tokens & self._CURRENT_INDICATORS:
            return QueryTemporalIntent.CURRENT
        if any(re.search(p, q_lower) for p in self._CURRENT_PHRASES):
            return QueryTemporalIntent.CURRENT

        # 5. Point in time (Month+Year or Year mentioned)
        if self._MONTH_YEAR_PATTERN.search(q_lower) or self._YEAR_PATTERN.search(q_lower):
            return QueryTemporalIntent.POINT_IN_TIME

        return QueryTemporalIntent.UNKNOWN

    def extract_query_target_date(self, query: str) -> Optional[str]:
        """Extract target date/year/month representation from query."""
        q_lower = query.lower()
        my_match = self._MONTH_YEAR_PATTERN.search(q_lower)
        if my_match:
            month_name = my_match.group(1).lower()
            year = my_match.group(2)
            month_num = self.MONTH_MAP.get(month_name, "01")
            return f"{year}-{month_num}"

        date_match = self._DATE_PATTERN.search(q_lower)
        if date_match:
            return date_match.group(1)

        year_match = self._YEAR_PATTERN.search(q_lower)
        if year_match:
            return year_match.group(1)

        return None

    def extract_evidence_metadata(
        self, chunk: Dict[str, Any]
    ) -> TemporalMetadata:
        """Extract temporal metadata from chunk dict fields and text."""
        text = chunk.get("text", "")

        meta = TemporalMetadata(
            timestamp=chunk.get("timestamp"),
            valid_from=chunk.get("valid_from"),
            valid_until=chunk.get("valid_until"),
            version=str(chunk["version"]) if chunk.get("version") is not None else None,
            supersedes=str(chunk["supersedes"]) if chunk.get("supersedes") is not None else None,
            document_id=chunk.get("document_id"),
            published_at=chunk.get("published_at"),
            effective_from=chunk.get("effective_from"),
            effective_until=chunk.get("effective_until"),
        )

        if text:
            if not meta.years_mentioned:
                meta.years_mentioned = self._YEAR_PATTERN.findall(text)

            m_range = self._DATE_RANGE_PATTERN.search(text)
            if m_range:
                if not meta.effective_from:
                    meta.effective_from = m_range.group(1)
                if not meta.effective_until:
                    meta.effective_until = m_range.group(2)
            else:
                if not meta.effective_from:
                    m = self._EFFECTIVE_FROM_PATTERN.search(text)
                    if m:
                        meta.effective_from = m.group(1)

                if not meta.effective_until:
                    m = self._EFFECTIVE_UNTIL_PATTERN.search(text)
                    if m:
                        meta.effective_until = m.group(1)

            if not meta.version:
                m = self._VERSION_PATTERN.search(text)
                if m:
                    meta.version = m.group(1)

            if not meta.supersedes:
                m = self._SUPERSEDES_PATTERN.search(text)
                if m:
                    meta.supersedes = m.group(1)

        # Check explicit superseded status in dict
        if str(chunk.get("superseded", "")).lower() in ("true", "yes", "1"):
            meta.temporal_state = TemporalState.SUPERSEDED
        else:
            meta.temporal_state = self._classify_temporal_state(meta, text)

        return meta

    def compute_compatibility(
        self,
        query_intent: QueryTemporalIntent,
        evidence_meta: TemporalMetadata,
        query_target_date: Optional[str] = None,
    ) -> TemporalCompatibilityResult:
        """Compute temporal compatibility between query intent and evidence."""
        # Safety invariant: UNKNOWN evidence -> neutral
        if evidence_meta.temporal_state == TemporalState.UNKNOWN:
            return TemporalCompatibilityResult(
                compatibility_score=self.config.unknown_neutral_score,
                query_intent=query_intent,
                evidence_state=TemporalState.UNKNOWN,
                reason="unknown_temporal_metadata_neutral",
            )

        # Safety invariant: UNKNOWN query intent -> neutral
        if query_intent == QueryTemporalIntent.UNKNOWN:
            return TemporalCompatibilityResult(
                compatibility_score=self.config.unknown_neutral_score,
                query_intent=QueryTemporalIntent.UNKNOWN,
                evidence_state=evidence_meta.temporal_state,
                reason="unknown_query_intent_neutral",
            )

        # Specific point-in-time evaluation
        if query_intent == QueryTemporalIntent.POINT_IN_TIME and query_target_date:
            # 1. Check effective date range bounds
            if evidence_meta.effective_from and query_target_date < evidence_meta.effective_from[:len(query_target_date)]:
                # Chunk only becomes effective AFTER query target date
                return TemporalCompatibilityResult(
                    compatibility_score=0.20,
                    query_intent=query_intent,
                    evidence_state=evidence_meta.temporal_state,
                    reason="effective_after_query_date",
                )

            if evidence_meta.effective_until or evidence_meta.valid_until:
                bound = evidence_meta.effective_until or evidence_meta.valid_until
                start = evidence_meta.effective_from or evidence_meta.valid_from or "1900"
                if start[:len(query_target_date)] <= query_target_date <= bound[:len(query_target_date)]:
                    return TemporalCompatibilityResult(
                        compatibility_score=1.0,
                        query_intent=query_intent,
                        evidence_state=TemporalState.TIME_BOUNDED,
                        reason="within_effective_date_range",
                    )

            # 2. Check year mentions
            if query_target_date in evidence_meta.years_mentioned:
                return TemporalCompatibilityResult(
                    compatibility_score=1.0,
                    query_intent=query_intent,
                    evidence_state=evidence_meta.temporal_state,
                    reason="year_match",
                )
            elif evidence_meta.years_mentioned:
                # Mentioned different years
                return TemporalCompatibilityResult(
                    compatibility_score=0.25,
                    query_intent=query_intent,
                    evidence_state=evidence_meta.temporal_state,
                    reason="year_mismatch",
                )

        # Lookup from config compatibility matrix
        score = self.config.get_compatibility(
            query_intent.value, evidence_meta.temporal_state.value
        )

        # Hard rule: superseded evidence + current query -> strong penalty
        if (
            query_intent == QueryTemporalIntent.CURRENT
            and evidence_meta.temporal_state == TemporalState.SUPERSEDED
        ):
            score = min(score, self.config.superseded_penalty)

        # Version boost: versioned current evidence for current queries
        if (
            query_intent == QueryTemporalIntent.CURRENT
            and evidence_meta.version
            and evidence_meta.temporal_state == TemporalState.CURRENT
        ):
            score = min(1.0, score + self.config.version_boost)

        reason = f"intent={query_intent.value}_state={evidence_meta.temporal_state.value}"

        return TemporalCompatibilityResult(
            compatibility_score=round(score, 4),
            query_intent=query_intent,
            evidence_state=evidence_meta.temporal_state,
            reason=reason,
        )

    def score_chunk(self, query: str, chunk: Dict[str, Any]) -> float:
        """Compute temporal compatibility score for a single chunk."""
        intent = self.extract_query_intent(query)
        target_date = self.extract_query_target_date(query)
        meta = self.extract_evidence_metadata(chunk)
        result = self.compute_compatibility(intent, meta, target_date)
        return result.compatibility_score

    def enrich_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        rerank: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Add temporal_score, temporal metadata, and combined_score to each chunk.
        If rerank=True, re-orders chunks deterministically by combined_score.
        """
        intent = self.extract_query_intent(query)
        target_date = self.extract_query_target_date(query)
        w = getattr(self.config, "temporal_weight", 0.30)

        # Version pool analysis for relative version awareness
        versions = []
        for c in chunks:
            m = self.extract_evidence_metadata(c)
            if m.version:
                try:
                    v_float = float(re.sub(r"[^\d.]", "", m.version))
                    versions.append((v_float, c))
                except ValueError:
                    pass

        max_version = max([v[0] for v in versions]) if versions else None

        for chunk in chunks:
            meta = self.extract_evidence_metadata(chunk)
            
            # Version chain awareness: older versions in pool get marked superseded for current queries
            if (
                intent == QueryTemporalIntent.CURRENT
                and max_version is not None
                and meta.version
            ):
                try:
                    cur_v = float(re.sub(r"[^\d.]", "", meta.version))
                    if cur_v < max_version:
                        meta.temporal_state = TemporalState.SUPERSEDED
                    elif cur_v == max_version:
                        meta.temporal_state = TemporalState.CURRENT
                except ValueError:
                    pass

            compat = self.compute_compatibility(intent, meta, target_date)
            base_score = chunk.get("priority_score", chunk.get("score", 0.5))

            chunk["temporal_score"] = compat.compatibility_score
            chunk["temporal_state"] = compat.evidence_state.value
            chunk["query_temporal_intent"] = compat.query_intent.value
            chunk["temporal_reason"] = compat.reason

            # Combined multi-signal score including temporal signal
            combined = (1.0 - w) * base_score + w * compat.compatibility_score
            chunk["combined_score"] = round(combined, 4)

        if rerank and chunks:
            # Deterministic stable sort by combined_score descending
            return sorted(
                chunks,
                key=lambda x: (x.get("combined_score", 0.0), x.get("priority_score", 0.0)),
                reverse=True,
            )

        return chunks

    # ── Internal ──────────────────────────────────────────────────────

    def _classify_temporal_state(
        self, meta: TemporalMetadata, text: str = ""
    ) -> TemporalState:
        """Classify temporal state from extracted metadata and text."""
        # Explicit supersession -> SUPERSEDED
        if meta.supersedes:
            return TemporalState.SUPERSEDED

        # Effective date range -> TIME_BOUNDED
        if meta.effective_from and meta.effective_until:
            return TemporalState.TIME_BOUNDED
        if meta.valid_from and meta.valid_until:
            return TemporalState.TIME_BOUNDED

        # Start date only -> CURRENT (still active)
        if meta.effective_from or meta.valid_from:
            return TemporalState.CURRENT

        # Check text for legacy / past markers
        t_lower = text.lower()
        if any(w in t_lower for w in ["legacy", "deprecated", "was previously", "former"]):
            return TemporalState.HISTORICAL

        # Years mentioned in text
        if meta.years_mentioned:
            current_year = datetime.datetime.now().year
            latest_year = int(max(meta.years_mentioned))
            if latest_year >= current_year - 1:
                return TemporalState.CURRENT
            elif latest_year >= current_year - 3:
                return TemporalState.CURRENT
            else:
                return TemporalState.HISTORICAL

        # Timestamp or published_at only -> assume CURRENT
        if meta.timestamp or meta.published_at:
            return TemporalState.CURRENT

        return TemporalState.UNKNOWN
