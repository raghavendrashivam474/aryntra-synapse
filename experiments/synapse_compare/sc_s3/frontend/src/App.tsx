import { useState } from "react";
import DecisionView from "./components/DecisionView";
import EvidenceWorld from "./components/EvidenceWorld";

export default function App() {
  const [view, setView] = useState<"decision" | "world">("decision");

  if (view === "world") {
    return <EvidenceWorld onBack={() => setView("decision")} />;
  }

  return <DecisionView onEnterWorld={() => setView("world")} />;
}
