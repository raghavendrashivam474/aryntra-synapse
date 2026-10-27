// types/experiment.ts — Contracts derived from actual SC-S1/SC-S2 artifacts.
// Do not add fields that are not present in the source JSON.

export interface RetrievalResult {
  document_id: string;
  rank: number;
  score: number;
}

export interface BaselineResult {
  schema_version: string;
  experiment_id: string;
  system: "baseline";
  query: string;
  corpus: { documents: string[] };
  retrieval: {
    method: string;
    top_k: number;
    results: RetrievalResult[];
  };
  decision: {
    selected_evidence: string[];
    output: string;
  };
  evaluation: {
    expected_current_document: string;
    selected_current_document: boolean;
    status: "PASS" | "FAIL";
  };
}

export interface SynapseResult {
  schema_version: string;
  experiment_id: string;
  system: "synapse";
  query: string;
  corpus: { documents: string[] };
  execution: {
    status: string;
    pipeline_time_ms: number;
  };
  retrieval: {
    method: string;
    selected_evidence: string[];
    rejected_evidence: string[];
  };
  decision: {
    outcome: string;
    selected_evidence: string[];
    confidence: number | null;
    output: string;
  };
  signals: {
    temporal_context: {
      query_intent: string | null;
      target_date: string | null;
    };
    conflict_detected: boolean;
    conflict_score: number;
    adjudication_triggered: boolean;
    adjudication_decision: string | null;
    safety_veto: boolean;
    sufficiency_score: number;
    relationships: {
      node_count: number;
      edge_count: number;
    };
  };
  evaluation: {
    expected_current_document: string;
    selected_current_document: boolean;
    status: "PASS" | "FAIL";
  };
}

export interface ComparisonResult {
  experiment_id: string;
  query: string;
  input_integrity: string;
  baseline: {
    system: string;
    execution_status: string;
    selected_evidence: string[];
    decision_output: string;
    confidence: number | null;
    evaluation_status: string;
  };
  synapse: {
    system: string;
    execution_status: string;
    selected_evidence: string[];
    decision_output: string;
    confidence: number | null;
    evaluation_status: string;
    temporal_intent: string | null;
    conflict_score: number | null;
    sufficiency_score: number | null;
  };
  evidence_selection_match: boolean;
  both_selected_current: boolean;
  baseline_selected_current: boolean;
  synapse_selected_current: boolean;
  decision_comparison: string;
  notes: string[];
}

export interface PolicyFixture {
  document_id: string;
  version: string;
  publication_date: string;
  status: string;
  content: string;
  supersedes: string | null;
}

export interface IntegrityCheck {
  valid: boolean;
  errors: string[];
}
