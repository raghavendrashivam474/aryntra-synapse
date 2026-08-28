"""
Aryntra Synapse — Sprint 11: End-to-End Quality Evaluation

Evaluates whether the adaptive context-engineering system (S1-S10)
produces better outcomes than the frozen RAG baseline.

Configs:
  A — Frozen Baseline (v0.2.0): retrieve -> generate
  B — Full Processing: retrieve -> S7 reuse -> S8 priority -> generate
  C — Adaptive Synapse: retrieve -> S7 reuse -> S10 selector -> generate

Hypothesis:
  Adaptive strategy selection can preserve the useful quality
  characteristics of richer context processing while reducing
  unnecessary computational and contextual overhead.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import re
import logging
from typing import List, Dict, Any, Tuple
import numpy as np

from app.core.config import settings
from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.llm.ollama_provider import OllamaProvider
from app.context.evidence_store import EvidenceStore
from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights
from app.optimization.embedding_cache import EmbeddingCache
from app.optimization.semantic_gate import LexicalSemanticGate
from app.strategy.selector import AdaptiveSelector

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# =====================================================================
# Query Sets (identical to S10 for comparability)
# =====================================================================

QUERIES_SIMPLE = [
    "What is Synapse?",
    "Version list",
    "Ollama mistral",
    "Chunk size",
    "Health check",
]

QUERIES_MEDIUM = [
    "How does the progressive context expansion handle tokens?",
    "What are the priority scores for high priority classes?",
    "How does semantic gate bypass work in Sprint 9?",
    "Explain the deduplication in S7 evidence reuse.",
    "How to configure embedding cache max size?",
]

QUERIES_COMPLEX = [
    "Detail the mathematical formulation of priority score blending "
    "semantic, lexical, and reuse signals with alpha beta gamma parameters.",
    "Compare the performance of the lexical semantic gate in cold and warm "
    "cache scenarios, highlighting the latency reduction and upstream "
    "routing fidelity.",
    "Explain the complete end-to-end context-engineering pipeline starting "
    "from FAISS retrieval through workspace deduplication, priority routing, "
    "sufficiency gates, and sentence-level compression.",
]

ALL_QUERIES = QUERIES_SIMPLE + QUERIES_MEDIUM + QUERIES_COMPLEX


# =====================================================================
# Quality Evaluation (deterministic heuristics — no LLM-as-judge)
# =====================================================================

REFUSAL_PHRASES = [
    "i don't know", "i cannot answer", "i'm not sure",
    "insufficient information", "not enough context",
    "i don't have enough", "unable to determine",
    "no information available", "cannot provide",
    "i do not have", "based on the provided context i cannot",
    "the provided context does not", "not mentioned in",
]


def detect_refusal(answer: str) -> bool:
    """Check if the LLM refused to answer."""
    lower = answer.lower()
    return any(phrase in lower for phrase in REFUSAL_PHRASES)


def measure_keyword_coverage(answer: str, query: str) -> float:
    """Fraction of query keywords that appear in the answer."""
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "how", "what",
        "does", "do", "in", "of", "to", "and", "for", "with", "on",
        "at", "by", "from", "or", "it", "its", "that", "this",
    }
    q_tokens = {
        t for t in re.findall(r"[a-z0-9]{3,}", query.lower())
        if t not in stop
    }
    if not q_tokens:
        return 1.0
    a_lower = answer.lower()
    matched = sum(1 for t in q_tokens if t in a_lower)
    return round(matched / len(q_tokens), 4)


def measure_evidence_grounding(answer: str, chunks: list) -> float:
    """Fraction of answer sentences that overlap with evidence text."""
    if not chunks or not answer.strip():
        return 0.0
    evidence_text = " ".join(c.get("text", "") for c in chunks).lower()
    evidence_words = set(re.findall(r"[a-z]{4,}", evidence_text))
    if not evidence_words:
        return 0.0

    sentences = [
        s.strip() for s in re.split(r"[.!?]+", answer)
        if len(s.strip()) > 10
    ]
    if not sentences:
        return 0.0

    grounded = 0
    for sent in sentences:
        sent_words = set(re.findall(r"[a-z]{4,}", sent.lower()))
        if not sent_words:
            continue
        overlap = len(sent_words & evidence_words)
        if overlap / len(sent_words) >= 0.25:
            grounded += 1
    return round(grounded / len(sentences), 4)


def detect_unsupported_numbers(answer: str, chunks: list) -> int:
    """Count numbers in the answer that don't appear in evidence."""
    evidence_text = " ".join(c.get("text", "") for c in chunks)
    ans_nums = set(re.findall(r"\b\d+\.?\d*\b", answer))
    ev_nums = set(re.findall(r"\b\d+\.?\d*\b", evidence_text))
    # Exclude very common numbers (0, 1, 2) that appear everywhere
    trivial = {"0", "1", "2", "0.0", "1.0"}
    return len((ans_nums - ev_nums) - trivial)


