import { useEffect, useState, useMemo, useCallback } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { PolicyFixture, BaselineResult, SynapseResult } from "../types/experiment";
import { loadBaseline, loadSynapse, loadFixtures } from "../data/loader";
import EntityNode, { type EntityVisualState } from "./EntityNode";
import RelationshipEdge from "./RelationshipEdge";
import WorldHUD from "./WorldHUD";
import EntityInspectionModal from "./EntityInspectionModal";
import RelationshipInspectionModal from "./RelationshipInspectionModal";

type Perspective = "baseline" | "synapse" | "compare";

interface Props {
  onBack: () => void;
}

const POSITIONS: Record<string, [number, number, number]> = {
  "AUTH-POLICY-V1": [-2.5, 0, 0],
  "AUTH-POLICY-V2": [2.5, 0, 0],
};

export default function EvidenceWorld({ onBack }: Props) {
  const [fixtures, setFixtures] = useState<PolicyFixture[]>([]);
  const [baseline, setBaseline] = useState<BaselineResult | null>(null);
  const [synapse, setSynapse] = useState<SynapseResult | null>(null);
  const [perspective, setPerspective] = useState<Perspective>("synapse");
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [selectedRel, setSelectedRel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Modal state — separate from selection so world state is preserved
  const [entityModalId, setEntityModalId] = useState<string | null>(null);
  const [relModalOpen, setRelModalOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [f, b, s] = await Promise.all([
          loadFixtures(), loadBaseline(), loadSynapse(),
        ]);
        setFixtures(f);
        setBaseline(b);
        setSynapse(s);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  const entityStates = useMemo(() => {
    const states: Record<string, EntityVisualState> = {};
    for (const f of fixtures) {
      const bSel = baseline?.decision.selected_evidence.includes(f.document_id) ?? false;
      const sSel = synapse?.retrieval.selected_evidence.includes(f.document_id) ?? false;
      const sRej = synapse?.retrieval.rejected_evidence.includes(f.document_id) ?? false;

      let selected = false;
      let rejected = false;

      if (perspective === "baseline") {
        selected = bSel;
      } else if (perspective === "synapse") {
        selected = sSel;
        rejected = sRej;
      } else {
        selected = bSel || sSel;
        rejected = sRej && !bSel;
      }

      states[f.document_id] = {
        status: f.status as "current" | "superseded",
        selected,
        rejected,
        perspective,
      };
    }
    return states;
  }, [fixtures, baseline, synapse, perspective]);

  const supersedingDoc = fixtures.find((f) => f.supersedes);
  const relId = supersedingDoc
    ? `${supersedingDoc.document_id}-SUPERSEDES-${supersedingDoc.supersedes}`
    : null;

  const handleMiss = () => {
    setSelectedEntity(null);
    setSelectedRel(null);
  };

  const openEntityModal = useCallback((id: string) => {
    setSelectedEntity(id);
    setSelectedRel(null);
    setEntityModalId(id);
  }, []);

  const closeEntityModal = useCallback(() => {
    setEntityModalId(null);
  }, []);

  const openRelModal = useCallback(() => {
    if (relId) {
      setSelectedRel(relId);
      setSelectedEntity(null);
      setRelModalOpen(true);
    }
  }, [relId]);

  const closeRelModal = useCallback(() => {
    setRelModalOpen(false);
  }, []);

  const navigateToEntity = useCallback((id: string) => {
    setRelModalOpen(false);
    setEntityModalId(id);
    setSelectedEntity(id);
    setSelectedRel(null);
  }, []);

  if (error) {
    return (
      <div className="error-state">
        <h1>World Load Error</h1>
        <p>{error}</p>
        <button onClick={onBack}>← Back</button>
      </div>
    );
  }

  if (!baseline || !synapse || fixtures.length === 0) {
    return <div className="loading">Loading Evidence World...</div>;
  }

  const activeFixture = entityModalId
    ? fixtures.find((f) => f.document_id === entityModalId)
    : undefined;

  return (
    <div className="evidence-world">
      <Canvas
        camera={{ position: [0, 3, 7], fov: 50 }}
        onPointerMissed={handleMiss}
      >
        <color attach="background" args={["#0d0d1a"]} />
        <fog attach="fog" args={["#0d0d1a", 12, 25]} />
        <ambientLight intensity={0.35} />
        <pointLight position={[5, 5, 5]} intensity={0.7} />
        <pointLight position={[-5, 3, -5]} intensity={0.25} />

        <gridHelper args={[20, 20, "#1a1a3e", "#111128"]} position={[0, -1.5, 0]} />

        {fixtures.map((f) => (
          <EntityNode
            key={f.document_id}
            id={f.document_id}
            position={POSITIONS[f.document_id] ?? [0, 0, 0]}
            visualState={
              entityStates[f.document_id] ?? {
                status: "superseded",
                selected: false,
                rejected: false,
                perspective,
              }
            }
            onClick={() => openEntityModal(f.document_id)}
          />
        ))}

        {supersedingDoc && supersedingDoc.supersedes && (
          <RelationshipEdge
            id={relId!}
            from={POSITIONS[supersedingDoc.document_id] ?? [2.5, 0, 0]}
            to={POSITIONS[supersedingDoc.supersedes] ?? [-2.5, 0, 0]}
            label="SUPERSEDES"
            provenance="Source: Fixture metadata (policy_v2.supersedes)"
            isSelected={selectedRel === relId}
            onClick={openRelModal}
          />
        )}

        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          minDistance={3}
          maxDistance={15}
          maxPolarAngle={Math.PI / 1.8}
        />
      </Canvas>

      <WorldHUD
        query={baseline.query}
        perspective={perspective}
        onPerspectiveChange={setPerspective}
        onBack={onBack}
        selectedEntity={selectedEntity}
        selectedRelationship={selectedRel}
      />

      {/* Entity Inspection Modal */}
      <EntityInspectionModal
        isOpen={entityModalId !== null}
        onClose={closeEntityModal}
        documentId={entityModalId ?? ""}
        fixture={activeFixture}
        baseline={baseline}
        synapse={synapse}
        onNavigateToEntity={navigateToEntity}
      />

      {/* Relationship Inspection Modal */}
      {supersedingDoc && supersedingDoc.supersedes && (
        <RelationshipInspectionModal
          isOpen={relModalOpen}
          onClose={closeRelModal}
          sourceEntity={supersedingDoc.document_id}
          targetEntity={supersedingDoc.supersedes}
          relType="SUPERSEDES"
          provenance="Fixture metadata (policy_v2.json supersedes field)"
          onNavigateToEntity={navigateToEntity}
        />
      )}
    </div>
  );
}
