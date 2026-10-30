import { useEffect, useState } from "react";
import Inputs from "./components/Inputs";
import ContainmentPanel from "./components/ContainmentPanel";
import Findings from "./components/Findings";
import Steps from "./components/Steps";
import { getHealth, getRun, getSample, listRuns, runAudit, runProbe } from "./api";
import type { Health, Probe, Run, RunSummary } from "./types";

const VERDICT_TITLE: Record<string, string> = {
  verified: "Verified",
  unverified: "Unverified",
  error: "Rejected",
};

function money(amount: number, currency: string) {
  return `${currency} ${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "unexpected error";
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [policyText, setPolicyText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [useSample, setUseSample] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [running, setRunning] = useState(false);
  const [probe, setProbe] = useState<Probe | null>(null);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const refreshRuns = () => {
    listRuns()
      .then(setRuns)
      .catch(() => undefined);
  };

  useEffect(() => {
    getHealth().then(setHealth).catch((e) => setError(message(e)));
    getSample("policy.yaml").then(setPolicyText).catch(() => undefined);
    refreshRuns();
  }, []);

  const handleRun = async () => {
    if (!useSample && !file) {
      setError("Choose a CSV file or tick the sample ledger.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const result = await runAudit(useSample ? null : file, policyText);
      setRun(result);
      refreshRuns();
    } catch (e) {
      setError(message(e));
    } finally {
      setRunning(false);
    }
  };

  const handleProbe = async () => {
    setProbing(true);
    setError(null);
    try {
      setProbe(await runProbe());
    } catch (e) {
      setError(message(e));
    } finally {
      setProbing(false);
    }
  };

  const loadYaml = () => {
    getSample("policy.yaml").then(setPolicyText).catch((e) => setError(message(e)));
  };
  const loadProse = () => {
    getSample("policy-brief.txt").then(setPolicyText).catch((e) => setError(message(e)));
  };

  const openRun = (id: string) => {
    getRun(id)
      .then(setRun)
      .catch((e) => setError(message(e)));
  };

  const currency = run?.currency ?? "INR";

  return (
    <div className="app">
      <div className="aurora" aria-hidden="true" />
      <div className="grid-overlay" aria-hidden="true" />

      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path
                d="M16 3.5 26.5 7.4v8.4c0 6.6-4.4 10.8-10.5 12.4C9.9 26.6 5.5 22.4 5.5 15.8V7.4L16 3.5Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <path d="M11.5 14.5h9M11.5 18.5h5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </span>
          <div className="brand-text">
            <h1>LedgerLock</h1>
            <p>containment-first expense audit</p>
          </div>
        </div>

        <div className="status">
          <span className="pill">
            <i className={`dot ${health ? "dot--live" : ""}`} aria-hidden="true" />
            sandbox {health?.sandbox_backend ?? "…"}
          </span>
          <span className="pill">
            <i className="dot dot--model" aria-hidden="true" />
            inference {health?.inference ?? "…"}
          </span>
          {health ? <span className="pill pill--mono">{health.model}</span> : null}
        </div>
      </header>

      <main>
        <section className="hero">
          <p className="eyebrow">agent rush · challenge 01 — blast radius zero</p>
          <h2>
            Audit a ledger.
            <br />
            <em>Trust nothing it says.</em>
          </h2>
          <p className="lede">
            Receipt notes are untrusted input. LedgerLock quarantines instruction-like text,
            evaluates the rest inside a network-less read-only container, then diffs every finding
            against a host-side reference before a reviewer sees it.
          </p>
        </section>

        <div className="workspace">
          <Inputs
            policyText={policyText}
            onPolicyText={setPolicyText}
            file={file}
            onFile={setFile}
            useSample={useSample}
            onUseSample={setUseSample}
            running={running}
            onRun={handleRun}
            onLoadYaml={loadYaml}
            onLoadProse={loadProse}
          />
          <ContainmentPanel health={health} probe={probe} probing={probing} onProbe={handleProbe} />
        </div>

        {error ? (
          <div className="error-banner" role="alert">
            <strong>Request failed.</strong> {error}
          </div>
        ) : null}

        {run ? (
          <>
            <section className={`verdict verdict--${run.status}`}>
              <div className="verdict-main">
                <span className="verdict-kicker">run {run.id}</span>
                <h2>{VERDICT_TITLE[run.status] ?? run.status}</h2>
                <p>
                  {run.status === "verified"
                    ? "Sandbox output matched the host reference byte for byte."
                    : run.error ?? "Review the trace before trusting this result."}
                </p>
                <div className="verdict-meta">
                  <span>policy: {run.policy_source}</span>
                  <span>checker: {run.codegen_source}</span>
                  <span>memo: {run.llm_source}</span>
                  <span>sandbox: {run.backend}</span>
                </div>
              </div>
              <div className="verdict-stats">
                <div>
                  <b>{run.row_count}</b>
                  <span>rows audited</span>
                </div>
                <div>
                  <b>{run.finding_count}</b>
                  <span>findings</span>
                </div>
                <div>
                  <b>{run.quarantined_count}</b>
                  <span>quarantined</span>
                </div>
                <div>
                  <b>{(run.duration_ms / 1000).toFixed(2)}s</b>
                  <span>wall time</span>
                </div>
              </div>
            </section>

            <div className="results">
              <Findings findings={run.findings} currency={currency} />

              <div className="side">
                <section className="card quarantine-card">
                  <div className="card-head">
                    <span className="tag tag--danger">held</span>
                    <h3>Quarantine</h3>
                    <span className="count">{run.quarantined_count}</span>
                  </div>
                  {run.quarantined.length === 0 ? (
                    <p className="empty-line">No instruction-like text in this ledger.</p>
                  ) : (
                    run.quarantined.map((row) => (
                      <div className="quarantine" key={row.txn_id}>
                        <div className="quarantine-top">
                          <code>{row.txn_id}</code>
                          <span>{row.vendor}</span>
                          <b>{money(row.amount, currency)}</b>
                        </div>
                        <p>{row.reason}</p>
                        <ul className="patterns">
                          {row.matched_patterns.map((pattern) => (
                            <li key={pattern}>
                              <code>{pattern}</code>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))
                  )}
                  <p className="hint">
                    Held before the checker or the model reads the row, so the injected instruction
                    never executes.
                  </p>
                </section>

                <section className="card memo-card">
                  <div className="card-head">
                    <span className="card-index">05</span>
                    <h3>Reviewer memo</h3>
                    <span className="chip">{run.llm_source}</span>
                  </div>
                  <p>{run.memo || "No memo produced for this run."}</p>
                </section>
              </div>
            </div>

            <Steps steps={run.steps} durationMs={run.duration_ms} />
          </>
        ) : (
          <section className="card empty-card">
            <span className="card-index">result</span>
            <h3>Nothing audited yet</h3>
            <p>
              The sample ledger carries nine policy breaches and one prompt-injection attempt hidden
              in a lunch note. Run it to watch the row get quarantined and the findings get verified.
            </p>
            <button type="button" className="run run--compact" onClick={handleRun} disabled={running}>
              {running ? "Auditing…" : "Run the sample audit"}
            </button>
          </section>
        )}
      </main>

      <footer>
        <span>
          LedgerLock · findings verified against an independent host implementation
        </span>
        {runs.length > 0 ? (
          <div className="recent">
            <span className="recent-label">recent</span>
            {runs.slice(0, 5).map((item) => (
              <button
                key={item.id}
                type="button"
                className={`recent-run recent-run--${item.status}`}
                onClick={() => openRun(item.id)}
                title={`${item.finding_count} findings · ${item.quarantined_count} quarantined`}
              >
                {item.id}
                <span>{item.finding_count}</span>
              </button>
            ))}
          </div>
        ) : null}
      </footer>
    </div>
  );
}
