"""
Aryntra Synapse - Sprint 13: Master Generalization and Failure Mapping Matrix (Optimized)

Executes systematic multi-dimensional evaluation with cached vector embeddings:
- Corpus scaling (5, 25, 50, 100, 150, 250 chunks)
- Distractor taxonomy (D1-D6) and distractor densities (Low, Moderate, High, Dense)
- Query complexity classes (Q1-Q7)
- Evidence distributions (Concentrated, Distributed, Redundant, Sparse, Fragmented)
- Signal ablations and Calibrated priority weights
- Adaptive routing analysis and ConfidenceGuard recovery metrics
- Failure severity classification (F0-F4) and Recovery Rate
"""

import os
import sys
import json
import time
import random
import logging
from typing import List, Dict, Any, Tuple, Set, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.context.evidence_priority import EvidencePriorityEngine, EvidencePriorityWeights, PriorityClass
from app.context.calibration import EvidenceSurvivalTracker, PriorityCalibrationConfig
from app.strategy.fallback import ConfidenceGuard, FallbackDecision
from app.strategy.selector import AdaptiveSelector, StrategyDecision
from app.retrieval.embeddings import EmbeddingModel
from app.optimization.embedding_cache import EmbeddingCache

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "s13"))


def load_distractor_pool() -> Dict[str, List[str]]:
    filepath = os.path.join(DATA_DIR, "distractor_corpus.json")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_query_suite() -> List[Dict[str, Any]]:
    filepath = os.path.join(DATA_DIR, "query_suite.json")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


class FailureSeverity:
    F0_NO_FAILURE = "F0_none"
    F1_SELECTION_DEGRADATION = "F1_selection_degraded"
    F2_DEPRIORITIZED_RECOVERABLE = "F2_deprioritized_recoverable"
    F3_EVIDENCE_PRUNED = "F3_evidence_pruned"
    F4_DANGEROUS_UNSUPPORTED = "F4_dangerous_unsupported"


def classify_failure(
    top1_bearing: bool,
    top_k_recall: float,
    survival_rate: float,
    guard_triggered: bool,
    is_contradictory_top: bool = False
) -> str:
    if is_contradictory_top:
        return FailureSeverity.F4_DANGEROUS_UNSUPPORTED
    if top1_bearing and top_k_recall >= 0.99:
        return FailureSeverity.F0_NO_FAILURE
    if top_k_recall >= 0.66 and survival_rate >= 0.5:
        return FailureSeverity.F1_SELECTION_DEGRADATION
    if survival_rate > 0.0 or guard_triggered:
        return FailureSeverity.F2_DEPRIORITIZED_RECOVERABLE
    return FailureSeverity.F3_EVIDENCE_PRUNED


