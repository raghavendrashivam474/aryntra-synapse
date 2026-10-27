import { useState, useCallback, useEffect } from "react";
import type { LiveCompareResponse } from "../types/live";
import type { BaselineResult, SynapseResult, PolicyFixture } from "../types/experiment";
import { submitLiveQuery } from "../data/liveClient";
import EvidenceWorld from "./EvidenceWorld";

interface Props {
  onBackToRecorded: () => void;
}

type Status = "idle" | "loading" | "success" | "error";
type ViewMode = "cards" | "world3d";

const CARD: React.CSSProperties = {
  background: "#1a1a2e",
  border: "1px solid #2a2a4a",
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

const BADGE_LIVE: React.CSSProperties = {
  display: "inline-block",
  background: "#00e676",
  color: "#000",
  fontWeight: 700,
  fontSize: 11,
  padding: "2px 8px",
  borderRadius: 4,
  letterSpacing: 1,
  marginRight: 8,
};

const STATUS_OK: React.CSSProperties = { color: "#00e676" };
const STATUS_ERR: React.CSSProperties = { color: "#ff5252" };
const STATUS_WARN: React.CSSProperties = { color: "#ffc107" };
const STATUS_DIM: React.CSSProperties = { color: "#888" };

function statusColor(s: string): React.CSSProperties {
  if (s === "success" || s === "completed") return STATUS_OK;
  if (s === "error") return STATUS_ERR;
  if (s === "partial" || s === "not_available") return STATUS_WARN;
  return STATUS_DIM;
}

export default function LiveQueryView({ onBackToRecorded }: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [response, setResponse] = useState<LiveCompareResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [allFixtures, setAllFixtures] = useState<PolicyFixture[]>([]);

  // Load all 6 live fixtures for 3D world view
  useEffect(() => {
    fetch("/data/fixtures.json")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: PolicyFixture[]) => setAllFixtures(data))
      .catch(() => {});
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setStatus("loading");
    setErrorMsg("");
    setResponse(null);

    try {
      const res = await submitLiveQuery({ query: trimmed, top_k: 2 });
      setResponse(res);
      setStatus("success");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // If in 3D world mode, render EvidenceWorld with live results
  if (viewMode === "world3d" && response) {
    const bResult = response.baseline.result as BaselineResult | null;
    const sResult = response.synapse.result as SynapseResult | null;

    return (
      <div style={{ position: "relative", width: "100vw", height: "100vh" }}>
        <EvidenceWorld
          onBack={() => setViewMode("cards")}
          customBaseline={bResult}
          customSynapse={sResult}
          customFixtures={allFixtures}
          customQuery={response.query}
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 24, fontFamily: "system-ui, sans-serif", color: "#e0e0e0" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <span style={BADGE_LIVE}>LIVE ENGINE MODE</span>
          <span style={{ fontSize: 14, color: "#888" }}>Synapse Compare — Real-time Execution</span>
        </div>
        <button
          onClick={onBackToRecorded}
          style={{
            background: "transparent", border: "1px solid #555", color: "#aaa",
            padding: "6px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13,
          }}
        >
          ← Recorded Artifacts
        </button>
      </div>

      {/* Query Input */}
      <div style={{ ...CARD, display: "flex", gap: 8 }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a query about the authentication policy corpus..."
          disabled={status === "loading"}
          style={{
            flex: 1, padding: "10px 14px", fontSize: 15,
            background: "#0d0d1a", border: "1px solid #333", borderRadius: 4,
            color: "#fff", outline: "none",
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={status === "loading" || !query.trim()}
          style={{
            padding: "10px 20px", fontSize: 14, fontWeight: 600,
            background: status === "loading" ? "#333" : "#00bcd4",
            color: status === "loading" ? "#888" : "#000",
            border: "none", borderRadius: 4, cursor: status === "loading" ? "wait" : "pointer",
          }}
        >
          {status === "loading" ? "Executing..." : "Compare ▶"}
        </button>
      </div>

      {/* Error */}
      {status === "error" && (
        <div style={{ ...CARD, borderColor: "#ff5252" }}>
          <strong style={STATUS_ERR}>⚠ Execution Failed</strong>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "#ccc" }}>{errorMsg}</p>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#888" }}>
            Ensure the backend is running: <code>uvicorn experiments.synapse_compare.server.main:app --port 8000</code>
          </p>
        </div>
      )}

      {/* Results */}
      {status === "success" && response && (
        <>
          {/* View Mode Bar + Meta bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: "#666" }}>
              Run <code>{response.run_id}</code> · {response.metadata.execution_time_ms} ms ·
              Corpus: {response.corpus.documents.join(", ")}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                onClick={() => setViewMode("cards")}
                style={{
                  padding: "4px 12px", fontSize: 12, fontWeight: 600,
                  background: viewMode === "cards" ? "#00bcd4" : "#1a1a2e",
                  color: viewMode === "cards" ? "#000" : "#888",
                  border: "1px solid #333", borderRadius: 4, cursor: "pointer",
                }}
              >
                Card View
              </button>
              <button
                onClick={() => setViewMode("world3d")}
                style={{
                  padding: "4px 12px", fontSize: 12, fontWeight: 600,
                  background: viewMode === "world3d" ? "#00bcd4" : "#1a1a2e",
                  color: viewMode === "world3d" ? "#000" : "#888",
                  border: "1px solid #333", borderRadius: 4, cursor: "pointer",
                }}
              >
                🌐 3D Evidence World (6 Nodes)
              </button>
            </div>
          </div>

          {/* Execution Status Row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            {/* Baseline */}
            <div style={CARD}>
              <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>
                Lexical Baseline{" "}
                <span style={statusColor(response.baseline.execution_status)}>
                  [{response.baseline.execution_status.toUpperCase()}]
                </span>
              </h3>
              {response.baseline.result ? (
                <>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    <strong>Selected:</strong> {response.baseline.result.decision.selected_evidence.join(", ")}
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "#aaa" }}>
                    {response.baseline.result.decision.output}
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 12 }}>
                    Retrieval: {response.baseline.result.retrieval.method} ·
                    {response.baseline.result.retrieval.results.map(
                      (r) => ` ${r.document_id}(${r.score})`
                    )}
                  </p>
                </>
              ) : (
                <p style={STATUS_ERR}>{response.baseline.error}</p>
              )}
            </div>

            {/* Synapse */}
            <div style={CARD}>
              <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>
                Aryntra Synapse{" "}
                <span style={statusColor(response.synapse.execution_status)}>
                  [{response.synapse.execution_status.toUpperCase()}]
                </span>
              </h3>
              {response.synapse.result ? (
                <>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    <strong>Decision:</strong> {response.synapse.result.decision.outcome}{" "}
                    (confidence: {response.synapse.result.decision.confidence})
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 13 }}>
                    <strong>Selected:</strong> {response.synapse.result.retrieval.selected_evidence.join(", ")}
                    {" · "}
                    <strong>Rejected:</strong> {response.synapse.result.retrieval.rejected_evidence.join(", ") || "(none)"}
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 12, color: "#aaa" }}>
                    Temporal intent: {response.synapse.result.signals.temporal_context.query_intent} ·
                    Conflict: {response.synapse.result.signals.conflict_score} ·
                    Sufficiency: {response.synapse.result.signals.sufficiency_score}
                  </p>
                </>
              ) : (
                <p style={STATUS_ERR}>{response.synapse.error}</p>
              )}
            </div>
          </div>

          {/* Comparison */}
          <div style={CARD}>
            <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>
              Comparison{" "}
              <span style={statusColor(response.comparison.status)}>
                [{response.comparison.status.toUpperCase()}]
              </span>
            </h3>
            {response.comparison.status === "completed" && "notes" in response.comparison.result ? (
              <>
                <p style={{ margin: 0, fontSize: 13 }}>
                  <strong>Decision:</strong>{" "}
                  {(response.comparison.result as Record<string, unknown>).decision_comparison as string}
                </p>
                <p style={{ margin: "4px 0 0", fontSize: 13 }}>
                  Evidence match:{" "}
                  {String((response.comparison.result as Record<string, unknown>).evidence_selection_match)}
                </p>
                {((response.comparison.result as Record<string, unknown>).notes as string[]).length > 0 && (
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20, fontSize: 12, color: "#aaa" }}>
                    {((response.comparison.result as Record<string, unknown>).notes as string[]).map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <p style={STATUS_WARN}>
                Comparison could not be completed ({response.comparison.status}).
              </p>
            )}
          </div>

          {/* Evaluation */}
          <div style={CARD}>
            <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>
              Evaluation{" "}
              <span style={STATUS_WARN}>[{response.evaluation.status.toUpperCase()}]</span>
            </h3>
            <p style={{ margin: 0, fontSize: 13, color: "#aaa" }}>
              {response.evaluation.reason}
            </p>
          </div>
        </>
      )}

      {/* Idle hint */}
      {status === "idle" && (
        <div style={{ textAlign: "center", padding: 40, color: "#555", fontSize: 14 }}>
          Enter a query above to execute both engines against the policy corpus.
          <br />
          <span style={{ fontSize: 12 }}>
            Try: "What authentication policy is currently in effect for internal systems?"
          </span>
        </div>
      )}
    </div>
  );
}