def evaluate_quality(query: str, answer: str, chunks: list) -> dict:
    """Produce a complete quality record for one query-answer pair."""
    refusal = detect_refusal(answer)
    keyword_cov = measure_keyword_coverage(answer, query)
    grounding = measure_evidence_grounding(answer, chunks)
    unsupported_nums = detect_unsupported_numbers(answer, chunks)
    ans_len = len(answer.strip())

    # Quality tier
    if refusal:
        tier = "REFUSAL"
    elif ans_len < 20:
        tier = "TRIVIAL"
    elif grounding >= 0.5 and keyword_cov >= 0.5 and unsupported_nums <= 1:
        tier = "GOOD"
    elif grounding >= 0.3 or keyword_cov >= 0.4:
        tier = "ACCEPTABLE"
    else:
        tier = "WEAK"

    # Failure category
    failure = "NONE"
    if refusal:
        failure = "INSUFFICIENT_EVIDENCE"
    elif grounding < 0.2 and not refusal:
        failure = "QUALITY_REGRESSION"
    elif unsupported_nums > 2:
        failure = "UNSUPPORTED_INFORMATION"
    elif keyword_cov < 0.3 and not refusal:
        failure = "MISSED_RELEVANT_EVIDENCE"

    return {
        "refusal": refusal,
        "keyword_coverage": keyword_cov,
        "evidence_grounding": grounding,
        "unsupported_numbers": unsupported_nums,
        "answer_length": ans_len,
        "quality_tier": tier,
        "failure_category": failure,
    }


# =====================================================================
# Component Initialization (mirrors routes.py wiring)
# =====================================================================

def init_components() -> dict:
    """Build all shared components once."""
    retriever = Retriever()

    if not os.path.exists(settings.sample_document):
        os.makedirs("data", exist_ok=True)
        with open(settings.sample_document, "w") as f:
            f.write(
                "Aryntra Synapse is an advanced context-processing and "
                "context-engineering engine.\n"
                "It has progressive expansion, sentence level compression "
                "and S7 reuse mechanisms.\n"
                "Priority routing categorizes chunks based on alpha and "
                "beta relevance.\n"
                "Caches are bounded LRU blocks holding up to 4096 query "
                "and chunk embeddings.\n"
                "Fast-path gates use Jaccard index overlap for cheap "
                "semantic-call bypass decisions."
            )

    chunks = load_and_chunk(settings.sample_document)
    retriever.index_chunks(chunks)

    llm = OllamaProvider()
    evidence_store = EvidenceStore()
    query_cache = EmbeddingCache(
        max_entries=settings.embedding_cache_max_entries
    )
    evidence_cache = EmbeddingCache(
        max_entries=settings.embedding_cache_max_entries
    )
    semantic_gate = LexicalSemanticGate(
        high_confidence=settings.lexical_gate_high_confidence,
        low_confidence=settings.lexical_gate_low_confidence,
    )
    priority_engine = EvidencePriorityEngine(
        embedding_model=retriever._embedding_model,
        weights=EvidencePriorityWeights(),
        query_cache=query_cache,
        evidence_cache=evidence_cache,
        semantic_gate=semantic_gate,
    )
    selector = AdaptiveSelector(mode="adaptive")

    return {
        "retriever": retriever,
        "llm": llm,
        "evidence_store": evidence_store,
        "query_cache": query_cache,
        "evidence_cache": evidence_cache,
        "priority_engine": priority_engine,
        "selector": selector,
    }


# =====================================================================
# Config Runners
# =====================================================================

def run_config_a(query: str, comp: dict) -> dict:
    """Config A — Frozen Baseline: retrieve -> generate. No processing."""
    t0 = time.perf_counter()

    ret = comp["retriever"].query(query, top_k=3)
    chunks = ret["results"]
    ret_lat = ret["retrieval_latency"]

    t_gen = time.perf_counter()
    llm_out = comp["llm"].generate(query, chunks)
    gen_lat = time.perf_counter() - t_gen

    total_lat = time.perf_counter() - t0
    quality = evaluate_quality(query, llm_out["answer"], chunks)

    return {
        "config": "A_frozen",
        "answer": llm_out["answer"],
        "retrieval_latency": round(ret_lat, 6),
        "generation_latency": round(gen_lat, 6),
        "total_latency": round(total_lat, 6),
        "preprocessing_latency": 0.0,
        "num_chunks": len(chunks),
        "context_length": llm_out.get("context_length", 0),
        "selected_path": "none",
        "selected_candidate": "none",
        "strategy_reason": "frozen_baseline",
        "semantic_calls": 0,
        "cache_hits": 0,
        "reused_count": 0,
        "high_priority_count": 0,
        "quality": quality,
    }


