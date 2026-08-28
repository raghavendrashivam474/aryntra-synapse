"""
experiments/s9_efficiency_ablation.py

Aryntra Synapse — Sprint 9
Evidence Processing Efficiency Ablation Benchmark

Compares:
  - Control: Pure S8 Baseline (Full Blend weights, no caches, no lexical gate)
  - Exp A: S8 + Evidence Embedding Cache
  - Exp B: S8 + Query Embedding Cache
  - Exp C: S8 + Lexical Fast-Path Gate
  - Exp D: S8 + Evidence Cache + Lexical Fast-Path Gate
  - Exp E: S8 Full Optimization Blend (Query Cache + Evidence Cache + Lexical Gate)

Dataset: Standard S8 evaluation queries + repeated query pass to simulate warm cache & multi-turn interaction.
"""

import sys
import json
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.retrieval.embeddings import EmbeddingModel
from app.context.evidence_store import EvidenceStore
from app.context.evidence_priority import (
    EvidencePriorityEngine,
    EvidencePriorityWeights,
    PriorityClass,
)
from app.context.workspace import EvidenceWorkspace
from app.context.sufficiency import SufficiencyEngine, SemanticSufficiencyEngine
from app.context.semantic_gate import SemanticGate
from app.optimization.embedding_cache import EmbeddingCache
from app.optimization.semantic_gate import LexicalSemanticGate

TEST_QUERIES = [
    {"id": "Q1", "query": "What is the core architecture of Aryntra Synapse?", "topic": "Architecture"},
    {"id": "Q2", "query": "How does context compression reduce token usage?", "topic": "Compression"},
    {"id": "Q3", "query": "What is the role of the evidence workspace in managing context?", "topic": "Workspace"},
    {"id": "Q4", "query": "How does deterministic sufficiency evaluate keyword coverage?", "topic": "Sufficiency"},
    {"id": "Q5", "query": "What are the benefits of cross-query evidence reuse and fingerprinting?", "topic": "Reuse"},
    # Repeat sequence to evaluate real-world warm cache hit rates
    {"id": "Q1_rep", "query": "What is the core architecture of Aryntra Synapse?", "topic": "Architecture (Repeat)"},
    {"id": "Q3_rep", "query": "What is the role of the evidence workspace in managing context?", "topic": "Workspace (Repeat)"},
]

CONFIGURATIONS = {
    "Control_S8_Baseline": {
        "description": "S8 Baseline (Full blend scoring, no caches, no gate)",
        "use_query_cache": False,
        "use_evidence_cache": False,
        "use_gate": False,
    },
    "Exp_A_Evidence_Cache": {
        "description": "S8 + Evidence Embedding Cache",
        "use_query_cache": False,
        "use_evidence_cache": True,
        "use_gate": False,
    },
    "Exp_B_Query_Cache": {
        "description": "S8 + Query Embedding Cache",
        "use_query_cache": True,
        "use_evidence_cache": False,
        "use_gate": False,
    },
    "Exp_C_Lexical_Gate": {
        "description": "S8 + Lexical Fast-Path Gate",
        "use_query_cache": False,
        "use_evidence_cache": False,
        "use_gate": True,
    },
    "Exp_D_Evidence_Cache_Plus_Gate": {
        "description": "S8 + Evidence Cache + Lexical Fast-Path Gate",
        "use_query_cache": False,
        "use_evidence_cache": True,
        "use_gate": True,
    },
    "Exp_E_Full_Blend": {
        "description": "S8 + Query Cache + Evidence Cache + Lexical Fast-Path Gate",
        "use_query_cache": True,
        "use_evidence_cache": True,
        "use_gate": True,
    },
}


