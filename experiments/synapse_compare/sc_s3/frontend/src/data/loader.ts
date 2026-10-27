// data/loader.ts - Fetches and validates experiment artifacts.

import type {
  BaselineResult,
  SynapseResult,
  ComparisonResult,
  PolicyFixture,
  IntegrityCheck,
} from "../types/experiment";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error("Failed to load " + path + ": " + res.status);
  return res.json() as Promise<T>;
}

export async function loadBaseline(): Promise<BaselineResult> {
  return fetchJSON<BaselineResult>("/data/sc_s1_result.json");
}

export async function loadSynapse(): Promise<SynapseResult> {
  return fetchJSON<SynapseResult>("/data/sc_s2_result.json");
}

export async function loadComparison(): Promise<ComparisonResult> {
  return fetchJSON<ComparisonResult>("/data/sc_s2_comparison.json");
}

export async function loadFixtures(): Promise<PolicyFixture[]> {
  try {
    const res = await fetch("/data/fixtures.json");
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback to legacy
  }
  const [v1, v2] = await Promise.all([
    fetchJSON<PolicyFixture>("/data/policy_v1.json"),
    fetchJSON<PolicyFixture>("/data/policy_v2.json"),
  ]);
  return [v1, v2];
}

export function checkIntegrity(
  baseline: BaselineResult,
  synapse: SynapseResult,
  comparison: ComparisonResult
): IntegrityCheck {
  const errors: string[] = [];

  if (baseline.experiment_id !== synapse.experiment_id) {
    errors.push(
      "Experiment ID mismatch: baseline=" + baseline.experiment_id + ", synapse=" + synapse.experiment_id
    );
  }
  if (baseline.experiment_id !== comparison.experiment_id) {
    errors.push(
      "Experiment ID mismatch: baseline=" + baseline.experiment_id + ", comparison=" + comparison.experiment_id
    );
  }
  if (baseline.query !== synapse.query) {
    errors.push("Query mismatch between baseline and synapse results.");
  }
  if (comparison.input_integrity !== "MATCH") {
    errors.push(
      "Comparison input integrity: " + comparison.input_integrity
    );
  }

  return { valid: errors.length === 0, errors };
}
