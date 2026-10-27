import type { ComparisonResult } from "../types/experiment";

export default function ResearchFinding({ data }: { data: ComparisonResult }) {
  return (
    <section className="research-finding">
      <h2>Research Finding</h2>
      <p className="finding-headline">{data.decision_comparison}</p>
      <ul>
        {data.notes.map((note, i) => (
          <li key={i}>{note}</li>
        ))}
      </ul>
      <p className="finding-caveat">
        Both systems failed the temporal-correctness evaluation. Synapse detected
        relevant signals (temporal intent, supersession relationship) but its
        evidence assembler still selected the superseded document. This is a
        research finding, not a frontend presentation issue.
      </p>
    </section>
  );
}
