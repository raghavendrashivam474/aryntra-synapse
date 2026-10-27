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
  customBaseline?: BaselineResult | null;
  customSynapse?: SynapseResult | null;
  customFixtures?: PolicyFixture[];
  customQuery?: string;
}

export default function EvidenceWorld({
  onBack,
  customBaseline,
  customSynapse,
  customFixtures,
  customQuery,
}: Props) {
  const [fixtures, setFixtures] = useState<PolicyFixture[]>(customFixtures ?? []);
  const [baseline, setBaseline] = useState<BaselineResult | null>(customBaseline ?? null);
  const [synapse, setSynapse] = useState<SynapseResult | null>(customSynapse ?? null);
  const [perspective, setPerspective] = useState<Perspective>("synapse");
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [selectedRel, setSelectedRel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [entityModalId, setEntityModalId] = useState<string | null>(null);
  const [relModalOpen, setRelModalOpen] = useState(false);

  useEffect(() => {
    if (customFixtures && customFixtures.length > 0) return;
    (async () => {
      try {
        const [f, b, s] = await Promise.all([
          loadFixtures(), loadBaseline(), loadSynapse(),
        ]);
        setFixtures(f);
        setBaseline(customBaseline ?? b);
        setSynapse(customSynapse ?? s);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [customFixtures, customBaseline, customSynapse]);

  // Dynamic positions in a circle for N nodes
  const positions = useMemo(() => {
    const map: Record<string, [number, number, number]> = {};
    const count = fixtures.length;
    if (count === 0) return map;
    const radius = count > 2 ? 4.5 : 2.5;
    fixtures.forEach((f, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      map[f.document_id] = [
        Math.cos(angle) * radius,
        0,
        Math.sin(angle) * radius,
      ];
    });
    return map;
  }, [fixtures]);

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
        status: (f.status === "active" || f.status === "current") ? "current" : "superseded",
        selected,
        rejected,
        perspective,
      };
    }
    return states;
  }, [fixtures, baseline, synapse, perspective]);

  const edges = useMemo(() => {
    return fixtures
      .filter((f) => f.supersedes)
      .map((f) => ({
        id: `${f.document_id}-SUPERSEDES-${f.supersedes}`,
        source: f.document_id,
        target: f.supersedes!,
      }));
  }, [fixtures]);

  const activeEdge = edges.find((e) => e.id === selectedRel);

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

  const openRelModal = useCallback((id: string) => {
    setSelectedRel(id);
    setSelectedEntity(null);
    setRelModalOpen(true);
  }, []);

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

  if (fixtures.length === 0) {
    return <div className="loading">Loading Evidence World...</div>;
  }

  const activeFixture = entityModalId
    ? fixtures.find((f) => f.document_id === entityModalId)
    : undefined;

  return (
    <div className="evidence-world">
      <Canvas
        camera={{ position: [0, 5, 10], fov: 50 }}
        onPointerMissed={handleMiss}
      >
        <color attach="background" args={["#0d0d1a"]} />
        <fog attach="fog" args={["#0d0d1a", 15, 30]} />
        <ambientLight intensity={0.4} />
        <pointLight position={[5, 8, 5]} intensity={0.8} />
        <pointLight position={[-5, 3, -5]} intensity={0.3} />

        <gridHelper args={[24, 24, "#1a1a3e", "#111128"]} position={[0, -1.5, 0]} />

        {fixtures.map((f) => (
          <EntityNode
            key={f.document_id}
            id={f.document_id}
            position={positions[f.document_id] ?? [0, 0, 0]}
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

        {edges.map((e) => (
          <RelationshipEdge
            key={e.id}
            id={e.id}
            from={positions[e.source] ?? [0, 0, 0]}
            to={positions[e.target] ?? [0, 0, 0]}
            label="SUPERSEDES"
            provenance={`Source: Fixture metadata (${e.source}.supersedes)`}
            isSelected={selectedRel === e.id}
            onClick={() => openRelModal(e.id)}
          />
        ))}

        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          minDistance={3}
          maxDistance={20}
          maxPolarAngle={Math.PI / 1.8}
        />
      </Canvas>

      <WorldHUD
        query={customQuery ?? baseline?.query ?? "Corpus Visualization"}
        perspective={perspective}
        onPerspectiveChange={setPerspective}
        onBack={onBack}
        selectedEntity={selectedEntity}
        selectedRelationship={selectedRel}
      />

      <EntityInspectionModal
        isOpen={entityModalId !== null}
        onClose={closeEntityModal}
        documentId={entityModalId ?? ""}
        fixture={activeFixture}
        baseline={baseline}
        synapse={synapse}
        onNavigateToEntity={navigateToEntity}
      />

      {activeEdge && (
        <RelationshipInspectionModal
          isOpen={relModalOpen}
          onClose={closeRelModal}
          sourceEntity={activeEdge.source}
          targetEntity={activeEdge.target}
          relType="SUPERSEDES"
          provenance={`Fixture metadata (${activeEdge.source}.supersedes field)`}
          onNavigateToEntity={navigateToEntity}
        />
      )}
    </div>
  );
}
