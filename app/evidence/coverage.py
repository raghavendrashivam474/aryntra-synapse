"""
Aryntra Synapse — Sprint 14
Multi-Concept Evidence Coverage Analyzer.

Identifies discrete concept facets required by the query and evaluates
how comprehensively candidate chunks cover those facets.
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
from app.context.sufficiency import extract_keywords, STOPWORDS

# Additional interrogative/auxiliary words to exclude from standalone concept facets
FACET_EXCLUSIONS = STOPWORDS | {
    "did", "does", "done", "happened", "occurred", "what", "when", "where",
    "why", "how", "who", "which", "whose", "whom"
}


@dataclass
class ConceptFacet:
    name: str
    keywords: Set[str]
    is_covered: bool = False
    covered_by_chunks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "keywords": list(self.keywords),
            "is_covered": self.is_covered,
            "covered_by_chunks": self.covered_by_chunks,
        }


@dataclass
class CoverageReport:
    query_concepts: List[str]
    covered_concepts: List[str]
    missing_concepts: List[str]
    coverage_ratio: float  # 0.0 to 1.0
    is_sufficient: bool
    facet_details: List[ConceptFacet] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_concepts": self.query_concepts,
            "covered_concepts": self.covered_concepts,
            "missing_concepts": self.missing_concepts,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "is_sufficient": self.is_sufficient,
            "facet_details": [f.to_dict() for f in self.facet_details],
        }


class CoverageAnalyzer:
    """
    Analyzes conceptual coverage of a query across a candidate evidence set.
    Extracts multi-part facets (e.g. causes, dates, outcomes, components)
    and scores marginal concept contribution per chunk.
    """

    FACET_PATTERNS = {
        "cause": {
            "patterns": [r"\b(cause|caused|causing|reason|origin|why|due to|because)\b"],
            "chunk_indicators": {"cause", "caused", "reason", "due", "because", "source", "bug", "exception", "failure", "overload", "error"},
        },
        "time": {
            "patterns": [r"\b(when|date|year|timestamp|timeline|time|period|at \d{1,2}:\d{2})\b"],
            "chunk_indicators": {"date", "time", "year", "occurred", "happened", "timestamp", "utc", "gmt", "during", "schedule", "scheduled"},
        },
        "outcome": {
            "patterns": [r"\b(outcome|result|effect|impact|consequence|aftermath|resolution|status)\b"],
            "chunk_indicators": {"outcome", "result", "effect", "impact", "loss", "rollback", "restored", "resolved", "fixed", "recovery"},
        },
        "location": {
            "patterns": [r"\b(where|region|location|place|datacenter|cluster|site)\b"],
            "chunk_indicators": {"region", "datacenter", "location", "site", "zone", "cluster", "node", "host"},
        },
        "mechanism": {
            "patterns": [r"\b(how|mechanism|process|procedure|architecture|method|steps)\b"],
            "chunk_indicators": {"mechanism", "process", "pipeline", "protocol", "architecture", "method", "algorithm"},
        },
    }

    def __init__(self, min_facet_coverage_threshold: float = 0.70):
        self.min_coverage_threshold = min_facet_coverage_threshold

    def extract_facets(self, query: str) -> List[ConceptFacet]:
        """Deconstruct query into conceptual facets."""
        q_lower = query.lower()
        facets: List[ConceptFacet] = []
        covered_kw = set()

        # 1. Structural intent facets (cause, time, outcome, location, mechanism)
        for facet_name, config in self.FACET_PATTERNS.items():
            if any(re.search(pat, q_lower) for pat in config["patterns"]):
                # Keywords associated with this facet for chunk matching
                kw = set(config["chunk_indicators"])
                facets.append(ConceptFacet(name=facet_name, keywords=kw))

        # 2. Extract specific domain entity keywords (excluding stopwords & facet grammar)
        all_kw = extract_keywords(query)
        entity_kw = {k for k in all_kw if k not in FACET_EXCLUSIONS and len(k) > 3}
        for kw in entity_kw:
            facets.append(ConceptFacet(name=kw, keywords={kw}))

        # Fallback if no specific facets detected
        if not facets:
            raw_kw = extract_keywords(query)
            facets.append(ConceptFacet(name="general", keywords=raw_kw if raw_kw else {q_lower.strip()}))

        return facets

    def evaluate(self, query: str, chunks: List[Dict[str, Any]]) -> CoverageReport:
        """Evaluate concept coverage of query across the given chunks."""
        facets = self.extract_facets(query)
        if not facets:
            return CoverageReport([], [], [], 1.0, True, [])

        if not chunks:
            return CoverageReport(
                query_concepts=[f.name for f in facets],
                covered_concepts=[],
                missing_concepts=[f.name for f in facets],
                coverage_ratio=0.0,
                is_sufficient=False,
                facet_details=facets,
            )

        covered_names = []
        missing_names = []

        for facet in facets:
            facet_covered = False
            for chunk in chunks:
                chunk_id = str(chunk.get("chunk_id", "unknown"))
                chunk_text = chunk.get("text", "").lower()
                chunk_kw = extract_keywords(chunk_text)

                # Match if keywords intersect OR any facet keyword string is in chunk text
                has_year = (facet.name == "time" and bool(re.search(r"\b(19|20)\d{2}\b", chunk_text)))
                if (facet.keywords & chunk_kw) or any(k in chunk_text for k in facet.keywords) or has_year:
                    facet.is_covered = True
                    if chunk_id not in facet.covered_by_chunks:
                        facet.covered_by_chunks.append(chunk_id)
                    facet_covered = True

            if facet_covered:
                covered_names.append(facet.name)
            else:
                missing_names.append(facet.name)

        coverage_ratio = len(covered_names) / len(facets) if facets else 1.0
        is_sufficient = coverage_ratio >= self.min_coverage_threshold

        return CoverageReport(
            query_concepts=[f.name for f in facets],
            covered_concepts=covered_names,
            missing_concepts=missing_names,
            coverage_ratio=coverage_ratio,
            is_sufficient=is_sufficient,
            facet_details=facets,
        )

    def marginal_coverage_gain(
        self,
        query: str,
        current_chunks: List[Dict[str, Any]],
        candidate_chunk: Dict[str, Any],
    ) -> float:
        """Calculate additional coverage ratio provided by adding candidate_chunk."""
        current_rep = self.evaluate(query, current_chunks)
        new_rep = self.evaluate(query, current_chunks + [candidate_chunk])
        return max(0.0, new_rep.coverage_ratio - current_rep.coverage_ratio)
