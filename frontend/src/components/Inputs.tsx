import { useId } from "react";

interface Props {
  policyText: string;
  onPolicyText: (value: string) => void;
  file: File | null;
  onFile: (file: File | null) => void;
  useSample: boolean;
  onUseSample: (value: boolean) => void;
  running: boolean;
  onRun: () => void;
  onLoadYaml: () => void;
  onLoadProse: () => void;
}

export default function Inputs({
  policyText,
  onPolicyText,
  file,
  onFile,
  useSample,
  onUseSample,
  running,
  onRun,
  onLoadYaml,
  onLoadProse,
}: Props) {
  const fileId = useId();

  return (
    <section className="card inputs-card">
      <div className="card-head">
        <span className="card-index">01</span>
        <h3>Inputs</h3>
        <span className="card-note">untrusted</span>
      </div>

      <div className="field">
        <div className="field-label">
          <span>Expense ledger</span>
          <span className="label-meta">CSV</span>
        </div>
        <label className={`drop ${file ? "drop--loaded" : ""}`} htmlFor={fileId}>
          <input
            id={fileId}
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const picked = event.target.files?.[0] ?? null;
              onFile(picked);
              if (picked) onUseSample(false);
            }}
          />
          <span className="drop-icon">CSV</span>
          <span className="drop-title">{file ? file.name : "Drop a ledger or browse"}</span>
          <span className="drop-meta">
            {file
              ? `${Math.max(1, Math.round(file.size / 1024))} KB selected`
              : "txn_id, date, vendor, category, amount, currency, receipt_attached, approver, note"}
          </span>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={useSample}
            onChange={(event) => onUseSample(event.target.checked)}
          />
          <span>Use the sample ledger — 10 rows, one poisoned note</span>
        </label>
      </div>

      <div className="field">
        <div className="field-label">
          <span>Policy</span>
          <span className="mini-links">
            <button type="button" onClick={onLoadYaml}>
              YAML
            </button>
            <button type="button" onClick={onLoadProse}>
              Prose
            </button>
          </span>
        </div>
        <textarea
          value={policyText}
          spellCheck={false}
          rows={9}
          onChange={(event) => onPolicyText(event.target.value)}
          placeholder="Paste the expense policy as YAML or plain English."
        />
        <p className="hint">
          YAML is parsed directly. Prose is structured by the model before any rule runs.
        </p>
      </div>

      <button type="button" className="run" onClick={onRun} disabled={running}>
        {running ? (
          <>
            <span className="spinner" aria-hidden="true" />
            Auditing in sandbox…
          </>
        ) : (
          "Run containment audit"
        )}
      </button>
    </section>
  );
}
