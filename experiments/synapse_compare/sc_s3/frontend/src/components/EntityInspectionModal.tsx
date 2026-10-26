import type {
  PolicyFixture,
  BaselineResult,
  SynapseResult,
} from "../types/experiment";
import ModalShell from "./ModalShell";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  fixture: PolicyFixture | undefined;
  baseline: BaselineResult | null;
  synapse: SynapseResult | null;
  onNavigateToEntity: (id: string) => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="modal-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="modal-row">
      <span className="modal-label">{label}</span>
      <span className="modal-value">{value ?? "Not available"}</span>
    </div>
  );
}

export default function EntityInspectionModal({
  isOpen, onClose, documentId, fixture, baseline, synapse, onNavigateToEntity,
}: Props) {
  // Baseline observations
  const bSelected = baseline?.decision.selected_evidence.includes(documentId) ?? false;
  const bScore = baseline?.retrieval.results.find((r) => r.document_id === documentId);

  // Synapse observations
  const sSelected = synapse?.retrieval.selected_evidence.includes(documentId) ?? false;
  const sRejected = synapse?.retrieval.rejected_evidence.includes(documentId) ?? false;

  // Connected entity (from fixture supersession)
  const connectedId = fixture?.supersedes ?? null;

  return (
    <ModalShell title={`Entity: ${documentId}`} isOpen={isOpen} onClose={onClose}>
      {/* A. Identity */}
      <Section title="Identity">
        <Row label="Document ID" value={documentId} />
        <Row label="Entity Type" value="Policy Document" />
        <Row label="Scenario" value="SC-S1-TEMPORAL-001" />
      </Section>

      {/* B. Source Evidence */}
      <Section title="Source Evidence">
        {fixture ? (
          <div className="modal-evidence-block">
            <pre className="modal-source-text">{fixture.content}</pre>
            <span className="modal-provenance-note">
              Original text from fixture: {documentId.toLowerCase().replace(/-/g, "_")}.json
            </span>
          </div>
        ) : (
          <p className="modal-unavailable">Source text not available.</p>
        )}
      </Section>

      {/* C. Metadata */}
      <Section title="Metadata">
        {fixture ? (
          <>
            <Row label="Version" value={fixture.version} />
            <Row label="Publication Date" value={fixture.publication_date} />
            <Row
              label="Status"
              value={
                <span className={`status-tag status-${fixture.status}`}>
                  {fixture.status.toUpperCase()}
                </span>
              }
            />
            <Row label="Supersedes" value={fixture.supersedes ?? "None"} />
          </>
        ) : (
          <p className="modal-unavailable">Metadata not available.</p>
        )}
      </Section>

      {/* D. Relationships */}
      <Section title="Relationships">
        {connectedId ? (
          <div className="modal-rel-item">
            <span className="modal-rel-arrow">
              {documentId} → <strong>SUPERSEDES</strong> →{" "}
              <button
                className="modal-entity-link"
                onClick={() => onNavigateToEntity(connectedId)}
              >
                {connectedId}
              </button>
            </span>
            <span className="modal-provenance-note">
              Source: Fixture metadata (not engine-detected)
            </span>
          </div>
        ) : (
          <p className="modal-unavailable">
            No recorded relationships for this entity.
          </p>
        )}
        {synapse && (
          <div className="modal-rel-note">
            Synapse reported {synapse.signals.relationships.edge_count} edge(s)
            in its relationship graph for this experiment. The specific edge
            details are at the experiment level, not per-entity.
          </div>
        )}
      </Section>

      {/* E. Baseline Observation */}
      <Section title="Baseline Observation">
        <Row
          label="Selected"
          value={
            <span className={bSelected ? "status-selected" : "status-not-selected"}>
              {bSelected ? "Yes" : "No"}
            </span>
          }
        />
        {bScore && (
          <>
            <Row label="Retrieval Rank" value={bScore.rank} />
            <Row label="Retrieval Score" value={bScore.score} />
          </>
        )}
        {bSelected && baseline && (
          <Row label="Decision Output" value={baseline.decision.output} />
        )}
        <Row label="Evaluation" value={baseline?.evaluation.status ?? "Not available"} />
      </Section>

      {/* F. Synapse Observation */}
      <Section title="Synapse Observation">
        <Row
          label="Selected"
          value={
            <span className={sSelected ? "status-selected" : "status-not-selected"}>
              {sSelected ? "Yes" : "No"}
            </span>
          }
        />
        <Row
          label="Rejected"
          value={
            <span className={sRejected ? "status-rejected" : ""}>
              {sRejected ? "Yes" : "No"}
            </span>
          }
        />
        {synapse && (
          <>
            <Row label="Decision" value={synapse.decision.outcome} />
            <Row label="Confidence" value={synapse.decision.confidence} />
            <Row
              label="Temporal Intent"
              value={synapse.signals.temporal_context.query_intent ?? "Not detected"}
            />
            <Row label="Sufficiency" value={synapse.signals.sufficiency_score} />
          </>
        )}
        <Row label="Evaluation" value={synapse?.evaluation.status ?? "Not available"} />
        {sSelected && synapse && (
          <div className="modal-caveat">
            Note: Synapse selected this document despite detecting temporal intent
            &quot;{synapse.signals.temporal_context.query_intent}&quot; and a sufficiency
            score of {synapse.signals.sufficiency_score}. This is the central
            research finding of SC-S2.
          </div>
        )}
      </Section>

      {/* G. Provenance */}
      <Section title="Provenance">
        <Row label="Fixture Source" value={`${documentId.toLowerCase().replace(/-/g, "_")}.json`} />
        <Row label="Baseline Result" value="sc_s1_result.json" />
        <Row label="Synapse Result" value="sc_s2_result.json" />
        <Row label="Comparison" value="sc_s2_comparison.json" />
      </Section>
    </ModalShell>
  );
}
