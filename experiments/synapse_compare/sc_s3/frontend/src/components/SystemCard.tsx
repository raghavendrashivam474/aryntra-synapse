import type { BaselineResult, SynapseResult } from "../types/experiment";

type Props =
  | { variant: "baseline"; data: BaselineResult }
  | { variant: "synapse"; data: SynapseResult };

function StatusBadge({ status }: { status: string }) {
  const isPass = status === "PASS";
  return (
    <span className={`badge ${isPass ? "badge-pass" : "badge-fail"}`}>
      {status}
    </span>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <span className="field-value">{value ?? "Not available"}</span>
    </div>
  );
}

function BaselineCard({ data }: { data: BaselineResult }) {
  return (
    <div className="system-card card-baseline">
      <h2>Lexical Baseline</h2>

      <Field label="Method" value={data.retrieval.method} />

      <Field
        label="Selected Evidence"
        value={data.decision.selected_evidence.join(", ")}
      />

      {data.retrieval.results.length > 0 && (
        <Field
          label="Retrieval Scores"
          value={data.retrieval.results
            .map((r) => `${r.document_id}: ${r.score}`)
            .join(" | ")}
        />
      )}

      <Field label="Decision" value={data.decision.output} />
      <Field label="Confidence" value="Not available" />

      <div className="field">
        <span className="field-label">Evaluation</span>
        <span className="field-value">
          <StatusBadge status={data.evaluation.status} />
          <span className="eval-detail">
            Expected: {data.evaluation.expected_current_document}
            {" | "}
            Selected current: {data.evaluation.selected_current_document ? "Yes" : "No"}
          </span>
        </span>
      </div>
    </div>
  );
}

function SynapseCard({ data }: { data: SynapseResult }) {
  return (
    <div className="system-card card-synapse">
      <h2>Aryntra Synapse</h2>

      <Field label="Method" value={data.retrieval.method} />

      <Field
        label="Selected Evidence"
        value={data.retrieval.selected_evidence.join(", ")}
      />

      <Field
        label="Rejected Evidence"
        value={data.retrieval.rejected_evidence.join(", ") || "None"}
      />

      <Field label="Decision" value={data.decision.outcome} />

      {data.decision.confidence !== null && (
        <Field label="Confidence" value={data.decision.confidence} />
      )}

      <Field
        label="Temporal Intent"
        value={data.signals.temporal_context.query_intent ?? "Not detected"}
      />
      <Field
        label="Sufficiency Score"
        value={data.signals.sufficiency_score}
      />
      <Field
        label="Relationships Detected"
        value={`${data.signals.relationships.node_count} nodes, ${data.signals.relationships.edge_count} edges`}
      />
      <Field
        label="Execution"
        value={`${data.execution.status} (${data.execution.pipeline_time_ms}ms)`}
      />

      <div className="field">
        <span className="field-label">Evaluation</span>
        <span className="field-value">
          <StatusBadge status={data.evaluation.status} />
          <span className="eval-detail">
            Expected: {data.evaluation.expected_current_document}
            {" | "}
            Selected current: {data.evaluation.selected_current_document ? "Yes" : "No"}
          </span>
        </span>
      </div>
    </div>
  );
}

export default function SystemCard(props: Props) {
  if (props.variant === "baseline") {
    return <BaselineCard data={props.data} />;
  }
  return <SynapseCard data={props.data} />;
}
