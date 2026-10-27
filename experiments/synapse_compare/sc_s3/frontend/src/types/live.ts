// types/live.ts — Contracts for the SC-S4 live comparison API.
// Derived from the ADR-001 response schema and actual server output.

import type { BaselineResult, SynapseResult, ComparisonResult } from "./experiment";

export interface LiveCompareRequest {
  query: string;
  top_k?: number;
}

export interface LiveCompareResponse {
  run_id: string;
  mode: "live";
  query: string;
  corpus: {
    id: string;
    version: string;
    documents: string[];
  };
  baseline: {
    execution_status: "success" | "error";
    result: BaselineResult | null;
    error: string | null;
  };
  synapse: {
    execution_status: "success" | "error";
    result: SynapseResult | null;
    error: string | null;
  };
  comparison: {
    status: "completed" | "partial" | "not_available" | "error";
    result: ComparisonResult | Record<string, never>;
  };
  evaluation: {
    status: "not_applicable" | "evaluated";
    reason: string | null;
    ground_truth_id: string | null;
    metrics: Record<string, unknown> | null;
  };
  metadata: {
    baseline_engine: string;
    synapse_engine: string;
    corpus_documents: string[];
    execution_time_ms: number;
  };
}
