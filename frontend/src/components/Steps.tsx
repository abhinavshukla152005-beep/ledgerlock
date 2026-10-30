import type { Step } from "../types";

const LABEL: Record<string, string> = {
  ingest: "Ingest ledger",
  quarantine: "Quarantine scan",
  policy: "Resolve policy",
  codegen: "Generate checker",
  sandbox: "Execute in sandbox",
  retry: "Redraft on failure",
  fallback: "Fall back to template",
  verify: "Diff with host reference",
  memo: "Write memo",
};

export default function Steps({ steps, durationMs }: { steps: Step[]; durationMs: number }) {
  return (
    <section className="card steps-card">
      <div className="card-head">
        <span className="card-index">04</span>
        <h3>Agent trace</h3>
        <span className="count">{(durationMs / 1000).toFixed(2)}s</span>
      </div>
      <ol className="steps">
        {steps.map((step, index) => (
          <li key={`${step.name}-${index}`} className={`step step--${step.status}`}>
            <span className="step-dot" aria-hidden="true" />
            <span className="step-name">{LABEL[step.name] ?? step.name}</span>
            <span className="step-detail">{step.detail}</span>
            <span className="step-time">{step.duration_ms} ms</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
