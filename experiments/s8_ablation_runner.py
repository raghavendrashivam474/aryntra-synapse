"""
experiments/s8_ablation_runner.py

Aryntra Synapse — Sprint 8
Direct in-process ablation benchmark for Evidence Relevance & Priority Management.

Ablation Configurations:
  Control: S7 baseline (unprioritized order)
  Exp-A:   S8 Semantic-only priority
  Exp-B:   S8 Lexical-only priority
  Exp-C:   S8 Blended Semantic + Lexical priority
  Exp-D:   S8 Full Blend (Semantic + Lexical + S7 Reuse)

Metrics:
  - Latency (Priority latency, Retrieval latency, Total latency)
  - Context size (Final context length, Active chunks count, Retained chunks count)
  - Priority distribution (HIGH, MEDIUM, LOW count)
  - Sufficiency stop reason
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from app.core.config import settings
from app.retrieval.chunking import load_and_chunk
from app.retrieval.retriever import Retriever
from app.retrieval.embeddings import EmbeddingModel
from app.context.evidence_store import EvidenceStore
from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights, PriorityClass
from app.context.workspace import EvidenceWorkspace
from app.context.sufficiency import SufficiencyEngine, SemanticSufficiencyEngine
from app.context.semantic_gate import SemanticGate

# Standardized queries covering diverse topics from the sample document
TEST_QUERIES = [
    {"id": "Q1", "query": "What is the core architecture of Aryntra Synapse?", "topic": "Architecture"},
    {"id": "Q2", "query": "How does context compression reduce token usage?", "topic": "Compression"},
    {"id": "Q3", "query": "What is the role of the evidence workspace in managing context?", "topic": "Workspace"},
    {"id": "Q4", "query": "How does deterministic sufficiency evaluate keyword coverage?", "topic": "Sufficiency"},
    {"id": "Q5", "query": "What are the benefits of cross-query evidence reuse and fingerprinting?", "topic": "Reuse"},
]

CONFIGURATIONS = {
    "Control_S7": {
        "description": "S7 Control (No priority routing)",
        "priority_enabled": False,
        "weights": None,
    },
    "Exp_A_Semantic_Only": {
        "description": "S8 Semantic-only priority (alpha=1.0, beta=0.0, gamma=0.0)",
        "priority_enabled": True,
        "weights": EvidencePriorityWeights.semantic_only(),
    },
    "Exp_B_Lexical_Only": {
        "description": "S8 Lexical-only priority (alpha=0.0, beta=1.0, gamma=0.0)",
        "priority_enabled": True,
        "weights": EvidencePriorityWeights.lexical_only(),
    },
    "Exp_C_Semantic_Lexical": {
        "description": "S8 Semantic + Lexical priority (alpha=0.6, beta=0.4, gamma=0.0)",
        "priority_enabled": True,
        "weights": EvidencePriorityWeights.semantic_lexical(),
    },
    "Exp_D_Full_Blend": {
        "description": "S8 Full Blend: Semantic + Lexical + Reuse (alpha=0.5, beta=0.3, gamma=0.2)",
        "priority_enabled": True,
        "weights": EvidencePriorityWeights.full_blend(),
    },
}


def run_experiment():
    print("=" * 75)
    print("  ARYNTRA SYNAPSE — SPRINT 8 EVIDENCE PRIORITY EXPERIMENT & ABLATION")
    print("=" * 75)

    # 1. Initialize retriever and index sample data
    retriever = Retriever()
    chunks = load_and_chunk(settings.sample_document)
    retriever.index_chunks(chunks)
    embedder = retriever._embedding_model

    # Initialize S5/S6 engines
    lexical_engine = SufficiencyEngine(
        score_threshold=settings.sufficiency_score_threshold,
        coverage_threshold=settings.sufficiency_coverage_threshold,
    )
    semantic_gate = SemanticGate(embedder)
    blended_sufficiency = SemanticSufficiencyEngine(
        lexical_engine=lexical_engine,
        semantic_gate=semantic_gate,
        semantic_threshold=settings.semantic_sufficiency_threshold,
        mode="blended",
    )

    all_results = {}

    for config_name, config in CONFIGURATIONS.items():
        print(f"\nEvaluating: [{config_name}] — {config['description']}")
        print("-" * 75)

        store = EvidenceStore()
        engine = (
            EvidencePriorityEngine(embedding_model=embedder, weights=config["weights"])
            if config["priority_enabled"]
            else None
        )

        config_query_results = []

        for q_item in TEST_QUERIES:
            qid = q_item["id"]
            query = q_item["query"]

            t0 = time.perf_counter()

            # Retrieval
            retrieval_res = retriever.query(query, top_k=5)
            retrieved = retrieval_res["results"]
            retrieval_latency = retrieval_res["retrieval_latency"]

            # S7 Reuse Tagging
            tagged_chunks, reuse_metrics = store.process(retrieved)

            # S8 Priority Scoring
            priority_latency = 0.0
            high_count = 0
            med_count = 0
            low_count = 0
            avg_priority_score = 0.0

            if config["priority_enabled"] and engine:
                ranked_chunks, p_metrics = engine.rank(query, tagged_chunks)
                priority_latency = p_metrics.priority_latency
                high_count = p_metrics.high_priority_count
                med_count = p_metrics.medium_priority_count
                low_count = p_metrics.low_priority_count
                avg_priority_score = p_metrics.average_priority_score
                eval_chunks = ranked_chunks
            else:
                eval_chunks = tagged_chunks

            # Workspace simulation
            workspace = EvidenceWorkspace(chunks=eval_chunks, max_active=settings.max_active_chunks)
            if config["priority_enabled"]:
                workspace.promote_priority_initial(fallback_count=1)
            else:
                workspace.promote_initial(count=1)

            expansion_steps = 0
            stop_reason = "unknown"
            sufficiency_log = []

            while True:
                active = workspace.active()
                suff = blended_sufficiency.evaluate(query, active)
                sufficiency_log.append(suff.to_dict())

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

            q_record = {
                "id": qid,
                "query": query,
                "topic": q_item["topic"],
                "active_chunks": workspace.active_count,
                "available_chunks": workspace.available_count,
                "expansion_steps": expansion_steps,
                "stop_reason": stop_reason,
                "final_context_length": len(final_context),
                "total_latency_ms": round(total_latency * 1000, 3),
                "retrieval_latency_ms": round(retrieval_latency * 1000, 3),
                "priority_latency_ms": round(priority_latency * 1000, 3),
                "high_priority_count": high_count,
                "medium_priority_count": med_count,
                "low_priority_count": low_count,
                "avg_priority_score": round(avg_priority_score, 4),
            }
            config_query_results.append(q_record)

            print(
                f"  {qid} [{q_item['topic']}]: "
                f"Active={q_record['active_chunks']} | "
                f"CtxLen={q_record['final_context_length']} chars | "
                f"PriLatency={q_record['priority_latency_ms']} ms | "
                f"Stop={stop_reason}"
            )

        all_results[config_name] = {
            "description": config["description"],
            "queries": config_query_results,
            "aggregate": {
                "avg_context_length": round(
                    sum(r["final_context_length"] for r in config_query_results) / len(config_query_results), 1
                ),
                "avg_active_chunks": round(
                    sum(r["active_chunks"] for r in config_query_results) / len(config_query_results), 2
                ),
                "avg_expansion_steps": round(
                    sum(r["expansion_steps"] for r in config_query_results) / len(config_query_results), 2
                ),
                "avg_priority_latency_ms": round(
                    sum(r["priority_latency_ms"] for r in config_query_results) / len(config_query_results), 3
                ),
                "avg_total_latency_ms": round(
                    sum(r["total_latency_ms"] for r in config_query_results) / len(config_query_results), 3
                ),
                "sufficient_rate": round(
                    sum(1 for r in config_query_results if r["stop_reason"] == "evidence_sufficient")
                    / len(config_query_results),
                    2
                ),
            },
        }

    # Save output
    out_path = Path("experiments/S8_results_v1.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n\nExperiment results successfully written to: {out_path.resolve()}")

    # Print summary table
    print("\n" + "=" * 80)
    print(f"{'Configuration':<26} | {'Avg Ctx Len':<12} | {'Active Chunks':<14} | {'Pri Latency':<12} | {'Sufficiency Rate'}")
    print("-" * 80)
    for c_name, data in all_results.items():
        agg = data["aggregate"]
        print(
            f"{c_name:<26} | {agg['avg_context_length']:<12} | {agg['avg_active_chunks']:<14} | {agg['avg_priority_latency_ms']:>6.3f} ms    | {agg['sufficient_rate']:.0%}"
        )
    print("=" * 80)


if __name__ == "__main__":
    run_experiment()