def run_benchmark():
    print("=" * 80)
    print("  ARYNTRA SYNAPSE — SPRINT 9 EVIDENCE PROCESSING EFFICIENCY ABLATION")
    print("=" * 80)

    # 1. Initialize retriever and index sample data
    retriever = Retriever()
    chunks = load_and_chunk(settings.sample_document)
    retriever.index_chunks(chunks)
    embedder = retriever._embedding_model

    # Initialize S5/S6 sufficiency engines
    lexical_engine = SufficiencyEngine(
        score_threshold=settings.sufficiency_score_threshold,
        coverage_threshold=settings.sufficiency_coverage_threshold,
    )
    semantic_gate_suff = SemanticGate(embedder)
    blended_sufficiency = SemanticSufficiencyEngine(
        lexical_engine=lexical_engine,
        semantic_gate=semantic_gate_suff,
        semantic_threshold=settings.semantic_sufficiency_threshold,
        mode="blended",
    )

    all_results = {}

    for config_name, config in CONFIGURATIONS.items():
        print(f"\nEvaluating: [{config_name}] — {config['description']}")
        print("-" * 80)

        store = EvidenceStore()
        q_cache = EmbeddingCache(max_entries=1024) if config["use_query_cache"] else None
        ev_cache = EmbeddingCache(max_entries=4096) if config["use_evidence_cache"] else None
        gate = LexicalSemanticGate(high_confidence=0.60, low_confidence=0.05) if config["use_gate"] else None

        engine = EvidencePriorityEngine(
            embedding_model=embedder,
            weights=EvidencePriorityWeights.full_blend(),
            query_cache=q_cache,
            evidence_cache=ev_cache,
            semantic_gate=gate,
        )

        query_results = []
        total_semantic_evals = 0

        for q_item in TEST_QUERIES:
            qid = q_item["id"]
            query = q_item["query"]

            t0 = time.perf_counter()

            # 1. Retrieval
            retrieval_res = retriever.query(query, top_k=5)
            retrieved = retrieval_res["results"]
            retrieval_latency = retrieval_res["retrieval_latency"]

            # 2. S7 Reuse Tagging
            tagged_chunks, reuse_metrics = store.process(retrieved)

            # 3. S8 / S9 Priority Scoring
            ranked_chunks, p_metrics = engine.rank(query, tagged_chunks)
            total_semantic_evals += p_metrics.semantic_calls

            # 4. Workspace simulation
            workspace = EvidenceWorkspace(chunks=ranked_chunks, max_active=settings.max_active_chunks)
            workspace.promote_priority_initial(fallback_count=1)

            expansion_steps = 0
            stop_reason = "unknown"

            while True:
                active = workspace.active()
                suff = blended_sufficiency.evaluate(query, active)

                if suff.is_sufficient:
                    stop_reason = "evidence_sufficient"
                    break
                if not workspace.has_available():
                    stop_reason = "no_more_evidence"
                    break
                if expansion_steps >= settings.max_expansion_steps:
                    stop_reason = "max_expansion_reached"
                    break

                workspace.promote_next(reason=suff.reason)
                expansion_steps += 1

            final_context = workspace.build_active_context()
            total_latency = time.perf_counter() - t0

            q_rec = {
                "id": qid,
                "query": query,
                "topic": q_item["topic"],
                "active_chunks": workspace.active_count,
                "expansion_steps": expansion_steps,
                "stop_reason": stop_reason,
                "final_context_length": len(final_context),
                "total_latency_ms": round(total_latency * 1000, 3),
                "priority_latency_ms": round(p_metrics.priority_latency * 1000, 3),
                "semantic_latency_ms": round(p_metrics.semantic_latency * 1000, 3),
                "cache_lookup_latency_ms": round(p_metrics.cache_lookup_latency * 1000, 3),
                "semantic_calls": p_metrics.semantic_calls,
                "semantic_cache_hits": p_metrics.semantic_cache_hits,
                "query_cache_hits": p_metrics.query_cache_hits,
                "fast_path_hits": p_metrics.lexical_fast_path_hits,
                "semantic_fallbacks": p_metrics.semantic_fallback_count,
                "high_priority_count": p_metrics.high_priority_count,
                "medium_priority_count": p_metrics.medium_priority_count,
                "low_priority_count": p_metrics.low_priority_count,
            }
            query_results.append(q_rec)

            print(
                f"  {qid:<7} [{q_item['topic']:<22}]: "
                f"PriLat={q_rec['priority_latency_ms']:>6.2f}ms | "
                f"SemCalls={q_rec['semantic_calls']} | "
                f"FastPath={q_rec['fast_path_hits']} | "
                f"CacheHits={q_rec['semantic_cache_hits']+q_rec['query_cache_hits']} | "
                f"Active={q_rec['active_chunks']} | "
                f"Stop={stop_reason}"
            )

        avg_pri_lat = statistics.mean([r["priority_latency_ms"] for r in query_results])
        avg_tot_lat = statistics.mean([r["total_latency_ms"] for r in query_results])
        avg_ctx_len = statistics.mean([r["final_context_length"] for r in query_results])
        avg_active = statistics.mean([r["active_chunks"] for r in query_results])
        suff_rate = sum(1 for r in query_results if r["stop_reason"] == "evidence_sufficient") / len(query_results)

        all_results[config_name] = {
            "description": config["description"],
            "queries": query_results,
            "aggregate": {
                "avg_priority_latency_ms": round(avg_pri_lat, 3),
                "avg_total_latency_ms": round(avg_tot_lat, 3),
                "total_semantic_evals": total_semantic_evals,
                "avg_context_length": round(avg_ctx_len, 1),
                "avg_active_chunks": round(avg_active, 2),
                "sufficient_rate": round(suff_rate, 2),
                "evidence_cache_stats": ev_cache.stats() if ev_cache else None,
                "query_cache_stats": q_cache.stats() if q_cache else None,
                "gate_stats": gate.stats() if gate else None,
            },
        }

    # Save benchmark results to disk
    out_path = Path("experiments/S9_results_v1.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nBenchmark results successfully recorded to: {out_path.resolve()}")

    # Print Comparative Matrix Table
    print("\n" + "=" * 90)
    print(f"{'Configuration':<32} | {'Pri Latency':<12} | {'Total Sem Evals':<16} | {'Sufficiency Rate':<18} | {'Active Chunks'}")
    print("-" * 90)
    for c_name, data in all_results.items():
        agg = data["aggregate"]
        print(
            f"{c_name:<32} | "
            f"{agg['avg_priority_latency_ms']:>6.2f} ms     | "
            f"{agg['total_semantic_evals']:>8}         | "
            f"{agg['sufficient_rate']:>12.0%}       | "
            f"{agg['avg_active_chunks']:>6.2f}"
        )
    print("=" * 90)


if __name__ == "__main__":
    run_benchmark()
