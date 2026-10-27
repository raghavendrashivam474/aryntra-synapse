import { useState } from "react";
import DecisionView from "./components/DecisionView";
import EvidenceWorld from "./components/EvidenceWorld";
import LiveQueryView from "./components/LiveQueryView";

type Mode = "recorded" | "live";
type RecordedView = "decision" | "world";

export default function App() {
  const [mode, setMode] = useState<Mode>("recorded");
  const [recordedView, setRecordedView] = useState<RecordedView>("decision");

  // --- Live Engine Mode ---
  if (mode === "live") {
    return <LiveQueryView onBackToRecorded={() => setMode("recorded")} />;
  }

  // --- Recorded Artifact Mode ---
  if (recordedView === "world") {
    return <EvidenceWorld onBack={() => setRecordedView("decision")} />;
  }

  return (
    <>
      {/* Mode selector bar */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 1000,
          display: "flex",
          justifyContent: "center",
          gap: 0,
          background: "#0d0d1a",
          borderBottom: "1px solid #2a2a4a",
          padding: "6px 0",
        }}
      >
        <button
          onClick={() => setMode("recorded")}
          style={{
            padding: "6px 18px",
            fontSize: 13,
            fontWeight: 600,
            background: "#00bcd4",
            color: "#000",
            border: "none",
            borderRadius: "4px 0 0 4px",
            cursor: "pointer",
          }}
        >
          Recorded Artifacts
        </button>
        <button
          onClick={() => setMode("live")}
          style={{
            padding: "6px 18px",
            fontSize: 13,
            fontWeight: 600,
            background: "transparent",
            color: "#888",
            border: "1px solid #333",
            borderRadius: "0 4px 4px 0",
            cursor: "pointer",
          }}
        >
          Live Engine
        </button>
      </div>

      {/* Spacer for fixed bar */}
      <div style={{ height: 40 }} />

      <DecisionView onEnterWorld={() => setRecordedView("world")} />
    </>
  );
}
