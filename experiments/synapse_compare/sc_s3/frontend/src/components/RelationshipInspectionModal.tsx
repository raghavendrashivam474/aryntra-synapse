import ModalShell from "./ModalShell";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  sourceEntity: string;
  targetEntity: string;
  relType: string;
  provenance: string;
  onNavigateToEntity: (id: string) => void;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="modal-row">
      <span className="modal-label">{label}</span>
      <span className="modal-value">{value ?? "Not available"}</span>
    </div>
  );
}

export default function RelationshipInspectionModal({
  isOpen, onClose, sourceEntity, targetEntity, relType, provenance,
  onNavigateToEntity,
}: Props) {
  return (
    <ModalShell title={`Relationship: ${relType}`} isOpen={isOpen} onClose={onClose}>
      <section className="modal-section">
        <h3>Relationship Details</h3>
        <Row label="Type" value={<strong>{relType}</strong>} />
        <Row label="Direction" value="Source → Target" />
        <Row
          label="Source"
          value={
            <button
              className="modal-entity-link"
              onClick={() => onNavigateToEntity(sourceEntity)}
            >
              {sourceEntity}
            </button>
          }
        />
        <Row
          label="Target"
          value={
            <button
              className="modal-entity-link"
              onClick={() => onNavigateToEntity(targetEntity)}
            >
              {targetEntity}
            </button>
          }
        />
      </section>

      <section className="modal-section">
        <h3>Provenance</h3>
        <Row label="Source" value={provenance} />
        <div className="modal-caveat">
          This relationship comes from the canonical fixture metadata
          (policy_v2.json &quot;supersedes&quot; field). It is not a relationship
          independently detected by the Synapse engine, though Synapse did report
          building a graph with 1 edge.
        </div>
      </section>

      <section className="modal-section">
        <h3>Interpretation</h3>
        <div className="modal-caveat">
          The existence of this supersession relationship does not mean either
          system correctly used it to select the current policy. Both systems
          selected AUTH-POLICY-V1 (the superseded document) and both failed the
          temporal-correctness evaluation.
        </div>
      </section>
    </ModalShell>
  );
}