def generate_controlled_corpus(
    query_item: Dict[str, Any],
    distractor_pool: Dict[str, List[str]],
    target_size: int,
    distractor_type: str = "D1_random",
    seed: int = 42,
    reused_ratio: float = 0.2
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    rng = random.Random(seed)
    chunks = []
    answer_ids = set()

    expected_answers = query_item.get("expected_answers", [])
    for i, ans_text in enumerate(expected_answers):
        cid = f"ab_{query_item['id']}_{i}"
        is_reused = (rng.random() < reused_ratio)
        chunks.append({
            "chunk_id": cid,
            "text": ans_text,
            "source": "ground_truth",
            "category": "answer_bearing",
            "reused": is_reused,
            "score": 0.95
        })
        answer_ids.add(cid)

    remaining = max(0, target_size - len(chunks))
    pool = distractor_pool.get(distractor_type, distractor_pool["D1_random"])

    for i in range(remaining):
        base_text = pool[i % len(pool)]
        cid = f"dist_{distractor_type}_{i}"
        suffix = f" [ref {i+1}]" if i >= len(pool) else ""
        is_reused = (rng.random() < reused_ratio)
        chunks.append({
            "chunk_id": cid,
            "text": base_text + suffix,
            "source": distractor_type,
            "category": "distractor",
            "reused": is_reused,
            "score": 0.60
        })

    rng.shuffle(chunks)
    return chunks, answer_ids


class GeneralizationHarness:
    def __init__(self):
        self.embedder = EmbeddingModel()
        self.cache = EmbeddingCache(max_entries=16384)
        self.tracker = EvidenceSurvivalTracker()
        self.guard = ConfidenceGuard()
        self.selector = AdaptiveSelector()
        self.distractor_pool = load_distractor_pool()
        self.query_suite = load_query_suite()

        self.configurations = {
            "calibrated_blend": EvidencePriorityWeights(semantic_weight=0.50, lexical_weight=0.35, reuse_weight=0.15),
            "semantic_only": EvidencePriorityWeights.semantic_only(),
            "lexical_only": EvidencePriorityWeights.lexical_only(),
            "semantic_lexical": EvidencePriorityWeights.semantic_lexical(),
            "semantic_reuse": EvidencePriorityWeights(semantic_weight=0.70, lexical_weight=0.0, reuse_weight=0.30),
            "lexical_reuse": EvidencePriorityWeights(semantic_weight=0.0, lexical_weight=0.70, reuse_weight=0.30),
        }

    def run_full_matrix(
        self,
        corpus_sizes: List[int] = [5, 25, 50, 100, 150, 250],
        distractor_types: List[str] = ["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"],
        config_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if config_names is None:
            config_names = list(self.configurations.keys())

        results = {
            "metadata": {
                "sprint": "S13",
                "target_version": "v1.5.0",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "corpus_sizes": corpus_sizes,
                "distractor_types": distractor_types,
                "configurations": config_names,
                "query_count": len(self.query_suite)
            },
            "evaluations": [],
            "summary_by_corpus": {},
            "summary_by_distractor": {},
            "summary_by_query_type": {},
            "summary_by_config": {},
            "failure_severity_distribution": {},
            "recovery_metrics": {
                "total_failures": 0,
                "guard_triggers": 0,
                "recoverable_failures": 0,
                "recovered_failures": 0,
                "recovery_rate": 0.0
            }
        }

        total_trials = len(corpus_sizes) * len(distractor_types) * len(self.query_suite) * len(config_names)
        completed = 0
        t_start_all = time.perf_counter()

        for c_size in corpus_sizes:
            for d_type in distractor_types:
                for q_item in self.query_suite:
                    chunks, answer_ids = generate_controlled_corpus(
                        query_item=q_item,
                        distractor_pool=self.distractor_pool,
                        target_size=c_size,
                        distractor_type=d_type,
                        seed=42 + c_size
                    )

                    q_text = q_item["query"]

                    for cfg_name in config_names:
                        weights = self.configurations[cfg_name]
                        engine = EvidencePriorityEngine(
                            embedding_model=self.embedder,
                            weights=weights,
                            query_cache=self.cache,
                            evidence_cache=self.cache
                        )

                        qid = f"{q_item['id']}_c{c_size}_{d_type}_{cfg_name}"
                        self.tracker.reset()
                        self.tracker.mark_retrieved(qid, chunks, answer_ids)

                        t0 = time.perf_counter()
                        ranked, metrics = engine.rank(q_text, chunks)
                        latency = time.perf_counter() - t0

                        # Routing & Guard
                        strategy_dec = self.selector.select(q_text, ranked)
                        guard_assess = self.guard.assess(q_text, ranked, metrics.to_dict())
                        guard_triggered = (guard_assess.decision != FallbackDecision.TRUST_PRIORITY)

                        self.tracker.mark_prefilter(qid, {c.get("chunk_id", "") for c in ranked})
                        self.tracker.mark_priority(qid, ranked)
                        final_ids = {c.get("chunk_id", "") for c in ranked if c.get("state") == "active"}
                        self.tracker.mark_final_context(qid, final_ids)

                        survival_rates = self.tracker.get_survival_rates(qid)

                        top1_id = ranked[0].get("chunk_id", "") if ranked else ""
                        top1_bearing = top1_id in answer_ids
                        top_k = min(len(answer_ids) + 2, len(ranked))
                        top_k_bearing = sum(1 for c in ranked[:top_k] if c.get("chunk_id", "") in answer_ids)
                        top_k_recall = top_k_bearing / max(1, len(answer_ids))

                        is_contradictory_top = False
                        if d_type == "D6_contradictory" and top1_id.startswith("dist_D6"):
                            is_contradictory_top = True

                        severity = classify_failure(
                            top1_bearing=top1_bearing,
                            top_k_recall=top_k_recall,
                            survival_rate=survival_rates.get("final_rate", 0.0),
                            guard_triggered=guard_triggered,
                            is_contradictory_top=is_contradictory_top
                        )

                        recovered = False
                        if not top1_bearing and (guard_triggered or strategy_dec.path.value == "deep"):
                            if top_k_bearing > 0:
                                recovered = True

                        eval_record = {
                            "query_id": q_item["id"],
                            "query_type": q_item["type"],
                            "evidence_distribution": q_item["distribution"],
                            "corpus_size": c_size,
                            "distractor_type": d_type,
                            "config_name": cfg_name,
                            "latency_ms": round(latency * 1000, 3),
                            "top1_is_answer_bearing": top1_bearing,
                            "top_k_recall": round(top_k_recall, 4),
                            "survival_rate": round(survival_rates.get("final_rate", 0.0), 4),
                            "route_selected": strategy_dec.path.value,
                            "guard_decision": guard_assess.decision.value,
                            "guard_confidence": round(guard_assess.confidence_score, 4),
                            "guard_triggered": guard_triggered,
                            "failure_severity": severity,
                            "recovered": recovered,
                            "high_count": metrics.high_priority_count,
                            "avg_score": round(metrics.average_priority_score, 4)
                        }

                        results["evaluations"].append(eval_record)
                        completed += 1

                    if completed % 126 == 0 or completed == total_trials:
                        pct = (completed / total_trials) * 100
                        print(f"  Progress: {completed}/{total_trials} evaluations ({pct:.1f}%) complete...")

        total_duration = time.perf_counter() - t_start_all
        results["metadata"]["total_duration_s"] = round(total_duration, 2)

        self._compute_aggregates(results)
        return results

    def _compute_aggregates(self, results: Dict[str, Any]) -> None:
        evals = results["evaluations"]
        n_total = len(evals)
        if n_total == 0:
            return

        sev_counts = {}
        for ev in evals:
            s = ev["failure_severity"]
            sev_counts[s] = sev_counts.get(s, 0) + 1
        results["failure_severity_distribution"] = {k: {"count": v, "ratio": round(v / n_total, 4)} for k, v in sev_counts.items()}

        failures = [ev for ev in evals if not ev["top1_is_answer_bearing"]]
        recoverable = [ev for ev in failures if ev["top_k_recall"] > 0]
        recovered = [ev for ev in recoverable if ev["recovered"]]
        triggers = [ev for ev in evals if ev["guard_triggered"]]

        rec_rate = (len(recovered) / len(recoverable)) if recoverable else 1.0
        results["recovery_metrics"] = {
            "total_evaluations": n_total,
            "total_failures": len(failures),
            "guard_triggers": len(triggers),
            "recoverable_failures": len(recoverable),
            "recovered_failures": len(recovered),
            "recovery_rate": round(rec_rate, 4)
        }

        # By Corpus Size
        c_groups = {}
        for ev in evals:
            c = ev["corpus_size"]
            c_groups.setdefault(c, []).append(ev)
        for c, records in sorted(c_groups.items()):
            n = len(records)
            results["summary_by_corpus"][f"C{c}"] = {
                "corpus_size": c,
                "count": n,
                "top1_accuracy": round(sum(1 for r in records if r["top1_is_answer_bearing"]) / n, 4),
                "avg_recall": round(sum(r["top_k_recall"] for r in records) / n, 4),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in records) / n, 2),
                "guard_trigger_rate": round(sum(1 for r in records if r["guard_triggered"]) / n, 4),
                "f0_no_failure_rate": round(sum(1 for r in records if r["failure_severity"] == FailureSeverity.F0_NO_FAILURE) / n, 4),
                "f3_pruned_rate": round(sum(1 for r in records if r["failure_severity"] == FailureSeverity.F3_EVIDENCE_PRUNED) / n, 4),
                "f4_dangerous_rate": round(sum(1 for r in records if r["failure_severity"] == FailureSeverity.F4_DANGEROUS_UNSUPPORTED) / n, 4)
            }

        # By Distractor Type
        d_groups = {}
        for ev in evals:
            d = ev["distractor_type"]
            d_groups.setdefault(d, []).append(ev)
        for d, records in sorted(d_groups.items()):
            n = len(records)
            results["summary_by_distractor"][d] = {
                "count": n,
                "top1_accuracy": round(sum(1 for r in records if r["top1_is_answer_bearing"]) / n, 4),
                "avg_recall": round(sum(r["top_k_recall"] for r in records) / n, 4),
                "guard_trigger_rate": round(sum(1 for r in records if r["guard_triggered"]) / n, 4),
                "f4_dangerous_count": sum(1 for r in records if r["failure_severity"] == FailureSeverity.F4_DANGEROUS_UNSUPPORTED)
            }

        # By Query Complexity
        q_groups = {}
        for ev in evals:
            q = ev["query_type"]
            q_groups.setdefault(q, []).append(ev)
        for q, records in sorted(q_groups.items()):
            n = len(records)
            results["summary_by_query_type"][q] = {
                "count": n,
                "top1_accuracy": round(sum(1 for r in records if r["top1_is_answer_bearing"]) / n, 4),
                "avg_recall": round(sum(r["top_k_recall"] for r in records) / n, 4),
                "avg_survival_rate": round(sum(r["survival_rate"] for r in records) / n, 4)
            }

        # By Configuration
        cfg_groups = {}
        for ev in evals:
            cfg = ev["config_name"]
            cfg_groups.setdefault(cfg, []).append(ev)
        for cfg, records in sorted(cfg_groups.items()):
            n = len(records)
            results["summary_by_config"][cfg] = {
                "count": n,
                "top1_accuracy": round(sum(1 for r in records if r["top1_is_answer_bearing"]) / n, 4),
                "avg_recall": round(sum(r["top_k_recall"] for r in records) / n, 4),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in records) / n, 2)
            }


