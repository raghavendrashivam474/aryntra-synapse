type Perspective = "baseline" | "synapse" | "compare";

interface Props {
  query: string;
  perspective: Perspective;
  onPerspectiveChange: (p: Perspective) => void;
  onBack: () => void;
  selectedEntity: string | null;
  selectedRelationship: string | null;
}

const PERSPECTIVE_LABELS: Record<Perspective, string> = {
  baseline: "Baseline",
  synapse: "Synapse",
  compare: "Compare Both",
};

export default function WorldHUD({
  query, perspective, onPerspectiveChange, onBack,
  selectedEntity, selectedRelationship,
}: Props) {
  return (
    <div className="world-hud">
      <div className="hud-top">
        <button className="hud-btn hud-btn-back" onClick={onBack}>
          ← Decision View
        </button>
        <div className="hud-perspective">
          {(["baseline", "synapse", "compare"] as const).map((p) => (
            <button
              key={p}
              className={`hud-btn ${perspective === p ? "hud-btn-active" : ""}`}
              onClick={() => onPerspectiveChange(p)}
            >
              {PERSPECTIVE_LABELS[p]}
            </button>
          ))}
        </div>
      </div>

      <div className="hud-query">
        <span className="hud-query-label">Q:</span> {query}
      </div>

      {(selectedEntity || selectedRelationship) && (
        <div className="hud-selection">
          {selectedEntity && (
            <span className="hud-sel-tag">Entity: {selectedEntity}</span>
          )}
          {selectedRelationship && (
            <span className="hud-sel-tag">Relationship: {selectedRelationship}</span>
          )}
        </div>
      )}

      <div className="hud-bottom">
        <span>Drag to rotate · Scroll to zoom · Click to inspect</span>
        <span className="hud-disclaimer">
          Entity positions are arbitrary — distance carries no semantic meaning.
        </span>
      </div>
    </div>
  );
}