def run_config_b(query: str, comp: dict) -> dict:
    """Config B — Full Processing: retrieve -> S7 -> S8 deep -> generate."""
    t0 = time.perf_counter()

    ret = comp["retriever"].query(query, top_k=3)
    chunks = ret["results"]
    ret_lat = ret["retrieval_latency"]

    # S7: Evidence reuse
    tagged, reuse_metrics = comp["evidence_store"].process(chunks)
    reuse_dict = reuse_metrics.to_dict()

    # S8: Full priority ranking (always deep — no S10 bypass)
    t_pre = time.perf_counter()
    ranked, pm = comp["priority_engine"].rank(query, tagged)
    pre_lat = time.perf_counter() - t_pre
    pm_dict = pm.to_dict()

    t_gen = time.perf_counter()
    llm_out = comp["llm"].generate(query, ranked)
    gen_lat = time.perf_counter() - t_gen

    total_lat = time.perf_counter() - t0
    quality = evaluate_quality(query, llm_out["answer"], ranked)

    return {
        "config": "B_full",
        "answer": llm_out["answer"],
        "retrieval_latency": round(ret_lat, 6),
        "generation_latency": round(gen_lat, 6),
        "total_latency": round(total_lat, 6),
        "preprocessing_latency": round(pre_lat, 6),
        "num_chunks": len(ranked),
        "context_length": llm_out.get("context_length", 0),
        "selected_path": "deep_always",
        "selected_candidate": "full_processing",
        "strategy_reason": "config_b_always_deep",
        "semantic_calls": pm_dict.get("semantic_calls", 0),
        "cache_hits": (
            pm_dict.get("query_cache_hits", 0)
            + pm_dict.get("semantic_cache_hits", 0)
        ),
        "reused_count": reuse_dict.get("reused_count", 0),
        "high_priority_count": pm_dict.get("high_priority_count", 0),
        "quality": quality,
    }


def run_config_c(query: str, comp: dict) -> dict:
    """Config C — Adaptive Synapse: retrieve -> S7 -> S10 select -> generate."""
    t0 = time.perf_counter()

    ret = comp["retriever"].query(query, top_k=3)
    chunks = ret["results"]
    ret_lat = ret["retrieval_latency"]

    # S7: Evidence reuse
    tagged, reuse_metrics = comp["evidence_store"].process(chunks)
    reuse_dict = reuse_metrics.to_dict()

    # S10: Adaptive strategy selection
    t_pre = time.perf_counter()
    cache_stats = (
        comp["query_cache"].stats() if comp["query_cache"] else {}
    )
    decision = comp["selector"].select(
        query, tagged, reuse_dict, cache_stats
    )

    processed, pm_dict = comp["selector"].execute_path(
        decision=decision,
        query=query,
        chunks=tagged,
        priority_engine=comp["priority_engine"],
    )
    pre_lat = time.perf_counter() - t_pre

    t_gen = time.perf_counter()
    llm_out = comp["llm"].generate(query, processed)
    gen_lat = time.perf_counter() - t_gen

    total_lat = time.perf_counter() - t0
    quality = evaluate_quality(query, llm_out["answer"], processed)

    return {
        "config": "C_adaptive",
        "answer": llm_out["answer"],
        "retrieval_latency": round(ret_lat, 6),
        "generation_latency": round(gen_lat, 6),
        "total_latency": round(total_lat, 6),
        "preprocessing_latency": round(pre_lat, 6),
        "num_chunks": len(processed),
        "context_length": llm_out.get("context_length", 0),
        "selected_path": decision.path.value,
        "selected_candidate": decision.candidate,
        "strategy_reason": decision.reason,
        "semantic_calls": pm_dict.get("semantic_calls", 0),
        "cache_hits": (
            pm_dict.get("query_cache_hits", 0)
            + pm_dict.get("semantic_cache_hits", 0)
        ),
        "reused_count": reuse_dict.get("reused_count", 0),
        "high_priority_count": pm_dict.get("high_priority_count", 0),
        "quality": quality,
    }


# =====================================================================
# Experiment Orchestrator
# =====================================================================