def run_s13_generalization_experiment():
    print("=" * 80)
    print("  ARYNTRA SYNAPSE - SPRINT 13 GENERALIZATION & FAILURE MATRIX")
    print("=" * 80)

    harness = GeneralizationHarness()
    results = harness.run_full_matrix(
        corpus_sizes=[5, 25, 50, 100, 150, 250],
        distractor_types=["D1_random", "D2_topic", "D3_lexical", "D4_semantic", "D5_partial", "D6_contradictory"],
        config_names=["calibrated_blend", "semantic_only", "lexical_only", "semantic_lexical", "semantic_reuse", "lexical_reuse"]
    )

    out_file = os.path.join(os.path.dirname(__file__), "S13_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nCompleted {len(results['evaluations'])} systematic evaluations in {results['metadata']['total_duration_s']}s")
    print(f"Results saved to: {out_file}")

    print("\n--- Corpus Scaling Performance ---")
    for c_key, data in results["summary_by_corpus"].items():
        print(f"  {c_key:<6}: Top-1={data['top1_accuracy']*100:5.1f}% | Recall={data['avg_recall']*100:5.1f}% | Lat={data['avg_latency_ms']:6.2f}ms | GuardTrigger={data['guard_trigger_rate']*100:4.1f}%")

    print("\n--- Distractor Taxonomy Vulnerability ---")
    for d_key, data in results["summary_by_distractor"].items():
        print(f"  {d_key:<18}: Top-1={data['top1_accuracy']*100:5.1f}% | Recall={data['avg_recall']*100:5.1f}% | GuardTrigger={data['guard_trigger_rate']*100:4.1f}% | F4={data['f4_dangerous_count']}")

    print("\n--- Configuration Ranking ---")
    for cfg_key, data in sorted(results["summary_by_config"].items(), key=lambda x: x[1]["top1_accuracy"], reverse=True):
        print(f"  {cfg_key:<20}: Top-1={data['top1_accuracy']*100:5.1f}% | Recall={data['avg_recall']*100:5.1f}% | Lat={data['avg_latency_ms']:6.2f}ms")

    print("\n--- Recovery Metrics ---")
    rec = results["recovery_metrics"]
    print(f"  Total Failures: {rec['total_failures']} | Recoverable: {rec['recoverable_failures']} | Recovered: {rec['recovered_failures']} | Recovery Rate: {rec['recovery_rate']*100:.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    run_s13_generalization_experiment()
