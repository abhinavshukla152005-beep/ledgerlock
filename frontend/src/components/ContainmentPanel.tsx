import type { Health, Probe } from "../types";

type Tone = "good" | "warn" | "bad" | "idle";

interface Row {
  label: string;
  value: string;
  tone: Tone;
  note: string;
}

function buildRows(probe: Probe | null): Row[] {
  if (!probe) {
    return [
      { label: "Network egress", value: "not probed", tone: "idle", note: "outbound sockets" },
      { label: "Root filesystem", value: "not probed", tone: "idle", note: "write attempt at /" },
      { label: "Secrets in env", value: "not probed", tone: "idle", note: "API keys, tokens" },
      { label: "Process cap", value: "not probed", tone: "idle", note: "100 concurrent children" },
      { label: "Runtime identity", value: "not probed", tone: "idle", note: "uid inside sandbox" },
    ];
  }
  const p = probe.payload;
  const net = p.network_egress ?? "unknown";
  const root = p.root_write ?? "unknown";
  const secrets = p.secret_env_keys ?? [];
  const children = p.child_processes_started;
  const capped = Boolean(p.fork_error) || (typeof children === "number" && children < 100);

  return [
    {
      label: "Network egress",
      value: /blocked/i.test(net) ? "blocked" : /allowed/i.test(net) ? "open" : net,
      tone: /blocked/i.test(net) ? "good" : "bad",
      note: net,
    },
    {
      label: "Root filesystem",
      value: /blocked/i.test(root) ? "read-only" : /allowed/i.test(root) ? "writable" : root,
      tone: /blocked/i.test(root) ? "good" : "bad",
      note: root,
    },
    {
      label: "Secrets in env",
      value: secrets.length === 0 ? "none" : `${secrets.length} exposed`,
      tone: secrets.length === 0 ? "good" : "bad",
      note: secrets.length ? secrets.join(", ") : "no key material in the sandbox",
    },
    {
      label: "Process cap",
      value: capped ? "capped" : `${children ?? "?"} started`,
      tone: capped ? "good" : "warn",
      note: p.fork_error ? `fork refused: ${p.fork_error}` : "no limit reached",
    },
    {
      label: "Runtime identity",
      value:
        typeof p.uid === "number" ? `uid ${p.uid}` : p.uid === null ? "not reported" : "unknown",
      tone: typeof p.uid === "number" && p.uid !== 0 ? "good" : "warn",
      note: p.uid === null ? "unavailable on this host" : "non-root expected",
    },
  ];
}

interface Props {
  health: Health | null;
  probe: Probe | null;
  probing: boolean;
  onProbe: () => void;
}

export default function ContainmentPanel({ health, probe, probing, onProbe }: Props) {
  const rows = buildRows(probe);

  return (
    <section className="card containment-card">
      <div className="card-head">
        <span className="card-index">02</span>
        <h3>Containment</h3>
        <button type="button" className="ghost" onClick={onProbe} disabled={probing}>
          {probing ? "Probing…" : "Run probe"}
        </button>
      </div>

      <p className="containment-label">{health?.containment ?? "checking sandbox…"}</p>

      <ul className="probe-list">
        {rows.map((row) => (
          <li key={row.label} className={`probe probe--${row.tone}`}>
            <span className="probe-dot" aria-hidden="true" />
            <span className="probe-label">{row.label}</span>
            <span className="probe-value">{row.value}</span>
            <span className="probe-note">{row.note}</span>
          </li>
        ))}
      </ul>

      {probe?.error ? <p className="probe-error">{probe.error}</p> : null}
      <p className="hint">
        The probe runs inside the same sandbox as the checker and reports what it can reach. A
        development host will fail the process-cap check.
      </p>
    </section>
  );
}