def run_experiment() -> dict:
    """Run all queries through all configs with cold + warm passes."""
    print("=" * 78)
    print("  Aryntra Synapse — Sprint 11: End-to-End Quality Evaluation")
    print("=" * 78)

    comp = init_components()
    n_queries = len(ALL_QUERIES)
    print(f"[*] Components initialized.")
    print(f"[*] {n_queries} queries x 3 configs x 2 runs = {n_queries * 6} evaluations")

    all_results = {"A_frozen": [], "B_full": [], "C_adaptive": []}
    runners = {
        "A_frozen": run_config_a,
        "B_full": run_config_b,
        "C_adaptive": run_config_c,
    }

    for run_idx in range(2):
        run_label = "cold" if run_idx == 0 else "warm"
        print(f"\n--- Run {run_idx + 1} ({run_label}) ---")

        # Reset state for cold run
        if run_idx == 0:
            comp["evidence_store"].clear()
            if comp["query_cache"]:
                comp["query_cache"].clear()

        for qi, query in enumerate(ALL_QUERIES):
            tag = (
                "simple" if query in QUERIES_SIMPLE
                else "medium" if query in QUERIES_MEDIUM
                else "complex"
            )
            print(f"  [{qi + 1:2d}/{n_queries}] ({tag}) {query[:55]}...")

            for cfg_name, runner in runners.items():
                try:
                    result = runner(query, comp)
                    result["run"] = run_label
                    result["query"] = query
                    result["query_complexity"] = tag
                    all_results[cfg_name].append(result)
                    tier = result["quality"]["quality_tier"]
                    lat = result["total_latency"]
                    print(
                        f"         {cfg_name}: {tier:<11} "
                        f"lat={lat:.3f}s"
                    )
                except Exception as e:
                    logger.error("ERROR [%s] %s: %s", cfg_name, query, e)
                    all_results[cfg_name].append({
                        "config": cfg_name,
                        "run": run_label,
                        "query": query,
                        "query_complexity": tag,
                        "error": str(e),
                        "answer": "",
                        "total_latency": 0.0,
                        "quality": {
                            "quality_tier": "ERROR",
                            "failure_category": "OTHER",
                        },
                    })
                    print(f"         {cfg_name}: ERROR — {e}")

    return all_results


# =====================================================================
# Analysis
# =====================================================================

def analyze_results(results: dict) -> dict:
    """Compute aggregate metrics per configuration."""
    analysis = {}

    for cfg, traces in results.items():
        valid = [t for t in traces if "error" not in t]
        if not valid:
            analysis[cfg] = {"status": "NO_VALID_RESULTS"}
            continue

        lats = [t["total_latency"] for t in valid]
        pre_lats = [t["preprocessing_latency"] for t in valid]
        gen_lats = [t["generation_latency"] for t in valid]
        tiers = [t["quality"]["quality_tier"] for t in valid]
        failures = [
            t["quality"]["failure_category"] for t in valid
        ]
        groundings = [t["quality"]["evidence_grounding"] for t in valid]
        coverages = [t["quality"]["keyword_coverage"] for t in valid]
        refusals = sum(1 for t in valid if t["quality"]["refusal"])
        sem_calls = sum(t.get("semantic_calls", 0) for t in valid)

        good_count = sum(
            1 for t in tiers if t in ("GOOD", "ACCEPTABLE")
        )

        analysis[cfg] = {
            "total_queries": len(valid),
            "mean_total_latency": round(float(np.mean(lats)), 4),
            "p95_total_latency": round(
                float(np.percentile(lats, 95)), 4
            ),
            "mean_preprocessing_latency": round(
                float(np.mean(pre_lats)), 4
            ),
            "mean_generation_latency": round(
                float(np.mean(gen_lats)), 4
            ),
            "mean_evidence_grounding": round(
                float(np.mean(groundings)), 4
            ),
            "mean_keyword_coverage": round(
                float(np.mean(coverages)), 4
            ),
            "refusal_count": refusals,
            "refusal_rate": round(refusals / len(valid), 4),
            "total_semantic_calls": sem_calls,
            "good_or_acceptable_rate": round(
                good_count / len(valid), 4
            ),
            "quality_distribution": {
                tier: tiers.count(tier) for tier in sorted(set(tiers))
            },
            "failure_distribution": {
                cat: failures.count(cat)
                for cat in sorted(set(failures))
                if cat != "NONE"
            },
        }

        if cfg == "C_adaptive":
            paths = [t.get("selected_path", "?") for t in valid]
            analysis[cfg]["path_distribution"] = {
                p: paths.count(p) for p in sorted(set(paths))
            }

    return analysis


# =====================================================================
# Reporting
# =====================================================================

