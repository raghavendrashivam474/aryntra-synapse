import { useEffect, useState } from "react";
import type {
  BaselineResult,
  SynapseResult,
  ComparisonResult,
} from "../types/experiment";
import {
  loadBaseline,
  loadSynapse,
  loadComparison,
  checkIntegrity,
} from "../data/loader";
import SystemCard from "./SystemCard";
import ResearchFinding from "./ResearchFinding";
import ModalShell from "./ModalShell";

interface Props {
  onEnterWorld: () => void;
}

export default function DecisionView({ onEnterWorld }: Props) {
  const [baseline, setBaseline] = useState<BaselineResult | null>(null);
  const [synapse, setSynapse] = useState<SynapseResult | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [integrityErrors, setIntegrityErrors] = useState<string[]>([]);
  const [showQueryInfo, setShowQueryInfo] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [b, s, c] = await Promise.all([
          loadBaseline(),
          loadSynapse(),
          loadComparison(),
        ]);
        setBaseline(b);
        setSynapse(s);
        setComparison(c);

        const check = checkIntegrity(b, s, c);
        if (!check.valid) setIntegrityErrors(check.errors);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  if (error) {
    return (
      <div className="error-state">
        <h1>Data Load Error</h1>
        <p>{error}</p>
        <p>Ensure the JSON artifacts exist in public/data/.</p>
      </div>
    );
  }

  if (!baseline || !synapse || !comparison) {
    return <div className="loading">Loading experiment data...</div>;
  }

  return (
    <div className="decision-view">
      <header className="header">
        <h1>Aryntra Synapse</h1>
        <p className="subtitle">Synapse Compare v0.1</p>
        <p className="experiment-id">
          Experiment: {baseline.experiment_id} (Recorded Artifact)
        </p>
      </header>

      {integrityErrors.length > 0 && (
        <div className="integrity-warning">
          <strong>Integrity Warning:</strong>
          <ul>
            {integrityErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="query-section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <h2>Query</h2>
          <button
            className="hud-btn"
            style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem", borderColor: "#ab47bc", color: "#ab47bc" }}
            onClick={() => setShowQueryInfo(true)}
          >
            💡 Why recorded query? / Custom Query Info
          </button>
        </div>
        <blockquote>{baseline.query}</blockquote>
        <p className="expected-note">
          Expected current document:{" "}
          <strong>{baseline.evaluation.expected_current_document}</strong>
        </p>
      </section>

      <section className="comparison-grid">
        <SystemCard variant="baseline" data={baseline} />
        <SystemCard variant="synapse" data={synapse} />
      </section>

      <ResearchFinding data={comparison} />

      <div className="world-entry">
        <button className="btn-primary" onClick={onEnterWorld}>
          Explore Evidence World &rarr;
        </button>
      </div>

      {/* Custom Query Info Modal */}
      <ModalShell
        title="Recorded Query vs. Custom Execution"
        isOpen={showQueryInfo}
        onClose={() => setShowQueryInfo(false)}
      >
        <section className="modal-section">
          <h3>Why is the query fixed in SC-S3?</h3>
          <p style={{ fontSize: "0.9rem", color: "#e0e0e0", marginBottom: "0.75rem" }}>
            SC-S3 is a <strong>scientific presentation layer</strong> designed to visualize
            and investigate the pre-recorded results of Experiment <code>SC-S1-TEMPORAL-001</code>.
          </p>
          <p style={{ fontSize: "0.85rem", color: "#8888aa" }}>
            To preserve evidence integrity, the current interface loads direct output from the
            verified SC-S1 (lexical baseline) and SC-S2 (Synapse engine) runs.
          </p>
        </section>

        <section className="modal-section">
          <h3>SC-S4 Proposal: Live Custom Queries</h3>
          <div className="modal-caveat">
            <strong>Approved Direction for Sprint SC-S4 (ADR-001):</strong><br />
            A lightweight FastAPI backend will execute <code>UnifiedEvidenceEngine</code> and
            <code>LexicalBaselineEngine</code> against custom query text in real-time,
            keeping live runs separate from the recorded reference experiment!
          </div>
        </section>
      </ModalShell>
    </div>
  );
}