def print_summary(analysis: dict):
    """Print the main comparison table and hypothesis verdict."""
    print("\n" + "=" * 95)
    print("  S11 END-TO-END QUALITY EVALUATION SUMMARY")
    print("=" * 95)
    print(
        f"| {'Config':<14} | {'Lat(s)':<8} | {'Pre(s)':<8} | "
        f"{'Ground':<7} | {'KeyCov':<7} | {'Good%':<7} | "
        f"{'Refuse':<7} | {'SemCal':<7} |"
    )
    print("|" + "-" * 93 + "|")

    for cfg in ["A_frozen", "B_full", "C_adaptive"]:
        a = analysis.get(cfg, {})
        if a.get("status") == "NO_VALID_RESULTS":
            print(f"| {cfg:<14} | {'NO DATA':^78} |")
            continue
        print(
            f"| {cfg:<14} | {a['mean_total_latency']:<8.3f} | "
            f"{a['mean_preprocessing_latency']:<8.4f} | "
            f"{a['mean_evidence_grounding']:<7.3f} | "
            f"{a['mean_keyword_coverage']:<7.3f} | "
            f"{a['good_or_acceptable_rate']:<7.1%} | "
            f"{a['refusal_count']:<7} | "
            f"{a['total_semantic_calls']:<7} |"
        )
    print("=" * 95)

    # Hypothesis verdict
    af = analysis.get("A_frozen", {})
    ab = analysis.get("B_full", {})
    ac = analysis.get("C_adaptive", {})

    if not all("mean_total_latency" in x for x in (af, ab, ac)):
        print("\n  VERDICT: INCONCLUSIVE (insufficient data)")
        return

    q1_better = (
        ab.get("good_or_acceptable_rate", 0)
        > af.get("good_or_acceptable_rate", 0)
    )
    q2_preserved = (
        abs(
            ac.get("good_or_acceptable_rate", 0)
            - ab.get("good_or_acceptable_rate", 0)
        )
        < 0.15
    )
    q3_cheaper = (
        ac.get("mean_total_latency", 999)
        < ab.get("mean_total_latency", 0)
    )

    q1_str = "YES" if q1_better else "NO"
    q2_str = "YES" if q2_preserved else "NO"
    q3_str = "YES" if q3_cheaper else "NO"

    print("\n  KEY COMPARISONS:")
    print(f"  Q1: Full processing > Baseline quality?    -> {q1_str}")
    print(f"  Q2: Adaptive ~= Full processing quality?   -> {q2_str}")
    print(f"  Q3: Adaptive < Full processing cost?       -> {q3_str}")

    if q1_better and q2_preserved and q3_cheaper:
        verdict = "SUPPORTED"
    elif q2_preserved and q3_cheaper:
        verdict = "PARTIALLY SUPPORTED (quality preserved, cost reduced, but full vs baseline unclear)"
    elif q2_preserved:
        verdict = "PARTIALLY SUPPORTED (quality preserved but no cost reduction)"
    elif q3_cheaper:
        verdict = "PARTIALLY SUPPORTED (cost reduced but quality not preserved)"
    else:
        verdict = "INCONCLUSIVE"

    print(f"\n  S10 HYPOTHESIS VERDICT: {verdict}")

    # Path distribution for adaptive
    if "path_distribution" in ac:
        print(f"\n  ADAPTIVE PATH DISTRIBUTION: {ac['path_distribution']}")

    # Failure breakdown
    print("\n  FAILURE BREAKDOWN:")
    for cfg in ["A_frozen", "B_full", "C_adaptive"]:
        a = analysis.get(cfg, {})
        fd = a.get("failure_distribution", {})
        if fd:
            print(f"    {cfg}: {fd}")
        else:
            print(f"    {cfg}: no failures")
    print()


# =====================================================================
# Main
# =====================================================================

def main():
    results = run_experiment()
    analysis = analyze_results(results)
    print_summary(analysis)

    output = {
        "sprint": "S11",
        "version": "1.3.0",
        "purpose": "End-to-end quality evaluation",
        "hypothesis": (
            "Adaptive strategy selection preserves quality "
            "while reducing cost"
        ),
        "configs": {
            "A_frozen": "v0.2.0 baseline: retrieve then generate",
            "B_full": "Full pipeline: S7 reuse + S8 deep priority",
            "C_adaptive": "S10 adaptive selector + S7 + S8/S9",
        },
        "analysis": analysis,
        "traces": results,
    }

    os.makedirs("experiments", exist_ok=True)
    out_path = "experiments/S11_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"[+] Full results saved to {out_path}")
    print(
        f"[+] Total trace records: "
        f"{sum(len(v) for v in results.values())}"
    )


if __name__ == "__main__":
    main()
